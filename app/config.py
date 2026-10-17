import os
from pathlib import Path
from zoneinfo import ZoneInfo

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_env(path: Path) -> None:
    """Minimal .env reader so no extra dependency is needed."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env(BASE_DIR / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x.isdigit()}
TZ = ZoneInfo(os.getenv("TIMEZONE", "Asia/Tashkent"))
DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "ishchilar.db"))
CURRENCY = os.getenv("CURRENCY", "so'm")
COMPANY = os.getenv("COMPANY_NAME", "Kompaniya")

# Defaults; admins change them later with /sozlama (stored in the database)
DEFAULT_SETTINGS = {
    "start": "09:00",
    "end": "18:00",
    "grace": "10",          # minutes allowed before counting as late
    "weekend": "6",         # weekday numbers, Monday=0 ... Sunday=6, comma separated
    "lat": "",              # legacy single workplace, moved into branches on start
    "lon": "",
    "radius": "150",        # meters, default for new branches
    "summary": "19:00",     # daily summary to admins
    "notify": "1",          # message admins on every check-in/out
    "selfie": "0",          # ask for a photo on check-in/out
}

# Leave kinds; paid ones count as worked days for monthly and daily pay
LEAVE_KINDS = {"tatil": "Ta'til", "kasal": "Kasallik", "ruxsat": "Ruxsat (o'z hisobidan)"}
PAID_LEAVE = {"tatil", "kasal"}


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS
