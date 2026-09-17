"""Sensor pro Raum: aktuelle Solltemperatur laut Plan."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import HeizplanEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    manager = entry.runtime_data
    async_add_entities(HeizplanRoomSensor(manager, room) for room in manager.rooms.values())


class HeizplanRoomSensor(HeizplanEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, manager, room: dict[str, Any]) -> None:
        super().__init__(manager)
        self._room_id = room["id"]
        self._room = room
        self._attr_unique_id = f"{manager.entry.entry_id}_{room['id']}_target"
        self._attr_name = f"Heizplan {room['name']}"

    @property
    def native_value(self) -> float:
        return self.manager.room_status(self._room_id)["temperature"]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        status = self.manager.room_status(self._room_id)
        status.pop("temperature")
        return {
            **status,
            "room_id": self._room_id,
            "climate_entity": self._room["climate"],
            "temp_sensor": self._room.get("temp_sensor"),
        }
