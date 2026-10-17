"""Admin panel: workers, today's status, monthly report, schedules, branches, holidays, leave, settings."""
from datetime import date, timedelta

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import BotCommand, BufferedInputFile, CallbackQuery, Message

from . import db
from .config import ADMIN_IDS, LEAVE_KINDS
from .days import parse_weekend, schedule
from .keyboards import (BTN_REPORT, BTN_SETTINGS, BTN_TODAY, BTN_WORKERS, PENDING, approve_kb, leave_kb,
                        location_kb, worker_kb)
from .report import month_excel, month_stats, month_summary_text, today_text, worker_month_text
from .utils import WEEKDAYS, money, now, parse_amount, parse_day, parse_month, parse_time, stamp, today
from .worker import leave_text, parse_leave

router = Router()
router.message.filter(F.from_user.id.in_(ADMIN_IDS))
router.callback_query.filter(F.from_user.id.in_(ADMIN_IDS))

ADMIN_COMMANDS = [
    BotCommand(command="bugun", description="Bugun kim keldi"),
    BotCommand(command="ishchilar", description="Ishchilar ro'yxati"),
    BotCommand(command="hisobot", description="Oylik hisobot + Excel"),
    BotCommand(command="tatillar", description="Ta'til va ruxsatlar"),
    BotCommand(command="bayramlar", description="Bayram kunlari"),
    BotCommand(command="filiallar", description="Filiallar"),
    BotCommand(command="sozlama", description="Sozlamalar"),
    BotCommand(command="yordam", description="Admin buyruqlari"),
]

HELP = """<b>👑 Admin buyruqlari</b>

<b>Kunlik</b>
/bugun: kim keldi, kim kechikdi, kim kelmadi, kim ta'tilda

<b>Ishchilar</b>
/ishchilar: ro'yxat va ID lar
<code>/maosh ID oylik 4000000</code> (yoki <code>kunlik 150k</code>, <code>soatlik 20k</code>)
<code>/grafik ID 20:00 08:00</code>: shaxsiy grafik (tungi smena ham)
<code>/grafik ID 09:00 18:00 shanba,yakshanba</code>: dam olish kunlari bilan
<code>/grafik ID umumiy</code>: umumiy grafikka qaytarish
<code>/ism ID Yangi Ism</code> · <code>/bloklash ID</code> · <code>/tiklash ID</code>
<code>/ishchi ID</code>: bir ishchining shu oyi (<code>/ishchi ID 2026-09</code>)

<b>Ta'til va ruxsat</b>
/tatillar: so'rovlar va shu oydagi ta'tillar
<code>/tatil ID 21.10 25.10 tatil</code> (turi: tatil, kasal, ruxsat)
<code>/tatil_ochir 7</code>
Ta'til va kasallik kunlari oylik/kunlik maoshda ishlangan kun hisoblanadi, ruxsat esa yo'q.

<b>Bayramlar</b>
/bayramlar · <code>/bayram 31.12 Yangi yil</code> · <code>/bayram ochir 31.12</code>

<b>Filiallar (joylashuv tekshiruvi)</b>
/filiallar · <code>/filial qosh Chilonzor</code> (keyin joylashuv yuborasiz)
<code>/filial 2 joy</code> · <code>/filial 2 radius 200</code> · <code>/filial 2 ochir</code>
<code>/bogla ID 2</code>: ishchini filialga bog'lash · <code>/bogla ID hammasi</code>
Filial bo'lmasa joylashuv so'ralmaydi.

<b>Tuzatish</b>
<code>/tuzat ID 15.10 09:05 18:10</code> (tungi: <code>/tuzat ID 15.10 20:00 08:00</code>)
<code>/tuzat ID 15.10 ochir</code>

<b>Hisobot</b>
/hisobot: shu oy (matn + Excel) · <code>/hisobot 2026-09</code>

<b>Sozlamalar</b>
/sozlama · <code>/sozlama ish 09:00 18:00</code> · <code>/sozlama kechikish 10</code>
<code>/sozlama dam yakshanba</code> · <code>/sozlama xulosa 19:00</code>
<code>/sozlama xabar off</code> · <code>/sozlama selfi on</code>
<code>/sozlama selfi video</code>: kelish/ketishda dumaloq video so'raladi"""


