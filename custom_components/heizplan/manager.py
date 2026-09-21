"""Speicherung und Steuerung für Heizplan."""

from __future__ import annotations

import asyncio
import logging
import uuid
from copy import deepcopy
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from . import logic
from .const import (
    CONF_ROOMS,
    DEFAULT_COMFORT_TEMP,
    DEFAULT_ECO_TEMP,
    DOMAIN,
    MAX_TEMP,
    MIN_TEMP,
    MODE_COMFORT,
    MODES,
    SIGNAL_UPDATE,
    STORAGE_VERSION,
)

_LOGGER = logging.getLogger(__name__)

BAD_STATES = (None, STATE_UNAVAILABLE, STATE_UNKNOWN)
EXTERNAL = "external"
# Aqara E1 verwirft die externe Temperatur, wenn sie nicht regelmäßig kommt.
EXTERNAL_PUSH_INTERVAL = timedelta(minutes=5)
# E1 übernimmt die Solltemperatur erst, wenn der Modus manual angekommen ist.
PRESET_SETTLE_SECONDS = 2

DEFAULT_WEEK = {
    **{d: [{"from": "06:00", "to": "08:00"}, {"from": "17:00", "to": "22:00"}] for d in logic.DAYS[:5]},
    **{d: [{"from": "08:00", "to": "22:30"}] for d in logic.DAYS[5:]},
}


def room_id_for(climate_entity_id: str) -> str:
    object_id = climate_entity_id.split(".", 1)[1]
    return object_id.removeprefix("thermostat_") or object_id


def parse_local(value: str | datetime) -> datetime:
    """Datum ohne Zeitzone gilt als Ortszeit von Home Assistant."""
    parsed = value if isinstance(value, datetime) else dt_util.parse_datetime(str(value))
    if parsed is None:
        raise ValueError(f"Ungültiges Datum: {value}")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt_util.get_default_time_zone())
    return dt_util.as_local(parsed)


def _clamp_temp(value: float) -> float:
    value = round(float(value) * 2) / 2
    if not MIN_TEMP <= value <= MAX_TEMP:
        raise ValueError(f"Temperatur muss zwischen {MIN_TEMP} und {MAX_TEMP} °C liegen")
    return value


