"""Everything a worker does: register, check in/out (location, selfie), ask for leave, see own month."""
import logging
from datetime import date, timedelta

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import Message, ReplyKeyboardRemove

from . import db
from .config import ADMIN_IDS, LEAVE_KINDS, is_admin
from .keyboards import (BTN_CANCEL, BTN_IN, BTN_LEAVE, BTN_MINE, BTN_OUT, PENDING, admin_kb, approve_kb,
                        cancel_kb, contact_kb, leave_kb, location_kb, worker_kb)
from .days import schedule
from .report import month_stats, shift_info, worker_month_text
from .utils import distance_m, fmt_minutes, hm, now, parse_day, parse_month, stamp, today

router = Router()
log = logging.getLogger(__name__)


async def notify_admins(bot: Bot, text: str, photo: str | None = None, **kwargs) -> None:
    for admin_id in ADMIN_IDS:
        try:
            if photo:
                await bot.send_photo(admin_id, photo, caption=text, **kwargs)
            else:
                await bot.send_message(admin_id, text, **kwargs)
        except Exception as e:  # admin never opened the bot, blocked it, etc.
            log.warning("admin %s not notified: %s", admin_id, e)


def menu_for(user_id: int):
    w = db.get_worker(user_id)
    active = bool(w and w["status"] == "active")
    if is_admin(user_id):
        return admin_kb(also_worker=active)
    return worker_kb() if active else None


@router.message(CommandStart())
async def start(message: Message):
    user_id = message.from_user.id
    w = db.get_worker(user_id)
    id_line = f"\n\nSizning Telegram ID: <code>{user_id}</code>"
    if is_admin(user_id):
        await message.answer("👑 Admin paneli. Pastdagi tugmalardan foydalaning.\n"
                             "Yordam: /yordam" + id_line, reply_markup=menu_for(user_id))
        return
    if w and w["status"] == "active":
        await message.answer(f"Salom, {w['name']}! Kelganda <b>{BTN_IN}</b>, ketayotganda <b>{BTN_OUT}</b> ni bosing.",
                             reply_markup=worker_kb())
    elif w and w["status"] == "pending":
        await message.answer("⏳ Arizangiz admin tomonidan ko'rib chiqilmoqda." + id_line)
    elif w and w["status"] == "blocked":
        await message.answer("🚫 Sizning kirishingiz yopilgan. Rahbaringizga murojaat qiling.")
    else:
        await message.answer("Assalomu alaykum! Ishchi sifatida ro'yxatdan o'tish uchun pastdagi tugma orqali "
                             "telefon raqamingizni yuboring." + id_line, reply_markup=contact_kb())


@router.message(F.contact)
async def on_contact(message: Message):
    c = message.contact
    user_id = message.from_user.id
    if c.user_id != user_id:
        await message.answer("Iltimos, o'zingizning raqamingizni tugma orqali yuboring.", reply_markup=contact_kb())
        return
    w = db.get_worker(user_id)
    if w and w["status"] != "pending":
        await start(message)
        return
    name = " ".join(x for x in (c.first_name, c.last_name) if x).strip() or message.from_user.full_name
    phone = c.phone_number if c.phone_number.startswith("+") else "+" + c.phone_number
    db.add_worker(user_id, name, phone, stamp(now()))
    if not ADMIN_IDS:
        await message.answer("⚠️ Botda admin belgilanmagan (.env dagi ADMIN_IDS). Rahbaringizga ayting.")
        return
    await message.answer("✅ Ariza yuborildi. Admin tasdiqlagach sizga xabar keladi.",
                         reply_markup=ReplyKeyboardRemove())
    await notify_admins(message.bot, f"👷 <b>Yangi ishchi arizasi</b>\n{name}\n{phone}\nID: <code>{user_id}</code>",
                        reply_markup=approve_kb(user_id))


def active_worker(message: Message):
    w = db.get_worker(message.from_user.id)
    return w if w and w["status"] == "active" else None