def worker_id(arg: str):
    arg = arg.strip().lstrip("#")
    return db.get_worker(int(arg)) if arg.isdigit() else None


DAY_NAMES = {name.lower(): i for i, name in enumerate(WEEKDAYS)}


def parse_day_names(value: str) -> str | None:
    """'shanba,yakshanba' -> '5,6'; 'yoq' -> ''; invalid -> None."""
    names = [x for x in value.lower().replace("'", "").split(",") if x]
    if names == ["yoq"]:
        return ""
    if names and all(n in DAY_NAMES for n in names):
        return ",".join(str(DAY_NAMES[n]) for n in names)
    return None


def weekend_label(value: str | None) -> str:
    return ", ".join(WEEKDAYS[d] for d in sorted(parse_weekend(value))) or "yo'q"


@router.message(Command("yordam", "help"))
async def help_cmd(message: Message):
    await message.answer(HELP)


@router.message(Command("bugun"))
@router.message(F.text == BTN_TODAY)
async def today_cmd(message: Message):
    await message.answer(today_text())


# ---------- workers ----------

@router.message(Command("ishchilar"))
@router.message(F.text == BTN_WORKERS)
async def workers_cmd(message: Message):
    people = db.workers(None)
    if not people:
        await message.answer("Hali ishchi yo'q. Ishchilar botga /start bosib ro'yxatdan o'tadi.")
        return
    settings = db.get_settings()
    branches = {b["id"]: b["name"] for b in db.branches()}
    groups = {"active": "👷 <b>Faol</b>", "pending": "⏳ <b>Tasdiq kutmoqda</b>", "blocked": "🚫 <b>Bloklangan</b>"}
    lines = []
    for status, title in groups.items():
        rows = [w for w in people if w["status"] == status]
        if not rows:
            continue
        lines += ["", f"{title} ({len(rows)})"]
        for w in rows:
            extra = []
            if w["rate"]:
                extra.append(f"{w['rate_type']} {money(w['rate'])}")
            if w["start"] or w["weekend"] is not None:
                extra.append(f"grafik {schedule(w, settings).label()}")
            if w["branch_id"] in branches:
                extra.append(branches[w["branch_id"]])
            tail = f" · {' · '.join(extra)}" if extra else ""
            lines.append(f"<code>{w['tg_id']}</code> {w['name']} {w['phone']}{tail}")
    lines += ["", "Barcha buyruqlar: /yordam"]
    await message.answer("\n".join(lines).strip())
    for w in people:
        if w["status"] == "pending":
            await message.answer(f"⏳ {w['name']} {w['phone']}", reply_markup=approve_kb(w["tg_id"]))


@router.callback_query(F.data.startswith("w:"))
async def approve(call: CallbackQuery):
    _, action, raw = call.data.split(":", 2)
    w = db.get_worker(int(raw))
    if not w:
        await call.answer("Topilmadi", show_alert=True)
        return
    if w["status"] != "pending":
        await call.answer("Bu ariza allaqachon ko'rib chiqilgan.")
        return
    if action == "ok":
        db.set_worker(w["tg_id"], status="active")
        await call.message.edit_text(call.message.html_text + "\n\n✅ Qabul qilindi")
        await call.bot.send_message(w["tg_id"], "🎉 Siz ishchi sifatida tasdiqlandingiz! Kelganda ✅ Keldim, "
                                                "ketayotganda 🏁 Ketdim ni bosing.", reply_markup=worker_kb())
    else:
        db.set_worker(w["tg_id"], status="blocked")
        await call.message.edit_text(call.message.html_text + "\n\n❌ Rad etildi")
        await call.bot.send_message(w["tg_id"], "Arizangiz rad etildi.")
    await call.answer()


@router.message(Command("maosh"))
async def salary(message: Message, command: CommandObject):
    parts = (command.args or "").split()
    w = worker_id(parts[0]) if parts else None
    amount = parse_amount(parts[2]) if len(parts) == 3 else None
    if not w or len(parts) != 3 or parts[1] not in ("oylik", "kunlik", "soatlik") or not amount:
        await message.answer("Masalan: <code>/maosh 123456789 oylik 4000000</code> "
                             "(turi: oylik, kunlik yoki soatlik). ID: /ishchilar")
        return
    db.set_worker(w["tg_id"], rate_type=parts[1], rate=amount)
    await message.answer(f"💰 {w['name']}: {parts[1]} {money(amount)}")


