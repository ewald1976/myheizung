"""Schalter pro Raum: Plan aktiv/pausiert."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import HeizplanEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    manager = entry.runtime_data
    async_add_entities(HeizplanRoomSwitch(manager, room) for room in manager.rooms.values())


class HeizplanRoomSwitch(HeizplanEntity, SwitchEntity):
    _attr_icon = "mdi:calendar-check"

    def __init__(self, manager, room: dict[str, Any]) -> None:
        super().__init__(manager)
        self._room_id = room["id"]
        self._attr_unique_id = f"{manager.entry.entry_id}_{room['id']}_enabled"
        self._attr_name = f"Heizplan {room['name']} aktiv"

    @property
    def is_on(self) -> bool:
        return self.manager.data["rooms"][self._room_id]["enabled"]

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.manager.async_set_enabled(self._room_id, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.manager.async_set_enabled(self._room_id, False)
