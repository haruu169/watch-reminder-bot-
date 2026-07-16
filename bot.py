import sqlite3
import asyncio 
import os
from datetime import datetime, timedelta
import aiohttp
 
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
 
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")  
WEATHER_KEY = "18406235f038f1ba6d2eba077bf23acf"  
CITY = "Bishkek"  
MY_CHAT_ID = 5190913819  
DB = "reminders.db"
 
bot = Bot(token=TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler(timezone="Asia/Bishkek")


# ---------- База данных (Этап 2) ----------
 
def db_init():
    """Создает таблицу напоминаний, если её еще нет."""
    with sqlite3.connect(DB) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS reminders ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "chat_id INTEGER, run_at TEXT, text TEXT)"
        )
 
 
def db_add(chat_id, run_at, text):
    """Добавляет новое напоминание в базу и возвращает его ID."""
    with sqlite3.connect(DB) as conn:
        cur = conn.execute(
            "INSERT INTO reminders (chat_id, run_at, text) VALUES (?, ?, ?)",
            (chat_id, run_at.isoformat(), text),
        )
        return cur.lastrowid  # id новой записи
 
 
def db_delete(reminder_id):
    """Удаляет напоминание из базы по ID."""
    with sqlite3.connect(DB) as conn:
        conn.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
 
 
def db_all():
    """Возвращает список всех напоминаний из базы."""
    with sqlite3.connect(DB) as conn:
        rows = conn.execute(
            "SELECT id, chat_id, run_at, text FROM reminders"
        ).fetchall()
    return [
        {"id": r[0], "chat_id": r[1],
         "time": datetime.fromisoformat(r[2]), "text": r[3]}
        for r in rows
    ]


# ---------- Планировщик ----------

async def send_reminder(reminder_id, chat_id, text):
    """Эта функция сработает в назначенное время."""
    await bot.send_message(chat_id, f"⏰ НАПОМИНАНИЕ: {text}")
    db_delete(reminder_id)  # сработало — удаляем из базы


def schedule_reminder(reminder_id, chat_id, run_at, text):
    """Регистрирует задачу в APScheduler."""
    scheduler.add_job(
        send_reminder, trigger="date", run_date=run_at,
        args=[reminder_id, chat_id, text],
        id=str(reminder_id),  # id задачи = id записи для возможности удаления
    )


def restore_reminders():
    """При старте бота возвращает в планировщик всё, что не успело сработать."""
    restored = 0
    for r in db_all():
        if r["time"] > datetime.now():
            schedule_reminder(r["id"], r["chat_id"], r["time"], r["text"])
            restored += 1
        else:
            db_delete(r["id"])  # удаляем старые просроченные напоминания
    print(f"Восстановлено напоминаний из базы: {restored}")


# ---------- Клавиатуры ----------

def get_weather_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh_weather"))
    return keyboard.as_markup()


# ---------- Обработчики команд ----------
 
@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "Привет! Я бот-напоминалка.\n\n"
        "Используй:\n"
        "/remind ЧЧ:ММ текст — чтобы создать напоминание\n"
        "/list — список задач с кнопками удаления 📋\n"
        "/weather — узнать погоду\n"
        "/id — узнать свой chat_id"
    )
 
@dp.message(Command("remind"))
async def cmd_remind(message: Message, command: CommandObject):
    if not command.args:
        await message.answer("Формат: /remind 15:30 текст напоминания")
        return
 
    parts = command.args.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "Не хватает текста. Пример: /remind 15:30 позвонить маме"
        )
        return
 
    time_str, text = parts
 
    try:
        hour, minute = map(int, time_str.split(":"))
        run_at = datetime.now().replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )
    except ValueError:
        await message.answer(
            "Не поняла время. Нужен формат ЧЧ:ММ, например 15:30"
        )
        return
 
    if run_at <= datetime.now():
        run_at += timedelta(days=1)
 
    # Сохраняем в базу данных и планируем в планировщике
    reminder_id = db_add(message.chat.id, run_at, text)
    schedule_reminder(reminder_id, message.chat.id, run_at, text)
 
    await message.answer(
        f"✅ Запомнила! Напомню «{text}» "
        f"{run_at.strftime('%d.%m в %H:%M')}"
    )


# ---------- Новые Inline-кнопки в /list (Этап 3) ----------

