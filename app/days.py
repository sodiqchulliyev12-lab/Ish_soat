"""Who should work when: schedules (incl. night shifts), weekends, holidays and leave."""
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from . import db
from .utils import at_time


@dataclass
class Schedule:
    start: str          # HH:MM
    end: str            # HH:MM; earlier than start means the shift ends the next day
    weekend: set[int]

    @property
    def overnight(self) -> bool:
        return self.end <= self.start

    def window(self, day: date) -> tuple[datetime, datetime]:
        """Expected start and end of the shift that begins on `day`."""
        start = at_time(day, self.start)
        end = at_time(day + timedelta(days=1) if self.overnight else day, self.end)
        return start, end

    def label(self) -> str:
        night = " (tungi)" if self.overnight else ""
        return f"{self.start}–{self.end}{night}"


def parse_weekend(value: str | None) -> set[int]:
    return {int(x) for x in (value or "").split(",") if x.strip().isdigit()}


def schedule(worker, settings: dict) -> Schedule:
    """The worker's own schedule if set, otherwise the company default."""
    w = dict(worker) if worker is not None else {}
    return Schedule(
        start=w.get("start") or settings["start"],
        end=w.get("end") or settings["end"],
        weekend=parse_weekend(w["weekend"]) if w.get("weekend") is not None else parse_weekend(settings["weekend"]),
    )


class Calendar:
    """Answers 'what kind of day is this for this worker' for one period with few queries."""

    def __init__(self, start: date, end: date, settings: dict):
        self.settings = settings
        self.holidays = db.holidays_between(start, end)
        self.leaves: dict[int, list] = {}
        for lv in db.leaves_overlapping(start, end):
            self.leaves.setdefault(lv["tg_id"], []).append(lv)

    def leave_on(self, tg_id: int, day: date):
        d = day.isoformat()
        for lv in self.leaves.get(tg_id, []):
            if lv["start"] <= d <= lv["end"]:
                return lv
        return None

    def kind(self, worker, day: date) -> str:
        """'holiday', 'weekend', 'leave:<kind>' or 'work'."""
        if day.isoformat() in self.holidays:
            return "holiday"
        if day.weekday() in schedule(worker, self.settings).weekend:
            return "weekend"
        lv = self.leave_on(worker["tg_id"], day)
        if lv:
            return f"leave:{lv['kind']}"
        return "work"


def calendar_for(day: date, settings: dict | None = None) -> Calendar:
    return Calendar(day, day + timedelta(days=1), settings or db.get_settings())
