"""Base class for all Uiprotectalarms devices."""
import threading
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyuiprotectalarms import PyUIProtectAlarms

_LOGGER = logging.getLogger(__name__)

class UnknownProductError(Exception):
    """Exception thrown when we don't recognize a product of a device."""

class UnknownModelError(Exception):
    """Exception thrown when we don't recognize a model of a device."""

class PyUIProtectBaseObject(object):
    """Base class for all Unifi Protect devices."""
    
    def __init__(
        self,
        details: dict[str, list],
        uiProtectAlarms: "PyUIProtectAlarms",
    ):
        """Initialize the Uiprotectalarms device."""

        self._uiProtectAlarms = uiProtectAlarms
        self._is_on = False

        self._feature_key_names: dict[str, str] = {}

        self.raw_state = None
        self._attr_cbs = []
        self._lock = threading.Lock()

    def __repr__(self):
        # Representation string of object.
        return f"<{self.__class__.__name__}>"

    def handle_server_update_base(self, details: dict):
        """Initial method called when we do a refrehs"""

        # This method exists so that we can run the polymorphic function to process updates, and then
        # run a _do_callbacks() command safely afterwards.
        self.handle_server_update(details)
        self._do_callbacks()

    def handle_server_update(self, details: dict):
        """Method to process an update"""
        self.update_state(details)

    def update_state(self, state: dict):
        """Process the state dictionary from the REST API."""

    def add_attr_callback(self, cb):
        """Add a callback to be called by _do_callbacks."""
        self._attr_cbs.append(cb)

    def _do_callbacks(self):
        """Run all registered callback"""
        cbs = []
        with self._lock:
            for cb in self._attr_cbs:
                cbs.append(cb)
        for cb in cbs:
            _LOGGER.debug("Running callback %s", cb)
            cb()