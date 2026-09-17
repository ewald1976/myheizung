"""Globale Temperaturen für Warm und Nacht."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import MAX_TEMP, MIN_TEMP
from .entity import HeizplanEntity, hub_device


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    manager = entry.runtime_data
    async_add_entities(
        [
            HeizplanTemperature(manager, "comfort_temp", "Warm-Temperatur", "mdi:fire"),
            HeizplanTemperature(manager, "eco_temp", "Nacht-Temperatur", "mdi:weather-night"),
        ]
    )


class HeizplanTemperature(HeizplanEntity, NumberEntity):
    _attr_native_min_value = MIN_TEMP
    _attr_native_max_value = MAX_TEMP
    _attr_native_step = 0.5
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_mode = NumberMode.BOX

    def __init__(self, manager, key: str, name: str, icon: str) -> None:
        super().__init__(manager, hub_device(manager))
        self._key = key
        self._attr_unique_id = f"{manager.entry.entry_id}_{key}"
        self._attr_name = name
        self._attr_icon = icon

    @property
    def native_value(self) -> float:
        return self.manager.data["settings"][self._key]

    async def async_set_native_value(self, value: float) -> None:
        await self.manager.async_set_settings(**{self._key: value})
