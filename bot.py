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

 
bot = Bot(token=TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler(timezone="Asia/Bishkek")
reminders = []


def get_weather_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh_weather"))
    return keyboard.as_markup()


def get_list_keyboard(current_index: int, total_count: int) -> InlineKeyboardMarkup:
    """Создает кнопки со значками-стрелками для прокрутки на часах."""
    keyboard = InlineKeyboardBuilder()
    
    prev_idx = current_index - 1 if current_index > 0 else total_count - 1
    next_idx = current_index + 1 if current_index < total_count - 1 else 0
    
    keyboard.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data=f"scroll_{prev_idx}"),
        InlineKeyboardButton(text=f"📍 {current_index + 1}/{total_count}", callback_data="ignore"),
        InlineKeyboardButton(text="Дальше ▶️", callback_data=f"scroll_{next_idx}")
    )
    return keyboard.as_markup()


async def send_reminder(chat_id: int, text: str):
    """Эта функция сработает в назначенное время."""
    await bot.send_message(chat_id, f"⏰ НАПОМИНАНИЕ: {text}")
 
@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "Привет! Я бот-напоминалка.\n\n"
        "Используй:\n"
        "/remind ЧЧ:ММ текст — чтобы создать напоминание\n"
        "/list — скролл-список задач 📱\n"
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
 
    # Разбираем время ЧЧ:ММ
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
 
    scheduler.add_job(send_reminder, trigger="date", run_date=run_at, args=[message.chat.id, text])
    reminders.append({"time": run_at, "text": text})
 
    await message.answer(
        f"✅ Запомнила! Напомню «{text}» "
        f"{run_at.strftime('%d.%m в %H:%M')}"
    )


# --- ТЕПЕРЬ ТУТ ВСЁ ИСПРАВЛЕНО И БУДЕТ РАБОТАТЬ! ---
@dp.message(Command("list"))
async def cmd_list(message: Message):
    # Оставляем только те, чьё время ещё не наступило
    active = [r for r in reminders if r["time"] > datetime.now()]
    
    # Теперь "Активных напоминаний нет" отправится ТОЛЬКО если список действительно пустой
    if not active:
        await message.answer("Активных напоминаний нет 📭")
        return

    active_sorted = sorted(active, key=lambda r: r["time"])
    total = len(active_sorted)
    
    first_item = active_sorted[0]
    text = (
        f"📋 **Твои напоминания (Скроллер):**\n\n"
        f"🔔 **Задача:** {first_item['text']}\n"
        f"📅 **Время:** {first_item['time'].strftime('%d.%m в %H:%M')}"
    )
    await message.answer(text, reply_markup=get_list_keyboard(0, total), parse_mode="Markdown")


@dp.callback_query(F.data.startswith("scroll_"))
async def process_scrolling(callback: CallbackQuery):
    """Срабатывает при прокрутке напоминаний на часах или телефоне."""
    index = int(callback.data.split("_")[1])
    active = [r for r in reminders if r["time"] > datetime.now()]
    
    if not active:
        await callback.message.edit_text("Активных напоминаний больше нет 📭")
        await callback.answer()
        return
        
    active_sorted = sorted(active, key=lambda r: r["time"])
    total = len(active_sorted)
    
    if index >= total:
        index = 0
        
    item = active_sorted[index]
    text = (
        f"📋 **Твои напоминания (Скроллер):**\n\n"
        f"🔔 **Задача:** {item['text']}\n"
        f"📅 **Время:** {item['time'].strftime('%d.%m в %H:%M')}"
    )
    
    await callback.message.edit_text(text, reply_markup=get_list_keyboard(index, total), parse_mode="Markdown")
    await callback.answer()


@dp.callback_query(F.data == "ignore")
async def process_ignore(callback: CallbackQuery):
    await callback.answer()


async def get_weather() -> str:
    """Запрашивает погоду у OpenWeather и собирает текст сообщения."""
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


# --- ТЕПЕРЬ ТУТ ТОЖЕ ВСЁ ИСПРАВЛЕНО! ---
async def send_morning_weather():
    text = await get_weather()
    await bot.send_message(MY_CHAT_ID, "Доброе утро! ☀️\n" + text, reply_markup=get_weather_keyboard())

 
async def main():
    # Настрой время рассылки на 2 минуты вперед от текущего времени на твоем компьютере!
    # Например, если сейчас 12:10, поставь hour=12, minute=12
    scheduler.add_job(send_morning_weather, trigger="cron", hour=12, minute=23)
    
    scheduler.start()
    print("Бот запущен. Остановка: Ctrl+C")
    await dp.start_polling(bot)


if __name__ == "__main__":  
    asyncio.run(main())