@router.message(Command("grafik"))
async def set_schedule(message: Message, command: CommandObject):
    parts = (command.args or "").split()
    w = worker_id(parts[0]) if parts else None
    usage = ("Masalan: <code>/grafik ID 20:00 08:00</code>, <code>/grafik ID 09:00 18:00 shanba,yakshanba</code> "
             "yoki <code>/grafik ID umumiy</code>")
    if not w or len(parts) < 2:
        await message.answer(usage)
        return
    if parts[1] == "umumiy":
        db.set_worker(w["tg_id"], start=None, end=None, weekend=None)
    else:
        a = parse_time(parts[1])
        b = parse_time(parts[2]) if len(parts) > 2 else None
        weekend = parse_day_names(parts[3]) if len(parts) > 3 else None
        if not a or not b or a == b or (len(parts) > 3 and weekend is None):
            await message.answer(usage)
            return
        db.set_worker(w["tg_id"], start=a, end=b, **({"weekend": weekend} if len(parts) > 3 else {}))
    w = db.get_worker(w["tg_id"])
    sched = schedule(w, db.get_settings())
    await message.answer(f"🕘 {w['name']}: {sched.label()}, dam olish: {weekend_label(','.join(map(str, sched.weekend)))}")


@router.message(Command("ism"))
async def rename(message: Message, command: CommandObject):
    parts = (command.args or "").split(maxsplit=1)
    w = worker_id(parts[0]) if parts else None
    if not w or len(parts) < 2:
        await message.answer("Masalan: <code>/ism 123456789 Aliyev Ali</code>")
        return
    db.set_worker(w["tg_id"], name=parts[1].strip())
    await message.answer(f"✏️ Ism o'zgartirildi: {parts[1].strip()}")


@router.message(Command("bloklash", "tiklash"))
async def block(message: Message, command: CommandObject):
    w = worker_id(command.args or "")
    if not w:
        await message.answer(f"Masalan: <code>/{command.command} 123456789</code>")
        return
    status = "blocked" if command.command == "bloklash" else "active"
    db.set_worker(w["tg_id"], status=status)
    await message.answer(f"{'🚫' if status == 'blocked' else '✅'} {w['name']}: "
                         f"{'bloklandi' if status == 'blocked' else 'faol'}")


@router.message(Command("ishchi"))
async def one_worker(message: Message, command: CommandObject):
    parts = (command.args or "").split()
    w = worker_id(parts[0]) if parts else None
    period = parse_month(parts[1] if len(parts) > 1 else None)
    if not w or not period:
        await message.answer("Masalan: <code>/ishchi 123456789</code> yoki <code>/ishchi 123456789 2026-09</code>")
        return
    stats = month_stats(*period, only=w["tg_id"])
    if not stats:
        await message.answer("Bu ishchi faol emas.")
        return
    await message.answer(worker_month_text(stats[0], period[0]))


@router.message(Command("tuzat"))
async def fix(message: Message, command: CommandObject):
    parts = (command.args or "").split()
    w = worker_id(parts[0]) if parts else None
    day = parse_day(parts[1]) if len(parts) > 1 else None
    usage = ("Masalan: <code>/tuzat 123456789 15.10 09:05 18:10</code> yoki "
             "<code>/tuzat 123456789 15.10 ochir</code>")
    if not w or not day or len(parts) < 3:
        await message.answer(usage)
        return
    if parts[2] in ("ochir", "o'chir"):
        ok = db.delete_shift(w["tg_id"], day)
        await message.answer(f"🗑 {w['name']}, {day:%d.%m}: o'chirildi." if ok else "Bu kunda yozuv yo'q.")
        return
    t_in = parse_time(parts[2])
    t_out = parse_time(parts[3]) if len(parts) > 3 else None
    if not t_in or (len(parts) > 3 and not t_out) or t_out == t_in:
        await message.answer(usage)
        return
    out_day = day + timedelta(days=1) if t_out and t_out < t_in else day  # night shift ends next morning
    db.set_shift(w["tg_id"], day, f"{day} {t_in}", f"{out_day} {t_out}" if t_out else None, "admin tuzatdi")
    night = " (ertasi kuni)" if out_day != day else ""
    await message.answer(f"✏️ {w['name']}, {day:%d.%m}: {t_in} → {t_out or 'ishda'}{night}")


