"""Integrationstests mit einer Test-Instanz von Home Assistant (pytest-homeassistant-custom-component)."""

from datetime import timedelta

import pytest
from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_mock_service,
)

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from custom_components.heizplan.const import CONF_ROOMS, DOMAIN

ROOMS = [
    {"id": "buro", "name": "Büro", "climate": "climate.thermostat_buro", "temp_sensor": "sensor.zb_temperatur"},
    {"id": "wohnzimmer", "name": "Wohnzimmer", "climate": "climate.thermostat_wohnzimmer", "temp_sensor": None},
]


@pytest.fixture
async def setup(hass: HomeAssistant, freezer: FrozenDateTimeFactory):
    await hass.config.async_set_time_zone("Europe/Berlin")
    freezer.move_to("2026-09-14 07:00:00+02:00")  # Montag
    for room in ROOMS:
        hass.states.async_set(
            room["climate"], "heat",
            {"preset_mode": "auto", "preset_modes": ["manual", "away", "auto"], "temperature": 21},
        )
    hass.states.async_set("select.thermostat_buro_sensor", "internal")
    hass.states.async_set("number.thermostat_buro_external_temperature_input", "20")
    hass.states.async_set("sensor.zb_temperatur", "21.34")
    calls = {
        "preset": async_mock_service(hass, "climate", "set_preset_mode"),
        "temp": async_mock_service(hass, "climate", "set_temperature"),
        "select": async_mock_service(hass, "select", "select_option"),
        "number": async_mock_service(hass, "number", "set_value"),
    }
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_ROOMS: ROOMS}, unique_id=DOMAIN)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    return entry, calls


def _temps(calls):
    return {c.data["entity_id"]: c.data["temperature"] for c in calls["temp"]}


async def test_start_applies_plan_and_fixes_sensor(hass, setup):
    _, calls = setup
    # Standardplan Mo 06–08 warm -> 23 °C, vorher Preset auf manual
    assert _temps(calls) == {"climate.thermostat_buro": 23.0, "climate.thermostat_wohnzimmer": 23.0}
    assert {c.data["preset_mode"] for c in calls["preset"]} == {"manual"}
    assert [c.data for c in calls["select"]] == [
        {"entity_id": "select.thermostat_buro_sensor", "option": "external"}
    ]
    state = hass.states.get("sensor.heizplan_buro")
    assert float(state.state) == 23.0
    assert state.attributes["sensor_resets"] == 1
    assert state.attributes["next_mode"] == "eco"


async def test_pushes_external_temperature(hass, setup, freezer):
    _, calls = setup
    # Die Number-Plattform von Heizplan ersetzt den Mock – daher hier neu mocken.
    number_calls = async_mock_service(hass, "number", "set_value")
    hass.states.async_set("select.thermostat_buro_sensor", "external")
    hass.states.async_set("sensor.zb_temperatur", "21.86")
    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert [c.data for c in number_calls] == [
        {"entity_id": "number.thermostat_buro_external_temperature_input", "value": 21.9}
    ]
    # Unveränderter Wert: erst nach 5 Minuten erneut senden
    for _ in range(5):
        freezer.tick(timedelta(minutes=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
    assert len(number_calls) == 2


async def test_switches_at_block_end_only_once(hass, setup, freezer):
    _, calls = setup
    calls["temp"].clear()
    hass.states.async_set("select.thermostat_buro_sensor", "external")
    for minute in range(58, 63):
        freezer.move_to(dt_util.parse_datetime(f"2026-09-14 07:{minute % 60:02d}:00+02:00") + timedelta(hours=minute // 60))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
    assert [c.data["temperature"] for c in calls["temp"]] == [18.0, 18.0]  # beide Räume je einmal


async def test_websocket_exception_and_settings(hass, setup, hass_ws_client):
    _, calls = setup
    client = await hass_ws_client(hass)
    calls["temp"].clear()

    await client.send_json_auto_id({"type": "heizplan/set_settings", "eco_temp": 17, "comfort_temp": 22.5})
    assert (await client.receive_json())["success"]
    await hass.async_block_till_done(wait_background_tasks=True)
    assert set(_temps(calls).values()) == {22.5}

    calls["temp"].clear()
    await client.send_json_auto_id(
        {"type": "heizplan/add_exception", "rooms": ["buro"], "start": "2026-09-14T06:30",
         "end": "2026-09-14T12:00", "mode": "eco", "note": "Homeoffice"}
    )
    assert (await client.receive_json())["success"]
    await hass.async_block_till_done(wait_background_tasks=True)
    assert _temps(calls) == {"climate.thermostat_buro": 17.0}

    await client.send_json_auto_id({"type": "heizplan/get"})
    data = (await client.receive_json())["result"]
    buro = next(r for r in data["rooms"] if r["id"] == "buro")
    assert buro["source"] == "exception" and buro["temperature"] == 17.0
    assert buro["next_change"].startswith("2026-09-14T17:00")  # nach Ausnahme-Ende gilt ohnehin Nacht

    calls["temp"].clear()
    await client.send_json_auto_id(
        {"type": "heizplan/delete_exception", "exception_id": data["exceptions"][0]["id"], "room_id": "buro"}
    )
    assert (await client.receive_json())["success"]
    await hass.async_block_till_done(wait_background_tasks=True)
    assert _temps(calls) == {"climate.thermostat_buro": 22.5}

    await client.send_json_auto_id(
        {"type": "heizplan/set_week", "room_id": "buro", "week": {"mon": [{"from": "09:00", "to": "08:00"}]}}
    )
    assert (await client.receive_json())["error"]["code"] == "invalid"


async def test_disabled_room_is_not_touched(hass, setup):
    _, calls = setup
    calls["temp"].clear()
    await hass.services.async_call("switch", "turn_off", {"entity_id": "switch.heizplan_wohnzimmer_aktiv"}, blocking=True)
    await hass.services.async_call("number", "set_value", {"entity_id": "number.heizplan_warm_temperatur", "value": 24}, blocking=True)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert _temps(calls) == {"climate.thermostat_buro": 24.0}
