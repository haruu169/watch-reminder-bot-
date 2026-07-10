import asyncio
import os
from datetime import datetime, timedelta
 
from aiogram import Bot, Dispatcher
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
 
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
 
bot = Bot(token=TOKEN)
dp = Dispatcher()
scheduler = scheduler = AsyncIOScheduler(timezone="Asia/Bishkek")
# Список напоминаний: каждый элемент — словарь {"time": ..., "text": ...}
reminders = []
async def send_reminder(chat_id: int, text: str):
    """Эта функция сработает в назначенное время."""
    await bot.send_message(chat_id, f"⏰ НАПОМИНАНИЕ: {text}")
 
 
@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        ""Привет! Я бот-напоминалка. ⏰\n\nИспользуй:\n/remind ЧЧ:ММ текст — чтобы создать напоминание\n/list — чтобы посмотреть активные задачи""
        "Формат: /remind 15:30 сдать отчёт"
    )
 
 
@dp.message(Command("remind"))
async def cmd_remind(message: Message, command: CommandObject):
    # command.args — всё, что после /remind,
    # например "15:30 сдать отчёт"
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
 
    # Если время уже прошло сегодня — переносим на завтра
    if run_at <= datetime.now():
        run_at += timedelta(days=1)
 
    scheduler.add_job( send_reminder, trigger="date", run_date=run_at, args=[message.chat.id, text], )
    reminders.append({"time": run_at, "text": text})
 
    await message.answer(
        f"✅ Запомнила! Напомню «{text}» "
        f"{run_at.strftime('%d.%m в %H:%M')}"
    )
 
@dp.message(Command("list"))
async def cmd_list(message: Message):
    # Оставляем только те, чьё время ещё не наступило
    active = [r for r in reminders if r["time"] > datetime.now()]
 
    if not active:
        await message.answer("Активных напоминаний нет 📭")
        return
 
    lines = [
        f"• {r['time'].strftime('%d.%m %H:%M')} — {r['text']}"
        for r in sorted(active, key=lambda r: r["time"])
    ]
    await message.answer("Твои напоминания:\n" + "\n".join(lines))
async def main():
    scheduler.start()
    print("Бот запущен. Остановка: Ctrl+C")
    await dp.start_polling(bot)
 
 
if __name__ == "__main__":
    asyncio.run(main())