@dp.message(Command("list"))
async def cmd_list(message: Message):
    """Выводит каждое напоминание отдельным сообщением с кнопкой «Удалить»."""
    active = [r for r in db_all() if r["time"] > datetime.now()]
    
    if not active:
        await message.answer("Активных напоминаний нет 📭")
        return

    await message.answer(f"Активных напоминаний: {len(active)}")
    for r in sorted(active, key=lambda r: r["time"]):
        # Создаем индивидуальную кнопку удаления под каждым напоминанием
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="❌ Удалить",
                callback_data=f"del:{r['id']}",
            )
        ]])
        await message.answer(
            f"• {r['time'].strftime('%d.%m %H:%M')} — {r['text']}",
            reply_markup=kb,
        )


@dp.callback_query(F.data.startswith("del:"))
async def cb_delete(callback: CallbackQuery):
    """Обрабатывает нажатие на кнопку «❌ Удалить»."""
    reminder_id = int(callback.data.split(":")[1])

    db_delete(reminder_id)
    try:
        scheduler.remove_job(str(reminder_id))  # убираем задачу из планировщика
    except Exception:
        pass  # если задачи уже нет, то не страшно

    await callback.answer("Удалено ✅")  # убирает крутилку-спиннер на кнопке
    await callback.message.edit_text(     # меняет текст сообщения прямо в чате
        f"🗑 {callback.message.text} — удалено"
    )


# ---------- Погода и утренний брифинг (Этап 4) ----------

async def get_weather() -> str:
    """Запрашивает погоду у OpenWeather."""
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {
        "q": CITY,
        "appid": WEATHER_KEY,
        "units": "metric",   # градусы Цельсия
        "lang": "ru",        # описание по-русски
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as resp:
            if resp.status != 200:
                error_text = await resp.text()  
                return f"Ошибка OpenWeather (Код {resp.status}): {error_text}"
            
            data = await resp.json()
 
    temp = round(data["main"]["temp"])
    feels = round(data["main"]["feels_like"])
    desc = data["weather"][0]["description"]
    
    updated_time = datetime.now().strftime("%H:%M:%S")
    return (
        f"Погода в {CITY}: {desc}\n"
        f"🌡 {temp}°C (ощущается как {feels}°C)\n"
        f"🕒 Обновлено в: {updated_time}"
    )


@dp.message(Command("id"))
async def cmd_id(message: Message):
    await message.answer(f"Твой chat_id: {message.chat.id}")


@dp.message(Command("weather"))
async def cmd_weather(message: Message):
    await message.answer("Запрос погоды отправлен, секунду...")
    try:
        text = await get_weather()
        await message.answer(text, reply_markup=get_weather_keyboard())
    except Exception as e:
        await message.answer(f"⚠️ Ошибка в коде погоды:\n{e}")


@dp.callback_query(F.data == "refresh_weather")
async def process_refresh_weather(callback: CallbackQuery):
    new_text = await get_weather()
    try:
        await callback.message.edit_text(new_text, reply_markup=get_weather_keyboard())
        await callback.answer("Погода обновлена! 🔄")
    except Exception:
        await callback.answer("Уже актуально!")


async def send_morning_briefing():
    """Финальный утренний брифинг: объединяет погоду и планы на сегодня."""
    weather = await get_weather()

    # Берем из базы только сегодняшние задачи, которые еще не наступили
    today = [
        r for r in db_all()
        if r["time"].date() == datetime.now().date()
        and r["time"] > datetime.now()
    ]
    
    if today:
        plans = "\n".join(
            f"• {r['time'].strftime('%H:%M')} — {r['text']}"
            for r in sorted(today, key=lambda r: r["time"])
        )
        plans_block = f"\n\n📋 Сегодня:\n{plans}"
    else:
        plans_block = f"\n\n📋 На сегодня напоминаний нет."

    await bot.send_message(
        MY_CHAT_ID, "Доброе утро! ☀️\n" + weather + plans_block
    )

 
async def main():
    db_init()            # 1. Инициализируем базу данных SQLite
    restore_reminders()  # 2. Восстанавливаем сохраненные напоминания при старте
    
    # Регистрация ежедневной утренней рассылки брифинга
    # (Для моментального теста: поставь время на 2 минуты вперед от текущего на ПК!)
    scheduler.add_job(send_morning_briefing, trigger="cron", hour=8, minute=0)
    
    scheduler.start()
    print("Бот запущен. Остановка: Ctrl+C")
    await dp.start_polling(bot)


if __name__ == "__main__":  
    asyncio.run(main())