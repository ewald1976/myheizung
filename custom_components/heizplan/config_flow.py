"""Einrichtung von Heizplan: Thermostate wählen, dann pro Raum das Hygrometer."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.selector import EntitySelector, EntitySelectorConfig

from .const import CONF_CLIMATES, CONF_ROOMS, DOMAIN
from .manager import room_id_for

CLIMATE_SELECTOR = EntitySelector(EntitySelectorConfig(domain="climate", multiple=True))
SENSOR_SELECTOR = EntitySelector(EntitySelectorConfig(domain="sensor", device_class="temperature"))


def _room_name(hass: HomeAssistant, entity_id: str) -> str:
    state = hass.states.get(entity_id)
    name = state.name if state else entity_id.split(".", 1)[1]
    return name.removeprefix("Thermostat ").strip() or name


def _sensor_schema(hass: HomeAssistant, climates: list[str], existing: dict[str, dict]) -> vol.Schema:
    fields: dict[Any, Any] = {}
    for entity_id in climates:
        current = existing.get(entity_id, {}).get("temp_sensor")
        key = vol.Optional(entity_id, description={"suggested_value": current})
        fields[key] = SENSOR_SELECTOR
    return vol.Schema(fields)


def _build_rooms(
    hass: HomeAssistant, climates: list[str], sensors: dict[str, Any], existing: dict[str, dict]
) -> list[dict[str, Any]]:
    rooms = []
    for entity_id in climates:
        rooms.append(
            {
                "id": room_id_for(entity_id),
                "name": existing.get(entity_id, {}).get("name") or _room_name(hass, entity_id),
                "climate": entity_id,
                "temp_sensor": sensors.get(entity_id) or None,
            }
        )
    return rooms


class HeizplanConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._climates: list[str] = []

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        if user_input is not None:
            self._climates = user_input[CONF_CLIMATES]
            return await self.async_step_sensors()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_CLIMATES): CLIMATE_SELECTOR}),
        )

    async def async_step_sensors(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            rooms = _build_rooms(self.hass, self._climates, user_input, {})
            return self.async_create_entry(title="Heizplan", data={CONF_ROOMS: rooms})
        return self.async_show_form(
            step_id="sensors", data_schema=_sensor_schema(self.hass, self._climates, {})
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return HeizplanOptionsFlow()


class HeizplanOptionsFlow(OptionsFlow):
    def __init__(self) -> None:
        self._climates: list[str] = []

    @property
    def _existing(self) -> dict[str, dict]:
        entry = self.config_entry
        source = entry.options if CONF_ROOMS in entry.options else entry.data
        return {room["climate"]: room for room in source.get(CONF_ROOMS, [])}

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            self._climates = user_input[CONF_CLIMATES]
            return await self.async_step_sensors()
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {vol.Required(CONF_CLIMATES, default=list(self._existing)): CLIMATE_SELECTOR}
            ),
        )

    async def async_step_sensors(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            rooms = _build_rooms(self.hass, self._climates, user_input, self._existing)
            return self.async_create_entry(data={CONF_ROOMS: rooms})
        return self.async_show_form(
            step_id="sensors", data_schema=_sensor_schema(self.hass, self._climates, self._existing)
        )
