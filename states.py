from aiogram.fsm.state import State, StatesGroup

class ReminderStates(StatesGroup):
    waiting_for_text = State()
    waiting_for_time = State()
    editing_reminder = State()
    editing_reminder_text = State()
    editing_reminder_time = State() 