class HeizplanManager:
    """Hält Pläne, Ausnahmen und Einstellungen und steuert die Thermostate."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}")
        self.data: dict[str, Any] = {}
        self._applied: dict[str, tuple[str, float]] = {}
        self._external: dict[str, dict[str, Any]] = {}
        self._unsub: CALLBACK_TYPE | None = None
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------ Räume

    @property
    def rooms(self) -> dict[str, dict[str, Any]]:
        """Raum-ID -> {id, name, climate, temp_sensor}."""
        source = self.entry.options if CONF_ROOMS in self.entry.options else self.entry.data
        return {room["id"]: room for room in source.get(CONF_ROOMS, [])}

    def _room_conf(self, room_id: str) -> dict[str, Any]:
        if room_id not in self.rooms:
            raise ValueError(f"Unbekannter Raum: {room_id}")
        return self.data["rooms"][room_id]

    def _thermostat_entity(self, climate_entity_id: str, domain: str, suffix: str) -> str | None:
        """Findet z. B. select.*_sensor am selben Gerät wie das Thermostat."""
        registry = er.async_get(self.hass)
        climate = registry.async_get(climate_entity_id)
        if climate and climate.device_id:
            for entry in er.async_entries_for_device(registry, climate.device_id):
                if entry.domain == domain and entry.entity_id.endswith(suffix):
                    return entry.entity_id
        guess = f"{domain}.{climate_entity_id.split('.', 1)[1]}{suffix}"
        return guess if self.hass.states.get(guess) else None

    # -------------------------------------------------------------- Speicher

    async def async_load(self) -> None:
        stored = await self._store.async_load() or {}
        self.data = {
            "settings": {
                "comfort_temp": DEFAULT_COMFORT_TEMP,
                "eco_temp": DEFAULT_ECO_TEMP,
                **stored.get("settings", {}),
            },
            "rooms": stored.get("rooms", {}),
            "exceptions": stored.get("exceptions", []),
        }
        for room_id in self.rooms:
            self.data["rooms"].setdefault(
                room_id, {"enabled": True, "week": deepcopy(DEFAULT_WEEK), "override": None}
            )

    def _save(self) -> None:
        self._store.async_delay_save(lambda: self.data, 1)

    # -------------------------------------------------------------- Abfragen

    def temperature_for(self, mode: str) -> float:
        settings = self.data["settings"]
        return settings["comfort_temp"] if mode == MODE_COMFORT else settings["eco_temp"]

    def _parsed_exceptions(self) -> list[dict[str, Any]]:
        return [
            {**exc, "start": parse_local(exc["start"]), "end": parse_local(exc["end"])}
            for exc in self.data["exceptions"]
        ]

    def room_status(self, room_id: str, now: datetime | None = None) -> dict[str, Any]:
        now = now or dt_util.now()
        conf = self.data["rooms"][room_id]
        exceptions = self._parsed_exceptions()
        mode, exc = logic.desired_mode(conf["week"], exceptions, room_id, now)
        override = conf.get("override")
        # Bei pausiertem Plan gibt es keinen Wechsel, an dem die manuelle Temperatur enden könnte.
        if override and conf["enabled"] and override["base_mode"] != mode:
            override = None
        upcoming = logic.next_change(conf["week"], exceptions, room_id, now)
        stored_exc = next((e for e in self.data["exceptions"] if exc and e["id"] == exc["id"]), None)
        external = self._external.get(room_id, {})
        return {
            "enabled": conf["enabled"],
            "mode": mode,
            "temperature": override["temperature"] if override else self.temperature_for(mode),
            "source": "override" if override else ("exception" if exc else "plan"),
            "exception": stored_exc,
            "next_change": upcoming[0].isoformat() if upcoming else None,
            "next_mode": upcoming[1] if upcoming else None,
            "next_temperature": self.temperature_for(upcoming[1]) if upcoming else None,
            "sensor_resets": external.get("resets", 0),
            "last_sensor_reset": external.get("last_reset"),
        }

    def as_dict(self) -> dict[str, Any]:
        now = dt_util.now()
        return {
            "settings": dict(self.data["settings"]),
            "rooms": [
                {**room, "week": self.data["rooms"][room_id]["week"], **self.room_status(room_id, now)}
                for room_id, room in self.rooms.items()
            ],
            "exceptions": sorted(self.data["exceptions"], key=lambda e: parse_local(e["start"])),
        }

    # ------------------------------------------------------------- Änderungen

    async def async_set_week(self, room_id: str, week: dict[str, Any]) -> None:
        self._room_conf(room_id)["week"] = logic.normalize_week(week)
        self._save()
        await self.async_evaluate()

    async def async_set_enabled(self, room_id: str, enabled: bool) -> None:
        conf = self._room_conf(room_id)
        conf["enabled"] = enabled
        conf["override"] = None
        self._applied.pop(room_id, None)
        self._save()
        await self.async_evaluate()

    async def async_set_override(self, room_id: str, temperature: float) -> None:
        """Setzt eine manuelle Temperatur, die bis zum nächsten Planwechsel gilt."""
        conf = self._room_conf(room_id)
        now = dt_util.now()
        exceptions = self._parsed_exceptions()
        mode, _ = logic.desired_mode(conf["week"], exceptions, room_id, now)
        conf["override"] = {"temperature": _clamp_temp(temperature), "base_mode": mode}
        self._applied.pop(room_id, None)
        self._save()
        await self.async_evaluate()

    async def async_clear_override(self, room_id: str) -> None:
        conf = self._room_conf(room_id)
        if conf.get("override") is None:
            return
        conf["override"] = None
        self._applied.pop(room_id, None)
        self._save()
        await self.async_evaluate()

    async def async_set_settings(
        self, comfort_temp: float | None = None, eco_temp: float | None = None
    ) -> None:
        settings = self.data["settings"]
        if comfort_temp is not None:
            settings["comfort_temp"] = _clamp_temp(comfort_temp)
        if eco_temp is not None:
            settings["eco_temp"] = _clamp_temp(eco_temp)
        self._save()
        await self.async_evaluate()

    async def async_add_exception(
        self, rooms: list[str], start: str | datetime, end: str | datetime, mode: str, note: str = ""
    ) -> dict[str, Any]:
        room_ids = list(self.rooms) if "all" in rooms else list(dict.fromkeys(rooms))
        if not room_ids:
            raise ValueError("Bitte mindestens einen Raum wählen")
        for room_id in room_ids:
            self._room_conf(room_id)
        if mode not in MODES:
            raise ValueError(f"Unbekannter Modus: {mode}")
        start_dt, end_dt = parse_local(start), parse_local(end)
        if end_dt <= start_dt:
            raise ValueError("Das Ende muss nach dem Beginn liegen")
        if end_dt <= dt_util.now():
            raise ValueError("Die Ausnahme liegt komplett in der Vergangenheit")
        exc = {
            "id": uuid.uuid4().hex,
            "rooms": room_ids,
            "start": start_dt.isoformat(),
            "end": end_dt.isoformat(),
            "mode": mode,
            "note": note.strip(),
        }
        self.data["exceptions"].append(exc)
        self._save()
        # Auch wenn der Modus gleich bleibt: Thermostat neu setzen (z. B. nach Handverstellung).
        await self.async_evaluate(force_rooms=room_ids if start_dt <= dt_util.now() else ())
        return exc

    async def async_delete_exception(self, exception_id: str, room_id: str | None = None) -> None:
        """Löscht eine Ausnahme – oder nimmt nur einen Raum aus ihr heraus."""
        exc = next((e for e in self.data["exceptions"] if e["id"] == exception_id), None)
        if exc is None:
            raise ValueError("Ausnahme nicht gefunden")
        if room_id and len(exc["rooms"]) > 1:
            exc["rooms"] = [r for r in exc["rooms"] if r != room_id]
            affected = [room_id]
        else:
            self.data["exceptions"].remove(exc)
            affected = exc["rooms"]
        self._save()
        await self.async_evaluate(force_rooms=affected)

    # --------------------------------------------------------------- Steuerung

    async def async_start(self) -> None:
        self._unsub = async_track_time_change(self.hass, self._async_tick, second=0)
        await self.async_evaluate()

    def async_stop(self) -> None:
        if self._unsub:
            self._unsub()
            self._unsub = None

    async def _async_tick(self, _now: datetime) -> None:
        await self.async_evaluate()

    async def async_evaluate(self, force_rooms: list[str] | tuple[str, ...] = ()) -> None:
        async with self._lock:
            now = dt_util.now()
            self._prune(now)
            exceptions = self._parsed_exceptions()
            for room_id, room in self.rooms.items():
                if room.get("temp_sensor"):
                    await self._async_check_external_sensor(room_id, room, now)
                conf = self.data["rooms"][room_id]
                if room_id in force_rooms:
                    self._applied.pop(room_id, None)
                override = conf.get("override")
                if not conf["enabled"]:
                    # Plan pausiert: nur eine manuell gesetzte Temperatur wird gehalten, sonst
                    # bleibt das Thermostat komplett in Handsteuerung. Es gibt keinen Planwechsel,
                    # der die manuelle Temperatur wieder beenden könnte.
                    if override is None:
                        self._applied.pop(room_id, None)
                        continue
                    target = ("override", override["temperature"])
                else:
                    mode, _ = logic.desired_mode(conf["week"], exceptions, room_id, now)
                    if override and override["base_mode"] != mode:
                        # Der Plan ist inzwischen weitergesprungen: manuelle Temperatur endet hier.
                        conf["override"] = None
                        override = None
                        self._save()
                    target = ("override", override["temperature"]) if override else (mode, self.temperature_for(mode))
                # Nur bei Wechsel setzen: Handverstellung am Thermostat bleibt bis zum nächsten Wechsel.
                if self._applied.get(room_id) == target:
                    continue
                if await self._async_apply(room["climate"], target[1]):
                    self._applied[room_id] = target
        async_dispatcher_send(self.hass, SIGNAL_UPDATE)

    def _prune(self, now: datetime) -> None:
        remaining = [e for e in self.data["exceptions"] if parse_local(e["end"]) > now]
        if len(remaining) != len(self.data["exceptions"]):
            self.data["exceptions"] = remaining
            self._save()

    async def _async_apply(self, entity_id: str, temperature: float) -> bool:
        state = self.hass.states.get(entity_id)
        if state is None or state.state in BAD_STATES:
            _LOGGER.debug("%s nicht verfügbar, versuche es später erneut", entity_id)
            return False
        if state.state == "off":
            _LOGGER.debug("%s ist ausgeschaltet, wird nicht gesteuert", entity_id)
            return False
        try:
            presets = state.attributes.get("preset_modes") or []
            if "manual" in presets and state.attributes.get("preset_mode") != "manual":
                await self.hass.services.async_call(
                    "climate", "set_preset_mode",
                    {ATTR_ENTITY_ID: entity_id, "preset_mode": "manual"}, blocking=True,
                )
                await asyncio.sleep(PRESET_SETTLE_SECONDS)
            await self.hass.services.async_call(
                "climate", "set_temperature",
                {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: temperature}, blocking=True,
            )
        except HomeAssistantError as err:
            _LOGGER.warning("Konnte %s nicht auf %s °C setzen: %s", entity_id, temperature, err)
            return False
        _LOGGER.info("%s auf %s °C gesetzt", entity_id, temperature)
        return True

    async def _async_check_external_sensor(
        self, room_id: str, room: dict[str, Any], now: datetime
    ) -> None:
        """Aqara-Bug: Das E1 springt gelegentlich von 'external' auf 'internal' zurück."""
        info = self._external.setdefault(room_id, {"resets": 0})
        climate = room["climate"]
        select_id = self._thermostat_entity(climate, "select", "_sensor")
        number_id = self._thermostat_entity(climate, "number", "_external_temperature_input")
        if not select_id or not number_id:
            if not info.get("warned"):
                _LOGGER.warning("Keine Sensor-Auswahl/externe Temperatur für %s gefunden", climate)
                info["warned"] = True
            return

        select_state = self.hass.states.get(select_id)
        if select_state is None or select_state.state in BAD_STATES:
            return
        forced = False
        try:
            if select_state.state != EXTERNAL:
                _LOGGER.warning(
                    "%s stand auf '%s' – stelle zurück auf 'external'", select_id, select_state.state
                )
                await self.hass.services.async_call(
                    "select", "select_option",
                    {ATTR_ENTITY_ID: select_id, "option": EXTERNAL}, blocking=True,
                )
                info["resets"] += 1
                info["last_reset"] = now.isoformat()
                forced = True

            sensor_state = self.hass.states.get(room["temp_sensor"])
            if sensor_state is None or sensor_state.state in BAD_STATES:
                return
            value = round(float(sensor_state.state), 1)
            last_push = info.get("pushed_at")
            if (
                forced
                or value != info.get("value")
                or last_push is None
                or now - last_push >= EXTERNAL_PUSH_INTERVAL
            ):
                await self.hass.services.async_call(
                    "number", "set_value",
                    {ATTR_ENTITY_ID: number_id, "value": value}, blocking=True,
                )
                info["value"] = value
                info["pushed_at"] = now
        except (HomeAssistantError, ValueError) as err:
            _LOGGER.warning("Externe Temperatur für %s fehlgeschlagen: %s", climate, err)