def not_active_text(user_id: int) -> str:
    w = db.get_worker(user_id)
    if w and w["status"] == "blocked":
        return "🚫 Sizning kirishingiz yopilgan. Rahbaringizga murojaat qiling."
    if w:
        return "⏳ Arizangiz hali tasdiqlanmagan."
    return "Siz hali ro'yxatdan o'tmagansiz. /start ni bosing."


# ---------- check in / out ----------

def blocker(w, action: str) -> str | None:
    """Why this check-in/out cannot happen now, if anything."""
    open_shift = db.latest_open_shift(w["tg_id"])
    if action == "in":
        if open_shift:
            d = date.fromisoformat(open_shift["date"])
            when = "bugun" if d == today() else f"{d:%d.%m} kuni"
            return f"Siz {when} {hm(open_shift['in_at'])} da kelgansiz. Ketayotganda <b>{BTN_OUT}</b> ni bosing."
        done = db.get_shift(w["tg_id"], today())
        if done:
            return f"Siz bugun {hm(done['in_at'])} da kelib, {hm(done['out_at'])} da ketgansiz."
        return None
    if not open_shift:
        done = db.get_shift(w["tg_id"], today())
        if done:
            return f"Siz bugun {hm(done['out_at'])} da ketgansiz."
        return f"Hali kelganingiz belgilanmagan. Avval <b>{BTN_IN}</b> ni bosing."
    return None


async def next_step(message: Message, w, state: dict):
    """Ask for whatever is still missing (location, then selfie), or finish."""
    settings = db.get_settings()
    if state["step"] == "start":
        if db.branches():
            state["step"] = "loc"
            PENDING[w["tg_id"]] = state
            await message.answer("📍 Ish joyida ekaningizni tasdiqlash uchun joylashuvni yuboring.",
                                 reply_markup=location_kb())
            return
        state["step"] = "loc_done"
    if state["step"] == "loc_done" and settings["selfie"] == "1":
        state["step"] = "photo"
        PENDING[w["tg_id"]] = state
        await message.answer("🤳 Endi selfi yuboring (📎 → Kamera).", reply_markup=cancel_kb())
        return
    PENDING.pop(w["tg_id"], None)
    await finish(message, w, state)


async def begin(message: Message, action: str):
    w = active_worker(message)
    if not w:
        await message.answer(not_active_text(message.from_user.id))
        return
    if reason := blocker(w, action):
        await message.answer(reason, reply_markup=menu_for(w["tg_id"]))
        return
    await next_step(message, w, {"action": action, "step": "start"})


@router.message(F.text == BTN_IN)
async def came(message: Message):
    await begin(message, "in")


@router.message(F.text == BTN_OUT)
async def left(message: Message):
    await begin(message, "out")


@router.message(F.text == BTN_CANCEL)
async def cancel(message: Message):
    PENDING.pop(message.from_user.id, None)
    await message.answer("Bekor qilindi.", reply_markup=menu_for(message.from_user.id))


def nearest_branch(w, lat: float, lon: float):
    allowed = [db.get_branch(w["branch_id"])] if w["branch_id"] else db.branches()
    allowed = [b for b in allowed if b]
    if not allowed:
        return None, 0.0
    return min(((b, distance_m(lat, lon, b["lat"], b["lon"])) for b in allowed), key=lambda x: x[1])


