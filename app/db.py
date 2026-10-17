import sqlite3
from contextlib import contextmanager
from datetime import date

from .config import DB_PATH, DEFAULT_SETTINGS

SCHEMA = """
CREATE TABLE IF NOT EXISTS workers (
    tg_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    phone TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'active', 'blocked')),
    rate_type TEXT DEFAULT '' CHECK (rate_type IN ('', 'oylik', 'kunlik', 'soatlik')),
    rate INTEGER DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS shifts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    in_at TEXT NOT NULL,
    out_at TEXT,
    in_lat REAL, in_lon REAL, out_lat REAL, out_lon REAL,
    auto_closed INTEGER DEFAULT 0,
    note TEXT DEFAULT ''
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_shift_day ON shifts(tg_id, date);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS flags (key TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS branches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    radius INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS holidays (date TEXT PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS leaves (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_id INTEGER NOT NULL,
    start TEXT NOT NULL,
    end TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('tatil', 'kasal', 'ruxsat')),
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    note TEXT DEFAULT '',
    created_at TEXT NOT NULL
);
"""

# Columns added after the first release; init() adds them to older databases.
NEW_COLUMNS = {
    "workers": {"branch_id": "INTEGER", "start": "TEXT", "end": "TEXT", "weekend": "TEXT"},
    "shifts": {"branch_id": "INTEGER", "in_photo": "TEXT", "out_photo": "TEXT"},
}


@contextmanager
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init() -> None:
    with db() as c:
        c.executescript(SCHEMA)
        for table, cols in NEW_COLUMNS.items():
            have = {r["name"] for r in c.execute(f"PRAGMA table_info({table})")}
            for col, kind in cols.items():
                if col not in have:
                    c.execute(f"ALTER TABLE {table} ADD COLUMN {col} {kind}")
        for k, v in DEFAULT_SETTINGS.items():
            c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))
        # First release kept one workplace in settings; move it into a branch.
        s = {r["key"]: r["value"] for r in c.execute("SELECT * FROM settings")}
        if s.get("lat") and s.get("lon"):
            if not c.execute("SELECT 1 FROM branches").fetchone():
                c.execute("INSERT INTO branches (name, lat, lon, radius) VALUES (?, ?, ?, ?)",
                          ("Asosiy", float(s["lat"]), float(s["lon"]), int(s.get("radius") or 150)))
            c.execute("UPDATE settings SET value = '' WHERE key IN ('lat', 'lon')")


# ---------- settings / flags ----------

def get_settings() -> dict[str, str]:
    with db() as c:
        return {r["key"]: r["value"] for r in c.execute("SELECT * FROM settings")}


def set_setting(key: str, value: str) -> None:
    with db() as c:
        c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))


def flag_once(key: str) -> bool:
    """True the first time a key is seen (used for once-only messages)."""
    with db() as c:
        return c.execute("INSERT OR IGNORE INTO flags (key) VALUES (?)", (key,)).rowcount > 0


# ---------- workers ----------

def get_worker(tg_id: int) -> sqlite3.Row | None:
    with db() as c:
        return c.execute("SELECT * FROM workers WHERE tg_id = ?", (tg_id,)).fetchone()


def add_worker(tg_id: int, name: str, phone: str, created_at: str) -> None:
    with db() as c:
        c.execute(
            "INSERT INTO workers (tg_id, name, phone, created_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(tg_id) DO UPDATE SET name = excluded.name, phone = excluded.phone",
            (tg_id, name, phone, created_at),
        )


def set_worker(tg_id: int, **fields) -> bool:
    allowed = {"name", "phone", "status", "rate_type", "rate", "branch_id", "start", "end", "weekend"}
    if not fields or not set(fields) <= allowed:
        raise ValueError(fields)
    sql = ", ".join(f'"{k}" = ?' for k in fields)
    with db() as c:
        return c.execute(f"UPDATE workers SET {sql} WHERE tg_id = ?", (*fields.values(), tg_id)).rowcount > 0


def workers(status: str | None = "active") -> list[sqlite3.Row]:
    with db() as c:
        if status is None:
            return c.execute("SELECT * FROM workers ORDER BY status, name").fetchall()
        return c.execute("SELECT * FROM workers WHERE status = ? ORDER BY name", (status,)).fetchall()


# ---------- shifts ----------

def get_shift(tg_id: int, day: date) -> sqlite3.Row | None:
    with db() as c:
        return c.execute("SELECT * FROM shifts WHERE tg_id = ? AND date = ?", (tg_id, day.isoformat())).fetchone()


def get_shift_by_id(shift_id: int) -> sqlite3.Row | None:
    with db() as c:
        return c.execute("SELECT * FROM shifts WHERE id = ?", (shift_id,)).fetchone()


def latest_open_shift(tg_id: int) -> sqlite3.Row | None:
    with db() as c:
        return c.execute("SELECT * FROM shifts WHERE tg_id = ? AND out_at IS NULL ORDER BY date DESC LIMIT 1",
                         (tg_id,)).fetchone()


def check_in(tg_id: int, day: date, at: str, lat, lon, branch_id=None, photo=None) -> None:
    with db() as c:
        c.execute(
            "INSERT INTO shifts (tg_id, date, in_at, in_lat, in_lon, branch_id, in_photo) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (tg_id, day.isoformat(), at, lat, lon, branch_id, photo),
        )


