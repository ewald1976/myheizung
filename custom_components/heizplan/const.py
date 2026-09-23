"""Konstanten für Heizplan."""

from .logic import MODE_COMFORT, MODE_ECO, MODES  # noqa: F401

DOMAIN = "heizplan"
VERSION = "0.4.1"

CONF_CLIMATES = "climates"
CONF_ROOMS = "rooms"

DEFAULT_COMFORT_TEMP = 23.0
DEFAULT_ECO_TEMP = 18.0
MIN_TEMP = 5.0
MAX_TEMP = 30.0

STORAGE_VERSION = 1
SIGNAL_UPDATE = f"{DOMAIN}_update"
FRONTEND_URL = "/heizplan_static"
