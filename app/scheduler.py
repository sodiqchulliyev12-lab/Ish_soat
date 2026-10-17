"""Runs every minute: reminders to check out, auto-closing forgotten shifts, daily summary."""
import logging
from datetime import date, timedelta

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from . import db
from .config import TZ
from .days import parse_weekend, schedule
from .report import today_text
from .utils import hm, now, parse_stamp, stamp
from .worker import notify_admins

log = logging.getLogger(__name__)

REMIND_AFTER = timedelta(minutes=30)     # after the expected end of the shift
AUTO_CLOSE_AFTER = timedelta(hours=6)    # close a forgotten shift at its expected end


async def send(bot: Bot, user_id: int, text: str) -> None:
    try:
        await bot.send_message(user_id, text)
    except Exception as e:
        log.warning("send to %s failed: %s", user_id, e)


async def tick(bot: Bot) -> None:
    current = now()
    day = current.date()
    s = db.get_settings()

    closed = []
    for sh in db.all_open_shifts():
        w = db.get_worker(sh["tg_id"])
        end = schedule(w, s).window(date.fromisoformat(sh["date"]))[1]
        # 1. "Did you forget to check out?"
        if current >= end + REMIND_AFTER and db.flag_once(f"remind:{sh['id']}"):
            await send(bot, sh["tg_id"], f"🔔 Ish vaqtingiz {end:%H:%M} da tugadi. Ketgan bo'lsangiz "
                                         "<b>🏁 Ketdim</b> ni bosing.")
        # 2. Close it at the expected end time once it is clearly forgotten
        if current >= end + AUTO_CLOSE_AFTER:
            out = max(parse_stamp(sh["in_at"]), end)
            db.check_out(sh["id"], stamp(out), None, None, auto=True)
            closed.append(f"• {w['name'] if w else sh['tg_id']}: {hm(sh['in_at'])} → {out:%H:%M} (avto)")
            await send(bot, sh["tg_id"], f"ℹ️ «Ketdim» bosilmadi, ketish vaqti {out:%d.%m %H:%M} deb yozildi. "
                                         "Noto'g'ri bo'lsa rahbaringizga ayting.")
    if closed:
        await notify_admins(bot, "🌙 <b>«Ketdim» bosilmagan smenalar avtomatik yopildi:</b>\n" + "\n".join(closed))

    # 3. Daily summary for admins (not on holidays or the company's days off)
    workday = day.weekday() not in parse_weekend(s["weekend"]) and not db.holidays_between(day, day + timedelta(days=1))
    if workday and current.strftime("%H:%M") >= s["summary"] and db.flag_once(f"summary:{day}"):
        await notify_admins(bot, "📨 <b>Kunlik xulosa</b>\n\n" + today_text())


def setup(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=TZ)
    scheduler.add_job(tick, "cron", second=5, args=[bot], max_instances=1, coalesce=True)
    return scheduler