def check_out(shift_id: int, at: str, lat, lon, auto: bool = False, photo=None) -> None:
    with db() as c:
        c.execute(
            "UPDATE shifts SET out_at = ?, out_lat = ?, out_lon = ?, auto_closed = ?, out_photo = ? WHERE id = ?",
            (at, lat, lon, int(auto), photo, shift_id),
        )


def set_shift(tg_id: int, day: date, in_at: str, out_at: str | None, note: str) -> None:
    with db() as c:
        c.execute(
            "INSERT INTO shifts (tg_id, date, in_at, out_at, note) VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(tg_id, date) DO UPDATE SET in_at = excluded.in_at, out_at = excluded.out_at, "
            "auto_closed = 0, note = excluded.note",
            (tg_id, day.isoformat(), in_at, out_at, note),
        )


def delete_shift(tg_id: int, day: date) -> bool:
    with db() as c:
        return c.execute("DELETE FROM shifts WHERE tg_id = ? AND date = ?", (tg_id, day.isoformat())).rowcount > 0


def shifts_between(start: date, end: date, tg_id: int | None = None) -> list[sqlite3.Row]:
    sql = "SELECT * FROM shifts WHERE date >= ? AND date < ?"
    args: list = [start.isoformat(), end.isoformat()]
    if tg_id is not None:
        sql += " AND tg_id = ?"
        args.append(tg_id)
    with db() as c:
        return c.execute(sql + " ORDER BY date, in_at", args).fetchall()


def all_open_shifts() -> list[sqlite3.Row]:
    with db() as c:
        return c.execute("SELECT * FROM shifts WHERE out_at IS NULL").fetchall()


# ---------- branches ----------

def branches() -> list[sqlite3.Row]:
    with db() as c:
        return c.execute("SELECT * FROM branches ORDER BY id").fetchall()


def get_branch(branch_id: int | None) -> sqlite3.Row | None:
    if branch_id is None:
        return None
    with db() as c:
        return c.execute("SELECT * FROM branches WHERE id = ?", (branch_id,)).fetchone()


def add_branch(name: str, lat: float, lon: float, radius: int) -> int:
    with db() as c:
        return c.execute("INSERT INTO branches (name, lat, lon, radius) VALUES (?, ?, ?, ?)",
                         (name, lat, lon, radius)).lastrowid


def update_branch(branch_id: int, **fields) -> bool:
    if not fields or not set(fields) <= {"name", "lat", "lon", "radius"}:
        raise ValueError(fields)
    sql = ", ".join(f"{k} = ?" for k in fields)
    with db() as c:
        return c.execute(f"UPDATE branches SET {sql} WHERE id = ?", (*fields.values(), branch_id)).rowcount > 0


def delete_branch(branch_id: int) -> bool:
    with db() as c:
        c.execute("UPDATE workers SET branch_id = NULL WHERE branch_id = ?", (branch_id,))
        return c.execute("DELETE FROM branches WHERE id = ?", (branch_id,)).rowcount > 0


# ---------- holidays ----------

def holidays_between(start: date, end: date) -> dict[str, str]:
    with db() as c:
        rows = c.execute("SELECT * FROM holidays WHERE date >= ? AND date < ? ORDER BY date",
                         (start.isoformat(), end.isoformat())).fetchall()
    return {r["date"]: r["name"] for r in rows}


def upcoming_holidays(start: date) -> list[sqlite3.Row]:
    with db() as c:
        return c.execute("SELECT * FROM holidays WHERE date >= ? ORDER BY date LIMIT 30", (start.isoformat(),)).fetchall()


def set_holiday(day: date, name: str) -> None:
    with db() as c:
        c.execute("INSERT OR REPLACE INTO holidays (date, name) VALUES (?, ?)", (day.isoformat(), name))


def delete_holiday(day: date) -> bool:
    with db() as c:
        return c.execute("DELETE FROM holidays WHERE date = ?", (day.isoformat(),)).rowcount > 0


# ---------- leaves ----------

def add_leave(tg_id: int, start: date, end: date, kind: str, status: str, note: str, created_at: str) -> int:
    with db() as c:
        return c.execute(
            "INSERT INTO leaves (tg_id, start, end, kind, status, note, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (tg_id, start.isoformat(), end.isoformat(), kind, status, note, created_at),
        ).lastrowid


def get_leave(leave_id: int) -> sqlite3.Row | None:
    with db() as c:
        return c.execute("SELECT * FROM leaves WHERE id = ?", (leave_id,)).fetchone()


def set_leave_status(leave_id: int, status: str) -> None:
    with db() as c:
        c.execute("UPDATE leaves SET status = ? WHERE id = ?", (status, leave_id))


def delete_leave(leave_id: int) -> bool:
    with db() as c:
        return c.execute("DELETE FROM leaves WHERE id = ?", (leave_id,)).rowcount > 0


def leaves_overlapping(start: date, end: date, tg_id: int | None = None, status: str = "approved") -> list[sqlite3.Row]:
    """Leaves touching [start, end)."""
    sql = 'SELECT * FROM leaves WHERE status = ? AND start < ? AND "end" >= ?'
    args: list = [status, end.isoformat(), start.isoformat()]
    if tg_id is not None:
        sql += " AND tg_id = ?"
        args.append(tg_id)
    with db() as c:
        return c.execute(sql + " ORDER BY start", args).fetchall()