# ---------- report ----------

@router.message(Command("hisobot"))
@router.message(F.text == BTN_REPORT)
async def report(message: Message, command: CommandObject | None = None):
    period = parse_month(command.args if command else None)
    if not period:
        await message.answer("Oy formati: <code>/hisobot 2026-09</code>")
        return
    stats = month_stats(*period)
    await message.answer(month_summary_text(stats, period[0]))
    if stats:
        data = month_excel(stats, period[0])
        await message.answer_document(BufferedInputFile(data, filename=f"davomat_{period[0]:%Y-%m}.xlsx"))


# ---------- leave ----------

@router.callback_query(F.data.startswith("l:"))
async def decide_leave(call: CallbackQuery):
    _, action, raw = call.data.split(":", 2)
    lv = db.get_leave(int(raw))
    if not lv:
        await call.answer("Topilmadi", show_alert=True)
        return
    if lv["status"] != "pending":
        await call.answer("Bu so'rov allaqachon ko'rib chiqilgan.")
        return
    ok = action == "ok"
    db.set_leave_status(lv["id"], "approved" if ok else "rejected")
    await call.message.edit_text(call.message.html_text + ("\n\n✅ Ruxsat berildi" if ok else "\n\n❌ Rad etildi"))
    verdict = "✅ So'rovingiz tasdiqlandi" if ok else "❌ So'rovingiz rad etildi"
    try:
        await call.bot.send_message(lv["tg_id"], f"{verdict}\n\n" + leave_text(lv))
    except Exception:
        pass
    await call.answer()


@router.message(Command("tatil"))
async def add_leave(message: Message, command: CommandObject):
    parts = (command.args or "").split()
    w = worker_id(parts[0]) if parts else None
    parsed = parse_leave(parts[1:]) if w else "Ishchi ID sini yozing."
    if isinstance(parsed, str):
        await message.answer(parsed + "\nMasalan: <code>/tatil 123456789 21.10 25.10 tatil</code>")
        return
    start, end, kind, note = parsed
    leave_id = db.add_leave(w["tg_id"], start, end, kind, "approved", note, stamp(now()))
    lv = db.get_leave(leave_id)
    await message.answer(f"✅ Yozildi (#{leave_id})\n" + leave_text(lv, w))
    try:
        await message.bot.send_message(w["tg_id"], "ℹ️ Sizga yozildi:\n" + leave_text(lv, w))
    except Exception:
        pass


@router.message(Command("tatil_ochir"))
async def remove_leave(message: Message, command: CommandObject):
    arg = (command.args or "").strip().lstrip("#")
    if arg.isdigit() and db.delete_leave(int(arg)):
        await message.answer(f"🗑 #{arg} o'chirildi.")
    else:
        await message.answer("Topilmadi. Masalan: <code>/tatil_ochir 7</code> (raqam /tatillar da)")


@router.message(Command("tatillar"))
async def list_leaves(message: Message, command: CommandObject):
    period = parse_month(command.args) or parse_month(None)
    start, end = period
    with db.db() as c:
        pending = c.execute("SELECT * FROM leaves WHERE status = 'pending' ORDER BY start").fetchall()
    approved = db.leaves_overlapping(start, end)
    lines = []
    if approved:
        lines += [f"🏖 <b>Tasdiqlangan ({start:%m.%Y})</b>"]
        lines += [f"<i>#{lv['id']}</i> " + leave_text(lv).replace("🏖 ", "") for lv in approved]
    else:
        lines += [f"Bu oyda ({start:%m.%Y}) ta'til yoki ruxsat yo'q."]
    lines += ["", "Qo'shish: <code>/tatil ID 21.10 25.10 tatil</code> · o'chirish: <code>/tatil_ochir 7</code>"]
    await message.answer("\n".join(lines))
    for lv in pending:
        await message.answer("📝 <b>Kutilmoqda</b>\n" + leave_text(lv), reply_markup=leave_kb(lv["id"]))


