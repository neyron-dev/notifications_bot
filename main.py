import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()
API_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')
ADMIN_ID = int(os.getenv('ADMIN_ID', '0'))  # Convert to integer

logging.basicConfig(level=logging.INFO)

# Initialize bot and dispatcher
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Клавиатура для админа
admin_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text='Создать напоминание')]],
    resize_keyboard=True
)

@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    await message.answer(f"ADMIN_ID: {ADMIN_ID}")
    await message.answer(f"Your ID: {message.from_user.id}")
    if message.from_user.id == ADMIN_ID:
        await message.answer("Привет, админ!", reply_markup=admin_kb)
    else:
        await message.answer("У тебя нет прав для использования этого бота.")

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main()) 