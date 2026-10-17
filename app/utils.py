import math
import re
from datetime import date, datetime, timedelta

from .config import CURRENCY, TZ

TIME_RE = re.compile(r"^([01]?\d|2[0-3])[:.]([0-5]\d)$")
WEEKDAYS = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"]
MONTHS = ["", "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun", "Iyul", "Avgust", "Sentabr",
          "Oktabr", "Noyabr", "Dekabr"]


def now() -> datetime:
    return datetime.now(TZ).replace(tzinfo=None, second=0, microsecond=0)


def today() -> date:
    return now().date()


def stamp(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M")


def parse_stamp(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d %H:%M")


def hm(s: str) -> str:
    """'2026-10-17 09:05' -> '09:05'."""
    return s[11:16] if s else "—"


def parse_time(s: str) -> str | None:
    m = TIME_RE.match(s.strip())
    return f"{int(m.group(1)):02d}:{m.group(2)}" if m else None


def parse_day(s: str) -> date | None:
    try:
        return date.fromisoformat(s)
    except ValueError:
        pass
    m = re.fullmatch(r"(\d{1,2})\.(\d{1,2})(?:\.(\d{4}))?", s)
    if m:
        try:
            return date(int(m.group(3) or today().year), int(m.group(2)), int(m.group(1)))
        except ValueError:
            return None
    return None


def parse_month(s: str | None) -> tuple[date, date] | None:
    """'' -> this month, '2026-09' or '09.2026' -> that month. Returns (start, end_exclusive)."""
    s = (s or "").strip()
    if not s:
        start = today().replace(day=1)
    else:
        m = re.fullmatch(r"(\d{4})-(\d{1,2})", s) or re.fullmatch(r"(\d{1,2})\.(\d{4})", s)
        if not m:
            return None
        year, month = (int(m.group(1)), int(m.group(2))) if "-" in s else (int(m.group(2)), int(m.group(1)))
        if not 1 <= month <= 12:
            return None
        start = date(year, month, 1)
    end = (start + timedelta(days=32)).replace(day=1)
    return start, end


def at_time(day: date, hhmm: str) -> datetime:
    h, m = map(int, hhmm.split(":"))
    return datetime.combine(day, datetime.min.time()).replace(hour=h, minute=m)


def minutes(a: datetime, b: datetime) -> int:
    return int((b - a).total_seconds() // 60)


def fmt_minutes(n: int) -> str:
    h, m = divmod(max(n, 0), 60)
    return f"{h} soat {m:02d} daq" if h else f"{m} daq"


def money(n: float) -> str:
    return f"{int(round(n)):,}".replace(",", " ") + f" {CURRENCY}"


def distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def parse_amount(s: str) -> int | None:
    s = s.strip().lower().replace("_", "").replace(" ", "")
    m = re.fullmatch(r"(\d+(?:[.,]\d+)?)(k|m|mln)?", s)
    if not m:
        return None
    n = float(m.group(1).replace(",", "."))
    n *= {"k": 1_000, "m": 1_000_000, "mln": 1_000_000}.get(m.group(2) or "", 1)
    return int(round(n)) if n > 0 else None