@router.message(F.location)
async def on_location(message: Message):
    user_id = message.from_user.id
    state = PENDING.get(user_id)
    loc = message.location
    if state and state["action"] in ("branch_new", "branch_move") and is_admin(user_id):
        PENDING.pop(user_id)
        radius = int(db.get_settings()["radius"])
        if state["action"] == "branch_new":
            bid = db.add_branch(state["name"], loc.latitude, loc.longitude, radius)
            text = f"🏢 «{state['name']}» filiali qo'shildi (ID {bid}, radius {radius} m)."
        else:
            db.update_branch(state["id"], lat=loc.latitude, lon=loc.longitude)
            text = "📍 Filial joylashuvi yangilandi."
        await message.answer(text + "\nFiliallar: /filiallar", reply_markup=menu_for(user_id))
        return
    if not state or state.get("step") != "loc":
        await message.answer(f"Avval <b>{BTN_IN}</b> yoki <b>{BTN_OUT}</b> tugmasini bosing.",
                             reply_markup=menu_for(user_id))
        return
    if message.forward_origin:
        await message.answer("Joylashuvni tugma orqali yuboring, uzatilgan joylashuv qabul qilinmaydi.",
                             reply_markup=location_kb())
        return
    w = active_worker(message)
    if not w:
        PENDING.pop(user_id, None)
        return
    branch, dist = nearest_branch(w, loc.latitude, loc.longitude)
    if branch is None:  # the branch was deleted meanwhile
        state.update(step="loc_done", lat=loc.latitude, lon=loc.longitude, branch_id=None)
        await next_step(message, w, state)
        return
    if dist > branch["radius"]:
        PENDING.pop(user_id, None)
        await message.answer(f"❌ Siz «{branch['name']}» dan {int(dist)} m uzoqdasiz (ruxsat: {branch['radius']} m). "
                             "Ish joyiga kelgach qayta urinib ko'ring.", reply_markup=menu_for(user_id))
        await notify_admins(message.bot, f"⚠️ {w['name']} «{branch['name']}» dan {int(dist)} m uzoqdan "
                                         f"{'Keldim' if state['action'] == 'in' else 'Ketdim'} bosishga urindi.")
        return
    state.update(step="loc_done", lat=loc.latitude, lon=loc.longitude, branch_id=branch["id"])
    await next_step(message, w, state)


@router.message(F.photo)
async def on_photo(message: Message):
    state = PENDING.get(message.from_user.id)
    if not state or state.get("step") != "photo":
        return
    if message.forward_origin:
        await message.answer("Selfini kamera orqali hozir oling, uzatilgan rasm qabul qilinmaydi.")
        return
    w = active_worker(message)
    if not w:
        PENDING.pop(message.from_user.id, None)
        return
    state.update(step="done", photo=message.photo[-1].file_id)
    PENDING.pop(w["tg_id"], None)
    await finish(message, w, state)


def shift_day(w, settings: dict, current) -> date:
    """A night-shift worker arriving after midnight belongs to yesterday's shift."""
    sched = schedule(w, settings)
    yesterday = current.date() - timedelta(days=1)
    if sched.overnight and not db.get_shift(w["tg_id"], yesterday):
        y_start, y_end = sched.window(yesterday)
        if y_start - timedelta(hours=4) <= current < y_end and current < sched.window(current.date())[0] - timedelta(hours=4):
            return yesterday
    return current.date()


async def finish(message: Message, w, state: dict):
    if reason := blocker(w, state["action"]):  # e.g. double tap while sending location
        await message.answer(reason, reply_markup=menu_for(w["tg_id"]))
        return
    settings = db.get_settings()
    current = now()
    kb = menu_for(w["tg_id"])
    lat, lon, photo = state.get("lat"), state.get("lon"), state.get("photo")
    branch = db.get_branch(state.get("branch_id"))
    where = f" ({branch['name']})" if branch and len(db.branches()) > 1 else ""
    if state["action"] == "in":
        day = shift_day(w, settings, current)
        db.check_in(w["tg_id"], day, stamp(current), lat, lon, state.get("branch_id"), photo)
        info = shift_info(db.get_shift(w["tg_id"], day), settings, w)
        late = f"\n⏰ Kechikish: {fmt_minutes(info.late)}" if info.late else ""
        await message.answer(f"✅ Xush kelibsiz! Kelgan vaqt: <b>{current:%H:%M}</b>{late}", reply_markup=kb)
        if settings["notify"] == "1":
            await notify_admins(message.bot, f"✅ {w['name']} keldi: {current:%H:%M}{where}{late}", photo=photo)
        return
    shift = db.latest_open_shift(w["tg_id"])
    db.check_out(shift["id"], stamp(current), lat, lon, photo=photo)
    info = shift_info(db.get_shift_by_id(shift["id"]), settings, w)
    early = f"\n🏃 Erta ketish: {fmt_minutes(info.early)}" if info.early else ""
    await message.answer(f"🏁 Xayr! Ketgan vaqt: <b>{current:%H:%M}</b>\nIshladingiz: "
                         f"<b>{fmt_minutes(info.worked)}</b>{early}", reply_markup=kb)
    if settings["notify"] == "1":
        await notify_admins(message.bot, f"🏁 {w['name']} ketdi: {current:%H:%M}{where} "
                                         f"({fmt_minutes(info.worked)}){early}", photo=photo)


