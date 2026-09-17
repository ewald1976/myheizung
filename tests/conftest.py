from unittest.mock import AsyncMock, patch

import pytest

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture(autouse=True)
def no_frontend():
    """Das Frontend-Paket (hass_frontend) ist in der Testumgebung nicht installiert."""
    with (
        patch("homeassistant.components.frontend.async_setup", AsyncMock(return_value=True)),
        patch("custom_components.heizplan.add_extra_js_url") as add_js,
        patch("custom_components.heizplan.manager.PRESET_SETTLE_SECONDS", 0),
    ):
        yield add_js
