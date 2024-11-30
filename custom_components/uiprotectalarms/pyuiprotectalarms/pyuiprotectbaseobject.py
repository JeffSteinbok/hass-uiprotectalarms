"""Base class for all Uiprotectalarms devices."""
import threading
import logging
from typing import Dict
from typing import TYPE_CHECKING
from .constants import LOGGER_NAME

if TYPE_CHECKING:
    from PyUIProtectAlarms import PyUIProtectAlarms

_LOGGER = logging.getLogger(LOGGER_NAME)

class UnknownProductError(Exception):
    """Exception thrown when we don't recognize a product of a device."""

class UnknownModelError(Exception):
    """Exception thrown when we don't recognize a model of a device."""

class PyUIProtectBaseObject(object):
    def __init__(
        self,
        details: Dict[str, list],
        uiProtectAlarms: "PyUIProtectAlarms",
    ):

        self._uiProtectAlarms = uiProtectAlarms
        self._is_on = False

        self._feature_key_names: Dict[str, str] = {}

        self.raw_state = None
        self._attr_cbs = []
        self._lock = threading.Lock()

    def __repr__(self):
        # Representation string of object.
        return f"<{self.__class__.__name__}>"

    def update_state(self, state: dict):
        """Process the state dictionary from the REST API."""