# ---------- leave ----------

LEAVE_HELP = ("📝 <b>Ruxsat yoki ta'til so'rash</b>\n"
              "<code>/ruxsat 21.10 Shifokorga borishim kerak</code>: bir kun\n"
              "<code>/ruxsat 21.10 25.10 tatil Oilaviy sabab</code>: bir necha kun\n"
              "Turlari: <b>ruxsat</b> (o'z hisobidan, standart), <b>tatil</b>, <b>kasal</b>.\n"
              "Admin tasdiqlagach sizga xabar keladi.")


def parse_leave(parts: list[str]) -> tuple[date, date, str, str] | str:
    """'21.10 [25.10] [tatil|kasal|ruxsat] [izoh...]' -> (start, end, kind, note) or an error text."""
    start = parse_day(parts[0]) if parts else None
    if not start:
        return "Sanani yozing, masalan <code>21.10</code>."
    rest = parts[1:]
    end = parse_day(rest[0]) if rest else None
    if end:
        rest = rest[1:]
    end = end or start
    if end < start or (end - start).days > 60:
        return "Sanalar noto'g'ri (oxirgi sana boshidan keyin, 60 kundan oshmasin)."
    kind = "ruxsat"
    if rest and rest[0].lower().replace("'", "") in LEAVE_KINDS:
        kind, rest = rest[0].lower().replace("'", ""), rest[1:]
    return start, end, kind, " ".join(rest)


def leave_text(lv, w=None) -> str:
    w = w or db.get_worker(lv["tg_id"])
    s, e = date.fromisoformat(lv["start"]), date.fromisoformat(lv["end"])
    span = f"{s:%d.%m}" if s == e else f"{s:%d.%m} – {e:%d.%m} ({(e - s).days + 1} kun)"
    note = f"\nSabab: {lv['note']}" if lv["note"] else ""
    return f"🏖 <b>{w['name'] if w else lv['tg_id']}</b>: {LEAVE_KINDS[lv['kind']]}, {span}{note}"


@router.message(F.text == BTN_LEAVE)
async def leave_help(message: Message):
    await message.answer(LEAVE_HELP)


@router.message(Command("ruxsat"))
async def ask_leave(message: Message, command: CommandObject):
    w = active_worker(message)
    if not w:
        await message.answer(not_active_text(message.from_user.id))
        return
    parsed = parse_leave((command.args or "").split())
    if isinstance(parsed, str):
        await message.answer(parsed + "\n\n" + LEAVE_HELP)
        return
    start, end, kind, note = parsed
    leave_id = db.add_leave(w["tg_id"], start, end, kind, "pending", note, stamp(now()))
    lv = db.get_leave(leave_id)
    await message.answer("📨 So'rovingiz adminga yuborildi.\n\n" + leave_text(lv, w), reply_markup=menu_for(w["tg_id"]))
    await notify_admins(message.bot, "📝 <b>Ruxsat so'rovi</b>\n" + leave_text(lv, w), reply_markup=leave_kb(leave_id))


@router.message(F.text == BTN_MINE)
async def my_month(message: Message):
    w = active_worker(message)
    if not w:
        await message.answer(not_active_text(message.from_user.id))
        return
    start, end = parse_month(None)
    stats = month_stats(start, end, only=w["tg_id"])
    await message.answer(worker_month_text(stats[0], start), reply_markup=menu_for(w["tg_id"]))
