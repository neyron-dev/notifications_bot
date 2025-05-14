import sqlite3
import logging
from datetime import datetime
import pytz

logger = logging.getLogger(__name__)

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
        logger.info(f"Found {len(user_ids)} users: {user_ids}")
        return user_ids
    except Exception as e:
        logger.error(f"Error getting users: {e}")
        return []

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

def get_pending_reminders():
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

def get_user_reminders(user_id: int):
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

def get_moscow_time():
    moscow_tz = pytz.timezone('Europe/Moscow')
    return datetime.now(moscow_tz)

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