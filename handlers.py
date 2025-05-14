import logging
import os
from datetime import datetime
import pytz
from aiogram import types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from dotenv import load_dotenv

from database import (
    add_or_update_user,
    add_reminder,
    get_user_reminders,
    update_reminder,
    delete_reminder,
    get_moscow_time
)
from keyboards import admin_kb, cancel_kb, edit_kb, main_menu_kb
from states import ReminderStates

# Загрузка переменных окружения
load_dotenv()

logger = logging.getLogger(__name__)

ADMIN_ID = int(os.getenv('ADMIN_ID', '0'))

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

async def create_reminder(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    
    await message.answer(
        "Введите текст напоминания:",
        reply_markup=cancel_kb
    )
    await state.set_state(ReminderStates.waiting_for_text)

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

async def process_edit_callback(callback_query: types.CallbackQuery, state: FSMContext):
    logger.info(f"Received edit callback with data: {callback_query.data}")
    if callback_query.from_user.id != ADMIN_ID:
        await callback_query.answer("У вас нет прав для редактирования напоминаний")
        return
    
    try:
        reminder_id = int(callback_query.data.split("_")[1])
        logger.info(f"Processing edit for reminder ID: {reminder_id}")
        await state.update_data(editing_reminder_id=reminder_id)
        
        await callback_query.message.answer(
            "Выберите действие:",
            reply_markup=edit_kb
        )
        await callback_query.answer()
    except Exception as e:
        logger.error(f"Error in edit callback: {e}")
        await callback_query.answer("Произошла ошибка при обработке запроса")

async def process_edit_text_choice(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    
    data = await state.get_data()
    if 'editing_reminder_id' not in data:
        await message.answer("Ошибка: не выбрано напоминание для редактирования", reply_markup=admin_kb)
        return
    
    await message.answer(
        "Введите новый текст напоминания:",
        reply_markup=main_menu_kb
    )
    await state.set_state(ReminderStates.editing_reminder_text)

async def process_edit_time_choice(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    
    data = await state.get_data()
    if 'editing_reminder_id' not in data:
        await message.answer("Ошибка: не выбрано напоминание для редактирования", reply_markup=admin_kb)
        return
    
    current_time = get_moscow_time()
    await message.answer(
        f"Введите новое время напоминания в формате ДД.ММ.ГГГГ ЧЧ:ММ (например, {current_time.strftime('%d.%m.%Y %H:%M')}):",
        reply_markup=main_menu_kb
    )
    await state.set_state(ReminderStates.editing_reminder_time)

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
                reply_markup=main_menu_kb
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
            reply_markup=main_menu_kb
        )

async def return_to_main(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Возврат на главную", reply_markup=admin_kb)

async def track_user(message: types.Message):
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