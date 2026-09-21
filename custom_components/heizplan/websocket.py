"""WebSocket-API für die Heizplan-Karte."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN, MODES, SIGNAL_UPDATE

BLOCK = vol.Schema({vol.Required("from"): str, vol.Required("to"): str})


@callback
def async_register(hass: HomeAssistant) -> None:
    for command in (
        ws_get,
        ws_subscribe,
        ws_set_week,
        ws_set_enabled,
        ws_set_settings,
        ws_add_exception,
        ws_delete_exception,
        ws_set_override,
        ws_clear_override,
    ):
        websocket_api.async_register_command(hass, command)


def _manager(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]):
    manager = hass.data.get(DOMAIN)
    if manager is None:
        connection.send_error(msg["id"], "not_loaded", "Heizplan ist nicht eingerichtet")
    return manager


async def _run(hass, connection, msg, action) -> None:
    manager = _manager(hass, connection, msg)
    if manager is None:
        return
    try:
        await action(manager)
    except ValueError as err:
        connection.send_error(msg["id"], "invalid", str(err))
        return
    connection.send_result(msg["id"])


@websocket_api.websocket_command({vol.Required("type"): "heizplan/get"})
@callback
def ws_get(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    if manager := _manager(hass, connection, msg):
        connection.send_result(msg["id"], manager.as_dict())


@websocket_api.websocket_command({vol.Required("type"): "heizplan/subscribe"})
@callback
def ws_subscribe(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    if _manager(hass, connection, msg) is None:
        return

    @callback
    def forward() -> None:
        # Nach einem Neuladen der Integration gibt es einen neuen Manager.
        if manager := hass.data.get(DOMAIN):
            connection.send_message(websocket_api.event_message(msg["id"], manager.as_dict()))

    connection.subscriptions[msg["id"]] = async_dispatcher_connect(hass, SIGNAL_UPDATE, forward)
    connection.send_result(msg["id"])
    forward()


@websocket_api.websocket_command(
    {
        vol.Required("type"): "heizplan/set_week",
        vol.Required("room_id"): str,
        vol.Required("week"): {str: [BLOCK]},
    }
)
@websocket_api.async_response
async def ws_set_week(hass, connection, msg) -> None:
    await _run(hass, connection, msg, lambda m: m.async_set_week(msg["room_id"], msg["week"]))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "heizplan/set_enabled",
        vol.Required("room_id"): str,
        vol.Required("enabled"): bool,
    }
)
@websocket_api.async_response
async def ws_set_enabled(hass, connection, msg) -> None:
    await _run(hass, connection, msg, lambda m: m.async_set_enabled(msg["room_id"], msg["enabled"]))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "heizplan/set_settings",
        vol.Optional("comfort_temp"): vol.Coerce(float),
        vol.Optional("eco_temp"): vol.Coerce(float),
    }
)
@websocket_api.async_response
async def ws_set_settings(hass, connection, msg) -> None:
    await _run(
        hass, connection, msg,
        lambda m: m.async_set_settings(msg.get("comfort_temp"), msg.get("eco_temp")),
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "heizplan/add_exception",
        vol.Required("rooms"): [str],
        vol.Required("start"): str,
        vol.Required("end"): str,
        vol.Required("mode"): vol.In(MODES),
        vol.Optional("note", default=""): str,
    }
)
@websocket_api.async_response
async def ws_add_exception(hass, connection, msg) -> None:
    await _run(
        hass, connection, msg,
        lambda m: m.async_add_exception(msg["rooms"], msg["start"], msg["end"], msg["mode"], msg["note"]),
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "heizplan/delete_exception",
        vol.Required("exception_id"): str,
        vol.Optional("room_id"): str,
    }
)
@websocket_api.async_response
async def ws_delete_exception(hass, connection, msg) -> None:
    await _run(
        hass, connection, msg,
        lambda m: m.async_delete_exception(msg["exception_id"], msg.get("room_id")),
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "heizplan/set_override",
        vol.Required("room_id"): str,
        vol.Required("temperature"): vol.Coerce(float),
    }
)
@websocket_api.async_response
async def ws_set_override(hass, connection, msg) -> None:
    await _run(hass, connection, msg, lambda m: m.async_set_override(msg["room_id"], msg["temperature"]))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "heizplan/clear_override",
        vol.Required("room_id"): str,
    }
)
@websocket_api.async_response
async def ws_clear_override(hass, connection, msg) -> None:
    await _run(hass, connection, msg, lambda m: m.async_clear_override(msg["room_id"]))
