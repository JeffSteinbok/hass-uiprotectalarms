"""Uiprotectalarms API for controling fans."""

import logging
from typing import TYPE_CHECKING

from .constants import (
        UIProtectApi
)

from .pyuiprotectbaseobject import PyUIProtectBaseObject

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from pyuiprotectalarms import PyUIProtectAlarms


class PyUIProtectAutomation(PyUIProtectBaseObject):
    """Class to represent a Unifi Protect Alarm Automation."""

    def __init__(self, details: dict[str, list], PyUIProtectAlarms: "PyUIProtectAlarms"):
        super().__init__(details, PyUIProtectAlarms)

        self._name : str = None
        self._enabled : bool = None
        self._id : str = None
        self._raw_details : dict = None

        self.update_state(details)

    def __repr__(self):
        # Representation string of object.
        return f"<{self.__class__.__name__}:{self._id}:{self._name}>"
    
    @property
    def name(self) -> str:
        return self._name

    @property
    def enabled(self) -> bool:
        return self._enabled
    
    @enabled.setter
    def enabled(self, value: bool):
        """Enable or disable the automation."""

        # If the automation is disabled, add (Disabled) to the name, and remove it if enabled.
        if (value is True):
            if (self._name.endswith(" (Disabled)")):
                self._raw_details["name"] = self._name[:-11]
                self._name = self._name[:-11]
        else:
            if (not self._name.endswith(" (Disabled)")):
                self._raw_details["name"] = self._name + " (Disabled)"
                self._name = self._name + " (Disabled)"

        self._raw_details["enable"] = value
        self._enabled = value
        
        response, status_code = self._uiProtectAlarms.call_uiprotect_api(UIProtectApi.UPDATE_AUTOMATION, self._id, self._raw_details)
        if (status_code == 200 and response):
            self.handle_server_update_base(response)

    @property
    def id(self):
        """Return the id of the device."""
        return self._id

    @property
    def raw_details(self):
        """Return the raw details of the device."""
        return self._raw_details

    def update_state(self, state: dict):
        _LOGGER.debug("PyUIProtectAutomation:update_state: %s", state.get("id"))
        super().update_state(state)

        self._raw_details = state
        self._id = state.get("id")
        self._enabled = state.get("enable")
        self._name = state.get("name")