# ---------- holidays ----------

@router.message(Command("bayramlar"))
async def list_holidays(message: Message):
    rows = db.upcoming_holidays(today() - timedelta(days=31))
    lines = ["🎉 <b>Bayram kunlari</b> (dam olish, kelmagan hisoblanmaydi)"]
    lines += [f"• {date.fromisoformat(r['date']):%d.%m.%Y} ({WEEKDAYS[date.fromisoformat(r['date']).weekday()]}): {r['name']}"
              for r in rows] or ["Hali kiritilmagan."]
    lines += ["", "Qo'shish: <code>/bayram 31.12 Yangi yil</code> · o'chirish: <code>/bayram ochir 31.12</code>"]
    await message.answer("\n".join(lines))


@router.message(Command("bayram"))
async def holiday(message: Message, command: CommandObject):
    parts = (command.args or "").split(maxsplit=1)
    if len(parts) == 2 and parts[0] in ("ochir", "o'chir"):
        day = parse_day(parts[1].strip())
        ok = bool(day) and db.delete_holiday(day)
        await message.answer(f"🗑 {day:%d.%m.%Y} bayram ro'yxatidan olindi." if ok else "Topilmadi.")
        return
    day = parse_day(parts[0]) if parts else None
    if not day:
        await message.answer("Masalan: <code>/bayram 31.12 Yangi yil</code> yoki <code>/bayram 21.03 Navro'z</code>")
        return
    name = parts[1].strip() if len(parts) > 1 else "Bayram"
    db.set_holiday(day, name)
    await message.answer(f"🎉 {day:%d.%m.%Y}: {name}. Bu kuni hech kim kelmagan hisoblanmaydi.")


# ---------- branches ----------

@router.message(Command("filiallar"))
async def list_branches(message: Message):
    rows = db.branches()
    if not rows:
        await message.answer("Filial yo'q, joylashuv tekshirilmaydi.\nQo'shish: <code>/filial qosh Asosiy</code>")
        return
    counts: dict = {}
    for w in db.workers("active"):
        counts[w["branch_id"]] = counts.get(w["branch_id"], 0) + 1
    lines = ["🏢 <b>Filiallar</b>"]
    for b in rows:
        lines.append(f"<b>{b['id']}</b>. {b['name']}: radius {b['radius']} m, ishchilar {counts.get(b['id'], 0)} · "
                     f"<a href=\"https://maps.google.com/?q={b['lat']},{b['lon']}\">xarita</a>")
    if counts.get(None):
        lines.append(f"\nFilialga bog'lanmagan {counts[None]} ishchi istalgan filialda belgilay oladi.")
    lines.append("\nBuyruqlar: /yordam (Filiallar bo'limi)")
    await message.answer("\n".join(lines), disable_web_page_preview=True)


@router.message(Command("filial"))
async def branch(message: Message, command: CommandObject):
    parts = (command.args or "").split(maxsplit=2)
    if len(parts) >= 2 and parts[0] in ("qosh", "qo'sh"):
        name = " ".join(parts[1:]).strip()
        PENDING[message.from_user.id] = {"action": "branch_new", "name": name}
        await message.answer(f"📍 «{name}» joylashuvini yuboring: shu yerda turib tugmani bosing yoki "
                             "📎 → Joylashuv orqali xaritadan tanlang.", reply_markup=location_kb())
        return
    b = db.get_branch(int(parts[0])) if parts and parts[0].isdigit() else None
    if not b or len(parts) < 2:
        await message.answer("Masalan: <code>/filial qosh Chilonzor</code>, <code>/filial 2 joy</code>, "
                             "<code>/filial 2 radius 200</code>, <code>/filial 2 ochir</code>")
        return
    if parts[1] == "joy":
        PENDING[message.from_user.id] = {"action": "branch_move", "id": b["id"]}
        await message.answer(f"📍 «{b['name']}» uchun yangi joylashuvni yuboring.", reply_markup=location_kb())
    elif parts[1] == "radius" and len(parts) == 3 and parts[2].isdigit() and int(parts[2]) >= 20:
        db.update_branch(b["id"], radius=int(parts[2]))
        await message.answer(f"✅ «{b['name']}»: radius {parts[2]} m")
    elif parts[1] in ("ochir", "o'chir"):
        db.delete_branch(b["id"])
        await message.answer(f"🗑 «{b['name']}» o'chirildi." + ("" if db.branches() else
                             " Filial qolmadi, endi joylashuv so'ralmaydi."))
    elif parts[1] == "nom" and len(parts) == 3:
        db.update_branch(b["id"], name=parts[2].strip())
        await message.answer(f"✏️ Nomi: {parts[2].strip()}")
    else:
        await message.answer("Tushunmadim. /yordam (Filiallar bo'limi)")


