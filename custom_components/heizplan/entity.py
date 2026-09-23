"""Gemeinsame Basis für Heizplan-Entities."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, SIGNAL_UPDATE, VERSION
from .manager import HeizplanManager


def hub_device(manager: HeizplanManager) -> DeviceInfo:
    """Ein Gerät für die Einstellungen, die für alle Räume gelten."""
    return DeviceInfo(
        identifiers={(DOMAIN, manager.entry.entry_id)},
        name="Heizplan",
        entry_type=DeviceEntryType.SERVICE,
        sw_version=VERSION,
    )


def room_device(manager: HeizplanManager, room: dict[str, Any]) -> DeviceInfo:
    """Pro Raum ein eigenes Gerät, damit es einem Bereich zugeordnet werden kann."""
    if manager.hub_device_id is None:
        raise RuntimeError("Heizplan-Hubgerät wurde noch nicht registriert")
    return DeviceInfo(
        identifiers={(DOMAIN, f"{manager.entry.entry_id}_{room['id']}")},
        name=f"Heizplan {room['name']}",
        entry_type=DeviceEntryType.SERVICE,
        sw_version=VERSION,
        via_device_id=manager.hub_device_id,
    )


class HeizplanEntity(Entity):
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, manager: HeizplanManager, device: DeviceInfo) -> None:
        self.manager = manager
        self._attr_device_info = device

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_UPDATE, self.async_write_ha_state)
        )
