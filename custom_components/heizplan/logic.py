"""Reine Zeitplan-Logik ohne Home-Assistant-Abhängigkeiten (dadurch leicht testbar)."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, tzinfo
from typing import Any

MODE_COMFORT = "comfort"
MODE_ECO = "eco"
MODES = (MODE_COMFORT, MODE_ECO)
DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
DAY_MINUTES = 24 * 60


def parse_hhmm(value: str) -> int:
    """'07:45' -> 465 Minuten. '24:00' ist als Tagesende erlaubt."""
    parts = str(value).strip().split(":")
    if len(parts) < 2:
        raise ValueError(f"Ungültige Uhrzeit: {value}")
    hours, minutes = int(parts[0]), int(parts[1])
    total = hours * 60 + minutes
    if not (0 <= hours <= 24 and 0 <= minutes < 60 and total <= DAY_MINUTES):
        raise ValueError(f"Ungültige Uhrzeit: {value}")
    return total


def format_hhmm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def normalize_week(week: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
    """Prüft einen Wochenplan, sortiert die Zeiträume und fasst Überlappungen zusammen."""
    result: dict[str, list[dict[str, str]]] = {}
    for day in DAYS:
        blocks: list[tuple[int, int]] = []
        for block in week.get(day) or []:
            start, end = parse_hhmm(block["from"]), parse_hhmm(block["to"])
            if end <= start:
                raise ValueError(
                    f"Ende muss nach dem Beginn liegen ({block['from']}–{block['to']})"
                )
            blocks.append((start, end))
        merged: list[list[int]] = []
        for start, end in sorted(blocks):
            if merged and start <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], end)
            else:
                merged.append([start, end])
        result[day] = [{"from": format_hhmm(s), "to": format_hhmm(e)} for s, e in merged]
    return result


def plan_mode(week: dict[str, list[dict[str, str]]], moment: datetime) -> str:
    minute = moment.hour * 60 + moment.minute
    for block in week.get(DAYS[moment.weekday()], []):
        if parse_hhmm(block["from"]) <= minute < parse_hhmm(block["to"]):
            return MODE_COMFORT
    return MODE_ECO


def active_exception(
    exceptions: list[dict[str, Any]], room_id: str, moment: datetime
) -> dict[str, Any] | None:
    """Die zuletzt angelegte Ausnahme gewinnt, falls sich mehrere überschneiden."""
    found = None
    for exc in exceptions:
        if room_id in exc["rooms"] and exc["start"] <= moment < exc["end"]:
            found = exc
    return found


def desired_mode(
    week: dict[str, list[dict[str, str]]],
    exceptions: list[dict[str, Any]],
    room_id: str,
    moment: datetime,
) -> tuple[str, dict[str, Any] | None]:
    exc = active_exception(exceptions, room_id, moment)
    if exc is not None:
        return exc["mode"], exc
    return plan_mode(week, moment), None


def _at(day: date, minutes: int, tz: tzinfo | None) -> datetime:
    return datetime.combine(day, time(), tzinfo=tz) + timedelta(minutes=minutes)


def next_change(
    week: dict[str, list[dict[str, str]]],
    exceptions: list[dict[str, Any]],
    room_id: str,
    now: datetime,
    horizon_days: int = 8,
) -> tuple[datetime, str] | None:
    """Nächster Zeitpunkt, an dem sich der Modus des Raums ändert, samt neuem Modus."""
    candidates: set[datetime] = set()
    for offset in range(horizon_days + 1):
        day = now.date() + timedelta(days=offset)
        for block in week.get(DAYS[day.weekday()], []):
            candidates.add(_at(day, parse_hhmm(block["from"]), now.tzinfo))
            candidates.add(_at(day, parse_hhmm(block["to"]), now.tzinfo))
    for exc in exceptions:
        if room_id in exc["rooms"]:
            candidates.update((exc["start"], exc["end"]))

    current, _ = desired_mode(week, exceptions, room_id, now)
    for moment in sorted(c for c in candidates if c > now):
        mode, _ = desired_mode(week, exceptions, room_id, moment)
        if mode != current:
            return moment, mode
    return None
