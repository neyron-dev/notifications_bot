import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import asyncio
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
import pytz
import sqlite3
from typing import List, Tuple

load_dotenv()
API_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')
ADMIN_ID = int(os.getenv('ADMIN_ID', '0'))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize bot and dispatcher
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

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

@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    # Добавляем всех пользователей, включая админа, в базу данных
    add_or_update_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
        message.from_user.last_name
    )
    
    if message.from_user.id == ADMIN_ID:
        await message.answer("Привет, админ!", reply_markup=admin_kb)
    else:
        await message.answer(
            "Привет! Я бот для напоминаний. Вы будете получать все напоминания, "
            "которые создает администратор."
        )

@dp.message(F.text == "Создать напоминание")
async def create_reminder(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    
    await message.answer(
        "Введите текст напоминания:",
        reply_markup=cancel_kb
    )
    await state.set_state(ReminderStates.waiting_for_text)

@dp.message(ReminderStates.waiting_for_text)
async def process_reminder_text(message: types.Message, state: FSMContext):
    if message.text == "Отмена":
        await state.clear()
        await message.answer("Создание напоминания отменено", reply_markup=admin_kb)
        return

    await state.update_data(reminder_text=message.text)
    current_time = get_moscow_time()
    await message.answer(
        f"Введите дату и время напоминания в формате ДД.ММ.ГГГГ ЧЧ:ММ (например, {current_time.strftime('%d.%m.%Y %H:%M')}):",
        reply_markup=cancel_kb
    )
    await state.set_state(ReminderStates.waiting_for_time)

@dp.message(ReminderStates.waiting_for_time)
async def process_reminder_time(message: types.Message, state: FSMContext):
    if message.text == "Отмена":
        await state.clear()
        await message.answer("Создание напоминания отменено", reply_markup=admin_kb)
        return

    try:
        moscow_tz = pytz.timezone('Europe/Moscow')
        reminder_time = datetime.strptime(message.text, "%d.%m.%Y %H:%M")
        reminder_time = moscow_tz.localize(reminder_time)
        
        if reminder_time < get_moscow_time():
            await message.answer(
                "Нельзя создать напоминание в прошлом. Пожалуйста, введите будущую дату и время:",
                reply_markup=cancel_kb
            )
            return

        data = await state.get_data()
        reminder_text = data['reminder_text']
        
        try:
            # Сохраняем напоминание в базу данных
            reminder_id = add_reminder(message.from_user.id, reminder_text, reminder_time)
            
            await message.answer(
                f"Напоминание создано!\nID: {reminder_id}\nТекст: {reminder_text}\nВремя: {reminder_time.strftime('%d.%m.%Y %H:%M')} (МСК)",
                reply_markup=admin_kb
            )
        except Exception as e:
            logger.error(f"Error saving reminder: {e}")
            await message.answer(
                "Произошла ошибка при сохранении напоминания. Пожалуйста, попробуйте еще раз.",
                reply_markup=admin_kb
            )
        
        await state.clear()
        
    except ValueError:
        current_time = get_moscow_time()
        await message.answer(
            f"Неверный формат даты и времени. Пожалуйста, используйте формат ДД.ММ.ГГГГ ЧЧ:ММ (например, {current_time.strftime('%d.%m.%Y %H:%M')}):",
            reply_markup=cancel_kb
        )

@dp.message(F.text == "Список напоминаний")
async def list_reminders(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    reminders = get_user_reminders(message.from_user.id)
    if not reminders:
        await message.answer("У вас пока нет напоминаний.", reply_markup=admin_kb)
        return
    
    for reminder_id, text, reminder_time, is_sent in reminders:
        status = "✅ Отправлено" if is_sent else "⏳ Ожидает"
        reminder_time = datetime.fromisoformat(reminder_time)
        
        response = f"📋 Напоминание #{reminder_id}\n\n"
        response += f"Текст: {text}\n"
        response += f"Время: {reminder_time.strftime('%d.%m.%Y %H:%M')} (МСК)\n"
        response += f"Статус: {status}\n"
        
        keyboard = []
        if not is_sent:  # Показываем кнопки редактирования только для неотправленных напоминаний
            keyboard.append([
                types.InlineKeyboardButton(
                    text="✏️ Редактировать",
                    callback_data=f"edit_{reminder_id}"
                )
            ])
        
        if keyboard:
            reply_markup = types.InlineKeyboardMarkup(inline_keyboard=keyboard)
            await message.answer(response, reply_markup=reply_markup)
        else:
            await message.answer(response)

@dp.callback_query(F.data.startswith("edit_"))
async def process_edit_callback(callback_query: types.CallbackQuery, state: FSMContext):
    logger.info(f"Received edit callback with data: {callback_query.data}")
    if callback_query.from_user.id != ADMIN_ID:
        await callback_query.answer("У вас нет прав для редактирования напоминаний")
        return
    
    try:
        reminder_id = int(callback_query.data.split("_")[1])
        logger.info(f"Processing edit for reminder ID: {reminder_id}")
        await state.update_data(editing_reminder_id=reminder_id)
        
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text='📝 Изменить текст')],
                [KeyboardButton(text='🕒 Изменить время')],
                [KeyboardButton(text='🗑 Удалить напоминание')],
                [KeyboardButton(text='На главную')]
            ],
            resize_keyboard=True
        )
        
        await callback_query.message.answer(
            "Выберите действие:",
            reply_markup=keyboard
        )
        await callback_query.answer()
    except Exception as e:
        logger.error(f"Error in edit callback: {e}")
        await callback_query.answer("Произошла ошибка при обработке запроса")

