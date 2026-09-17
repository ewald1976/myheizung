"""Heizplan: Wochenpläne und Ausnahmen für Thermostate – bedienbar über eine Karte."""

from __future__ import annotations

from pathlib import Path

import voluptuous as vol

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.typing import ConfigType

from . import websocket
from .const import DOMAIN, FRONTEND_URL, MODES, VERSION
from .manager import HeizplanManager

PLATFORMS = [Platform.SENSOR, Platform.SWITCH, Platform.NUMBER]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

ADD_EXCEPTION_SCHEMA = vol.Schema(
    {
        vol.Required("rooms"): vol.All(cv.ensure_list, [cv.string]),
        vol.Required("start"): cv.string,
        vol.Required("end"): cv.string,
        vol.Required("mode"): vol.In(MODES),
        vol.Optional("note", default=""): cv.string,
    }
)
DELETE_EXCEPTION_SCHEMA = vol.Schema(
    {vol.Required("exception_id"): cv.string, vol.Optional("room_id"): cv.string}
)


def _manager(hass: HomeAssistant) -> HeizplanManager:
    manager = hass.data.get(DOMAIN)
    if manager is None:
        raise HomeAssistantError("Heizplan ist nicht eingerichtet")
    return manager


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    await hass.http.async_register_static_paths(
        [StaticPathConfig(FRONTEND_URL, str(Path(__file__).parent / "frontend"), False)]
    )
    add_extra_js_url(hass, f"{FRONTEND_URL}/heizplan-card.js?v={VERSION}")
    websocket.async_register(hass)

    async def add_exception(call: ServiceCall) -> None:
        try:
            await _manager(hass).async_add_exception(**call.data)
        except ValueError as err:
            raise ServiceValidationError(str(err)) from err

    async def delete_exception(call: ServiceCall) -> None:
        try:
            await _manager(hass).async_delete_exception(**call.data)
        except ValueError as err:
            raise ServiceValidationError(str(err)) from err

    hass.services.async_register(DOMAIN, "add_exception", add_exception, ADD_EXCEPTION_SCHEMA)
    hass.services.async_register(DOMAIN, "delete_exception", delete_exception, DELETE_EXCEPTION_SCHEMA)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    manager = HeizplanManager(hass, entry)
    await manager.async_load()
    entry.runtime_data = manager
    hass.data[DOMAIN] = manager

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    entry.async_on_unload(manager.async_stop)

    async def _start(_hass: HomeAssistant) -> None:
        await manager.async_start()

    entry.async_on_unload(async_at_started(hass, _start))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data.pop(DOMAIN, None)
    return unloaded


async def _async_reload(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
