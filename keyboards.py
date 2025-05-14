from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

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

# Клавиатура для редактирования
edit_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text='📝 Изменить текст')],
        [KeyboardButton(text='🕒 Изменить время')],
        [KeyboardButton(text='🗑 Удалить напоминание')],
        [KeyboardButton(text='На главную')]
    ],
    resize_keyboard=True
)

# Клавиатура для возврата на главную
main_menu_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text='На главную')]],
    resize_keyboard=True
) 