@router.message(Command("bogla"))
async def bind(message: Message, command: CommandObject):
    parts = (command.args or "").split()
    w = worker_id(parts[0]) if parts else None
    if not w or len(parts) != 2:
        await message.answer("Masalan: <code>/bogla 123456789 2</code> yoki <code>/bogla 123456789 hammasi</code>")
        return
    if parts[1] == "hammasi":
        db.set_worker(w["tg_id"], branch_id=None)
        await message.answer(f"✅ {w['name']} istalgan filialda belgilay oladi.")
        return
    b = db.get_branch(int(parts[1])) if parts[1].isdigit() else None
    if not b:
        await message.answer("Bunday filial yo'q. /filiallar")
        return
    db.set_worker(w["tg_id"], branch_id=b["id"])
    await message.answer(f"✅ {w['name']} → «{b['name']}»")


# ---------- settings ----------

SELFIE_LABELS = {"1": "ha, rasm", "video": "ha, dumaloq video", "0": "yo‘q"}


def settings_text() -> str:
    s = db.get_settings()
    branches = db.branches()
    place = f"{len(branches)} ta filial (/filiallar)" if branches else "belgilanmagan, joylashuv so'ralmaydi"
    return ("⚙️ <b>Sozlamalar</b>\n"
            f"🕘 Umumiy ish vaqti: {s['start']} – {s['end']}\n"
            f"⏰ Kechikishga ruxsat: {s['grace']} daq\n"
            f"🛌 Dam olish: {weekend_label(s['weekend'])}\n"
            f"📍 Ish joyi: {place}\n"
            f"🤳 Selfi talab qilinadi: {SELFIE_LABELS.get(s['selfie'], 'yo‘q')}\n"
            f"📨 Kunlik xulosa: {s['summary']}\n"
            f"🔔 Har bir kelish/ketish haqida xabar: {'yoqilgan' if s['notify'] == '1' else 'o‘chirilgan'}\n\n"
            "O'zgartirish: /yordam dagi Sozlamalar bo'limi")


@router.message(Command("sozlama"))
@router.message(F.text == BTN_SETTINGS)
async def settings(message: Message, command: CommandObject | None = None):
    parts = (command.args or "").split() if command else []
    if not parts:
        await message.answer(settings_text())
        return
    key, args = parts[0].lower(), parts[1:]
    error = None
    if key == "ish" and len(args) == 2 and (a := parse_time(args[0])) and (b := parse_time(args[1])) and a != b:
        db.set_setting("start", a)
        db.set_setting("end", b)
    elif key == "kechikish" and len(args) == 1 and args[0].isdigit():
        db.set_setting("grace", args[0])
    elif key == "dam" and len(args) == 1:
        value = parse_day_names(args[0])
        if value is None:
            error = "Kun nomlari: " + ", ".join(n.lower() for n in WEEKDAYS)
        else:
            db.set_setting("weekend", value)
    elif key == "joy":
        error = "Ish joyi endi filiallar orqali belgilanadi: <code>/filial qosh Asosiy</code>"
    elif key == "xulosa" and len(args) == 1 and (t := parse_time(args[0])):
        db.set_setting("summary", t)
    elif key == "selfi" and len(args) == 1 and args[0] in ("on", "off", "video"):
        db.set_setting("selfie", {"on": "1", "off": "0", "video": "video"}[args[0]])
    elif key == "xabar" and len(args) == 1 and args[0] in ("on", "off"):
        db.set_setting("notify", "1" if args[0] == "on" else "0")
    else:
        error = "Tushunmadim. Namunalar: /yordam"
    await message.answer(error or "✅ Saqlandi.\n\n" + settings_text())