@dp.message(F.text == "📝 Изменить текст")
async def process_edit_text_choice(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    
    data = await state.get_data()
    if 'editing_reminder_id' not in data:
        await message.answer("Ошибка: не выбрано напоминание для редактирования", reply_markup=admin_kb)
        return
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text='На главную')]],
        resize_keyboard=True
    )
    
    await message.answer(
        "Введите новый текст напоминания:",
        reply_markup=keyboard
    )
    await state.set_state(ReminderStates.editing_reminder_text)

@dp.message(F.text == "🕒 Изменить время")
async def process_edit_time_choice(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    
    data = await state.get_data()
    if 'editing_reminder_id' not in data:
        await message.answer("Ошибка: не выбрано напоминание для редактирования", reply_markup=admin_kb)
        return
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text='На главную')]],
        resize_keyboard=True
    )
    
    current_time = get_moscow_time()
    await message.answer(
        f"Введите новое время напоминания в формате ДД.ММ.ГГГГ ЧЧ:ММ (например, {current_time.strftime('%d.%m.%Y %H:%M')}):",
        reply_markup=keyboard
    )
    await state.set_state(ReminderStates.editing_reminder_time)

@dp.message(F.text == "🗑 Удалить напоминание")
async def process_delete_reminder(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    
    data = await state.get_data()
    if 'editing_reminder_id' not in data:
        await message.answer("Ошибка: не выбрано напоминание для удаления", reply_markup=admin_kb)
        return
    
    reminder_id = data['editing_reminder_id']
    if delete_reminder(reminder_id):
        await message.answer("Напоминание успешно удалено!", reply_markup=admin_kb)
    else:
        await message.answer("Произошла ошибка при удалении напоминания", reply_markup=admin_kb)
    
    await state.clear()

@dp.callback_query(F.data == "cancel_edit")
async def process_cancel_edit(callback_query: types.CallbackQuery, state: FSMContext):
    logger.info("Received cancel_edit callback")
    await state.clear()
    await callback_query.message.answer("Редактирование отменено")
    await callback_query.answer()

@dp.message(F.text == "На главную")
async def return_to_main(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Возврат на главную", reply_markup=admin_kb)

@dp.message(ReminderStates.editing_reminder_text)
async def process_edit_text(message: types.Message, state: FSMContext):
    if message.text == "На главную":
        await state.clear()
        await message.answer("Возврат на главную", reply_markup=admin_kb)
        return
        
    if message.from_user.id != ADMIN_ID:
        return
    
    data = await state.get_data()
    reminder_id = data['editing_reminder_id']
    
    if update_reminder(reminder_id, text=message.text):
        await message.answer("Текст напоминания успешно обновлен!", reply_markup=admin_kb)
    else:
        await message.answer("Произошла ошибка при обновлении текста напоминания", reply_markup=admin_kb)
    
    await state.clear()

@dp.message(ReminderStates.editing_reminder_time)
async def process_edit_time(message: types.Message, state: FSMContext):
    if message.text == "На главную":
        await state.clear()
        await message.answer("Возврат на главную", reply_markup=admin_kb)
        return
        
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        moscow_tz = pytz.timezone('Europe/Moscow')
        new_time = datetime.strptime(message.text, "%d.%m.%Y %H:%M")
        new_time = moscow_tz.localize(new_time)
        
        if new_time < get_moscow_time():
            await message.answer(
                "Нельзя установить время в прошлом. Пожалуйста, введите будущую дату и время:",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard=[[KeyboardButton(text='На главную')]],
                    resize_keyboard=True
                )
            )
            return
        
        data = await state.get_data()
        reminder_id = data['editing_reminder_id']
        
        if update_reminder(reminder_id, reminder_time=new_time):
            await message.answer("Время напоминания успешно обновлено!", reply_markup=admin_kb)
        else:
            await message.answer("Произошла ошибка при обновлении времени напоминания", reply_markup=admin_kb)
        
        await state.clear()
        
    except ValueError:
        current_time = get_moscow_time()
        await message.answer(
            f"Неверный формат даты и времени. Пожалуйста, используйте формат ДД.ММ.ГГГГ ЧЧ:ММ (например, {current_time.strftime('%d.%m.%Y %H:%M')}):",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text='На главную')]],
                resize_keyboard=True
            )
        )

