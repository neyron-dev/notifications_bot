import os
import logging
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv
from datetime import datetime, timedelta
import pytz
import sqlite3
from typing import List, Tuple

from database import init_db
from handlers import (
    send_welcome,
    create_reminder,
    process_reminder_text,
    process_reminder_time,
    list_reminders,
    process_edit_callback,
    process_edit_text_choice,
    process_edit_time_choice,
    process_delete_reminder,
    process_edit_text,
    process_edit_time,
    return_to_main,
    track_user
)
from reminders import send_missed_reminders, check_reminders
from states import ReminderStates

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()

# Получение токена бота из переменных окружения
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в переменных окружения")

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Database functions
def init_db():
    try:
        logger.info("Initializing database...")
        conn = sqlite3.connect('reminders.db')
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                reminder_time TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_sent BOOLEAN DEFAULT 0
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                last_interaction TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise

def add_or_update_user(user_id: int, username: str = None, first_name: str = None, last_name: str = None):
    try:
        logger.info(f"Adding/updating user {user_id} to database")
        conn = sqlite3.connect('reminders.db')
        c = conn.cursor()
        c.execute('''
            INSERT OR REPLACE INTO users (user_id, username, first_name, last_name, last_interaction)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (user_id, username, first_name, last_name))
        conn.commit()
        conn.close()
        logger.info(f"Successfully added/updated user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Error adding/updating user {user_id}: {e}")
        return False

def get_all_users():
    try:
        logger.info("Getting all users from database")
        conn = sqlite3.connect('reminders.db')
        c = conn.cursor()
        c.execute('SELECT user_id FROM users')
        users = c.fetchall()
        conn.close()
        user_ids = [user[0] for user in users]
        # Добавляем админа, если его нет в списке
        if ADMIN_ID not in user_ids:
            user_ids.append(ADMIN_ID)
            logger.info(f"Added admin {ADMIN_ID} to recipients list")
        logger.info(f"Found {len(user_ids)} users: {user_ids}")
        return user_ids
    except Exception as e:
        logger.error(f"Error getting users: {e}")
        return [ADMIN_ID]  # В случае ошибки возвращаем хотя бы админа

def add_reminder(user_id: int, text: str, reminder_time: datetime) -> int:
    try:
        logger.info(f"Adding reminder for user {user_id}")
        conn = sqlite3.connect('reminders.db')
        c = conn.cursor()
        c.execute(
            'INSERT INTO reminders (user_id, text, reminder_time) VALUES (?, ?, ?)',
            (user_id, text, reminder_time.isoformat())
        )
        reminder_id = c.lastrowid
        conn.commit()
        conn.close()
        logger.info(f"Reminder added successfully with ID {reminder_id}")
        return reminder_id
    except Exception as e:
        logger.error(f"Error adding reminder: {e}")
        raise

def get_pending_reminders() -> List[Tuple]:
    try:
        conn = sqlite3.connect('reminders.db')
        c = conn.cursor()
        current_time = get_moscow_time().isoformat()
        logger.info(f"Current time for query: {current_time}")
        c.execute('''
            SELECT id, user_id, text, reminder_time 
            FROM reminders 
            WHERE is_sent = 0 AND reminder_time <= ?
        ''', (current_time,))
        reminders = c.fetchall()
        logger.info(f"Found {len(reminders)} pending reminders in database")
        conn.close()
        return reminders
    except Exception as e:
        logger.error(f"Error getting pending reminders: {e}")
        return []

def mark_reminder_as_sent(reminder_id: int):
    try:
        conn = sqlite3.connect('reminders.db')
        c = conn.cursor()
        c.execute('UPDATE reminders SET is_sent = 1 WHERE id = ?', (reminder_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error marking reminder {reminder_id} as sent: {e}")

def get_user_reminders(user_id: int) -> List[Tuple]:
    try:
        conn = sqlite3.connect('reminders.db')
        c = conn.cursor()
        c.execute('''
            SELECT id, text, reminder_time, is_sent 
            FROM reminders 
            WHERE user_id = ? 
            ORDER BY reminder_time ASC, is_sent ASC
        ''', (user_id,))
        reminders = c.fetchall()
        conn.close()
        return reminders
    except Exception as e:
        logger.error(f"Error getting reminders for user {user_id}: {e}")
        return []

def update_reminder(reminder_id: int, text: str = None, reminder_time: datetime = None):
    try:
        conn = sqlite3.connect('reminders.db')
        c = conn.cursor()
        
        if text is not None and reminder_time is not None:
            c.execute('''
                UPDATE reminders 
                SET text = ?, reminder_time = ? 
                WHERE id = ?
            ''', (text, reminder_time.isoformat(), reminder_id))
        elif text is not None:
            c.execute('UPDATE reminders SET text = ? WHERE id = ?', (text, reminder_id))
        elif reminder_time is not None:
            c.execute('UPDATE reminders SET reminder_time = ? WHERE id = ?', (reminder_time.isoformat(), reminder_id))
            
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error updating reminder {reminder_id}: {e}")
        return False

def delete_reminder(reminder_id: int) -> bool:
    try:
        logger.info(f"Deleting reminder {reminder_id}")
        conn = sqlite3.connect('reminders.db')
        c = conn.cursor()
        c.execute('DELETE FROM reminders WHERE id = ?', (reminder_id,))
        conn.commit()
        conn.close()
        logger.info(f"Successfully deleted reminder {reminder_id}")
        return True
    except Exception as e:
        logger.error(f"Error deleting reminder {reminder_id}: {e}")
        return False

# Initialize database
try:
    init_db()
except Exception as e:
    logger.error(f"Failed to initialize database: {e}")

# States
class ReminderStates(StatesGroup):
    waiting_for_text = State()
    waiting_for_time = State()
    editing_reminder = State()
    editing_reminder_text = State()
    editing_reminder_time = State()

# Клавиатура для админа
admin_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text='Создать напоминание')],
        [KeyboardButton(text='Список напоминаний')]
    ],
    resize_keyboard=True
)

# Клавиатура для отмены
cancel_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text='Отмена')]],
    resize_keyboard=True
)

def get_moscow_time():
    moscow_tz = pytz.timezone('Europe/Moscow')
    return datetime.now(moscow_tz)

# Регистрация хендлеров
dp.message.register(send_welcome, Command("start"))
dp.message.register(create_reminder, F.text == "Создать напоминание")
dp.message.register(list_reminders, F.text == "Список напоминаний")
dp.message.register(process_reminder_text, ReminderStates.waiting_for_text)
dp.message.register(process_reminder_time, ReminderStates.waiting_for_time)
dp.message.register(process_edit_text_choice, F.text == "📝 Изменить текст")
dp.message.register(process_edit_time_choice, F.text == "🕒 Изменить время")
dp.message.register(process_delete_reminder, F.text == "🗑 Удалить напоминание")
dp.message.register(process_edit_text, ReminderStates.editing_reminder_text)
dp.message.register(process_edit_time, ReminderStates.editing_reminder_time)
dp.message.register(return_to_main, F.text == "На главную")
dp.callback_query.register(process_edit_callback, lambda c: c.data.startswith('edit_'))
dp.message.register(track_user)

async def main():
    # Инициализация базы данных
    init_db()
    
    # Отправка пропущенных напоминаний при запуске
    logger.info("Starting bot...")
    await send_missed_reminders(bot)
    
    # Запуск проверки напоминаний
    asyncio.create_task(check_reminders(bot))
    
    # Запуск бота
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main()) 