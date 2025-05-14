import logging
import asyncio
from datetime import datetime
import pytz
from database import (
    get_pending_reminders,
    get_all_users,
    delete_reminder,
    get_moscow_time,
    debug_print_reminders
)

logger = logging.getLogger(__name__)

async def send_missed_reminders(bot):
    try:
        logger.info("Checking for missed reminders...")
        reminders = get_pending_reminders()
        logger.info(f"Found {len(reminders)} missed reminders")

        if reminders:
            users = get_all_users()
            logger.info(f"Found {len(users)} users to send reminders to")
            
            for reminder_id, user_id, text, reminder_time in reminders:
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
                if delete_reminder(reminder_id):
                    logger.info(f"Successfully deleted reminder {reminder_id} after sending")
                else:
                    logger.error(f"Failed to delete reminder {reminder_id}")
        else:
            logger.info("No missed reminders found")
    except Exception as e:
        logger.error(f"Error sending missed reminders: {e}")

async def check_reminders(bot):
    while True:
        try:
            logger.info("Checking for pending reminders...")
            reminders = get_pending_reminders()
            logger.info(f"Found {len(reminders)} pending reminders")
            
            for reminder_id, user_id, text, reminder_time in reminders:
                try:
                    logger.info(f"Processing reminder {reminder_id}: {text}")
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
                    
                    if delete_reminder(reminder_id):
                        logger.info(f"Successfully deleted reminder {reminder_id} after sending")
                    else:
                        logger.error(f"Failed to delete reminder {reminder_id}")
                except Exception as e:
                    logger.error(f"Error processing reminder {reminder_id}: {e}")
        except Exception as e:
            logger.error(f"Error in check_reminders loop: {e}")
        await asyncio.sleep(60)  # Проверяем каждую минуту 