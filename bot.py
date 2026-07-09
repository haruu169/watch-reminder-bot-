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
 
async def send_reminder(chat_id: int, text: str):
    """Эта функция сработает в назначенное время."""
    await bot.send_message(chat_id, f"⏰ НАПОМИНАНИЕ: {text}")
 
 
@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "Привет! Я напоминалка. ⏰\n"
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
 
    scheduler.add_job(
        send_reminder,
        trigger="date",
        run_date=run_at,
        args=[message.chat.id, text],
    )
 
    await message.answer(
        f"✅ Запомнила! Напомню «{text}» "
        f"{run_at.strftime('%d.%m в %H:%M')}"
    )
 
 
async def main():
    scheduler.start()
    print("Бот запущен. Остановка: Ctrl+C")
    await dp.start_polling(bot)
 
 
if __name__ == "__main__":
    asyncio.run(main())