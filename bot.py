import asyncio
import os
 
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
from dotenv import load_dotenv
 
# Загружаем токен из файла .env
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
 
bot = Bot(token=TOKEN)
dp = Dispatcher()
 
 
@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "Привет! Я напоминалка. ⏰\n"
        "Напиши: /remind 15:30 сдать отчёт\n"
        "— и в 15:30 я пришлю напоминание."
    )
 
 
@dp.message()
async def echo(message: Message):
    await message.answer(f"Ты написала: {message.text}")
 
 
async def main():
    print("Бот запущен. Остановка: Ctrl+C")
    await dp.start_polling(bot)
 
 
if __name__ == "__main__":
    asyncio.run(main())