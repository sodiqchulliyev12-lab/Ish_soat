from aiogram.types import (InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton,
                           ReplyKeyboardMarkup)

BTN_IN, BTN_OUT, BTN_MINE, BTN_LEAVE = "✅ Keldim", "🏁 Ketdim", "📊 Mening oyim", "📝 Ruxsat so'rash"
BTN_TODAY, BTN_WORKERS, BTN_REPORT, BTN_SETTINGS = "📋 Bugun", "👥 Ishchilar", "📊 Oylik hisobot", "⚙️ Sozlamalar"
BTN_CANCEL = "⬅️ Bekor qilish"

# user_id -> what the next location/photo from that user is for:
#   {"action": "in"|"out", "step": "loc"|"photo", ...}  check-in/out in progress
#   {"action": "branch_new", "name": str} / {"action": "branch_move", "id": int}  admin setting a branch location
#   {"action": "position", "tg_id": int}  admin approved a worker and now types their position
PENDING: dict[int, dict] = {}


def worker_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text=BTN_IN), KeyboardButton(text=BTN_OUT)],
        [KeyboardButton(text=BTN_MINE), KeyboardButton(text=BTN_LEAVE)],
    ], resize_keyboard=True)


def admin_kb(also_worker: bool = False) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text=BTN_TODAY), KeyboardButton(text=BTN_WORKERS)],
        [KeyboardButton(text=BTN_REPORT), KeyboardButton(text=BTN_SETTINGS)],
    ]
    if also_worker:
        rows.append([KeyboardButton(text=BTN_IN), KeyboardButton(text=BTN_OUT)])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def contact_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="📱 Telefon raqamni yuborish", request_contact=True)]],
                               resize_keyboard=True, one_time_keyboard=True)


def location_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📍 Joylashuvni yuborish", request_location=True)],
        [KeyboardButton(text=BTN_CANCEL)],
    ], resize_keyboard=True, one_time_keyboard=True)


def approve_kb(tg_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Qabul qilish", callback_data=f"w:ok:{tg_id}"),
        InlineKeyboardButton(text="❌ Rad etish", callback_data=f"w:no:{tg_id}"),
    ]])


def leave_kb(leave_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Ruxsat berish", callback_data=f"l:ok:{leave_id}"),
        InlineKeyboardButton(text="❌ Rad etish", callback_data=f"l:no:{leave_id}"),
    ]])


def cancel_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=BTN_CANCEL)]], resize_keyboard=True, one_time_keyboard=True)