@dp.message()
async def track_user(message: types.Message):
    # Отслеживаем всех пользователей, которые взаимодействуют с ботом
    try:
        logger.info(f"Tracking user: {message.from_user.id}")
        add_or_update_user(
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
            message.from_user.last_name
        )
        logger.info(f"Successfully tracked user: {message.from_user.id}")
    except Exception as e:
        logger.error(f"Error tracking user {message.from_user.id}: {e}")

async def send_missed_reminders():
    try:
        logger.info("Checking for missed reminders...")
        conn = sqlite3.connect('reminders.db')
        c = conn.cursor()
        current_time = get_moscow_time().isoformat()
        logger.info(f"Current time for query: {current_time}")
        # Получаем все неотправленные напоминания, которые должны были быть отправлены
        c.execute('''
            SELECT id, user_id, text, reminder_time 
            FROM reminders 
            WHERE is_sent = 0 AND reminder_time <= ?
        ''', (current_time,))
        missed_reminders = c.fetchall()
        logger.info(f"SQL query executed, found {len(missed_reminders)} reminders")
        conn.close()

        if missed_reminders:
            logger.info(f"Found {len(missed_reminders)} missed reminders")
            users = get_all_users()
            logger.info(f"Found {len(users)} users to send reminders to")
            
            for reminder_id, user_id, text, reminder_time in missed_reminders:
                logger.info(f"Processing reminder {reminder_id}: {text}")
                for user_id in users:
                    try:
                        logger.info(f"Attempting to send reminder {reminder_id} to user {user_id}")
                        await bot.send_message(
                            user_id,
                            f"🔔 Пропущенное напоминание!\n\n{text}"
                        )
                        logger.info(f"Successfully sent reminder {reminder_id} to user {user_id}")
                    except Exception as e:
                        logger.error(f"Error sending missed reminder to user {user_id}: {e}")
                mark_reminder_as_sent(reminder_id)
                logger.info(f"Marked reminder {reminder_id} as sent")
        else:
            logger.info("No missed reminders found")
    except Exception as e:
        logger.error(f"Error sending missed reminders: {e}")

async def check_reminders():
    while True:
        try:
            logger.info("Checking for pending reminders...")
            reminders = get_pending_reminders()
            logger.info(f"Found {len(reminders)} pending reminders")
            
            for reminder_id, user_id, text, reminder_time in reminders:
                try:
                    logger.info(f"Processing reminder {reminder_id}: {text}")
                    # Отправляем напоминание всем пользователям
                    users = get_all_users()
                    logger.info(f"Found {len(users)} users to send reminders to")
                    
                    if not users:
                        logger.warning("No users found in database, skipping reminder")
                        continue
                        
                    for user_id in users:
                        try:
                            logger.info(f"Attempting to send reminder {reminder_id} to user {user_id}")
                            await bot.send_message(
                                user_id,
                                f"🔔 Напоминание!\n\n{text}"
                            )
                            logger.info(f"Successfully sent reminder {reminder_id} to user {user_id}")
                        except Exception as e:
                            logger.error(f"Error sending reminder to user {user_id}: {e}")
                    
                    # Удаляем напоминание после отправки
                    if delete_reminder(reminder_id):
                        logger.info(f"Successfully deleted reminder {reminder_id} after sending")
                    else:
                        logger.error(f"Failed to delete reminder {reminder_id}")
                except Exception as e:
                    logger.error(f"Error processing reminder {reminder_id}: {e}")
        except Exception as e:
            logger.error(f"Error in check_reminders loop: {e}")
        await asyncio.sleep(60)  # Проверяем каждую минуту

# Добавим функцию для просмотра всех напоминаний в базе
def debug_print_reminders():
    try:
        conn = sqlite3.connect('reminders.db')
        c = conn.cursor()
        c.execute('SELECT * FROM reminders')
        reminders = c.fetchall()
        logger.info("All reminders in database:")
        for reminder in reminders:
            logger.info(f"ID: {reminder[0]}, User: {reminder[1]}, Text: {reminder[2]}, Time: {reminder[3]}, Created: {reminder[4]}, Sent: {reminder[5]}")
        conn.close()
    except Exception as e:
        logger.error(f"Error printing reminders: {e}")

async def main():
    try:
        logger.info("Starting bot...")
        # Выводим все напоминания для отладки
        debug_print_reminders()
        
        # Отправляем пропущенные напоминания при запуске
        logger.info("Sending missed reminders...")
        await send_missed_reminders()
        
        # Запускаем проверку напоминаний в фоновом режиме
        logger.info("Starting reminder check loop...")
        asyncio.create_task(check_reminders())
        
        logger.info("Starting bot polling...")
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Error in main: {e}")
        raise

if __name__ == '__main__':
    asyncio.run(main()) 