"""
FSM States for the /newhire wizard.
"""
from aiogram.fsm.state import State, StatesGroup


class NewHireStates(StatesGroup):
    """States for the new hire creation wizard."""
    
    # Starting state
    start = State()
    
    # Data collection states
    full_name = State()
    start_date = State()
    role = State()
    leader = State()
    legal = State()
    devops = State()
    docs_email = State()
    access_checklist = State()
    notes = State()
    
    # Confirmation state
    confirm = State()
