"""Uiprotectalarms API for controling fans."""

import logging
from typing import TYPE_CHECKING, Dict

from .constants import (
        LOGGER_NAME,
        UIProtectApi
)

from .pyuiprotectbaseobject import PyUIProtectBaseObject

_LOGGER = logging.getLogger(LOGGER_NAME)

if TYPE_CHECKING:
    from PyUIProtectAlarms import PyUIProtectAlarms


class PyUIProtectAutomation(PyUIProtectBaseObject):

    def __init__(self, details: Dict[str, list], PyUIProtectAlarms: "PyUIProtectAlarms"):
        super().__init__(details, PyUIProtectAlarms)

        self._name = None
        self._enabled = None
        self._id = None
        self._raw_details = None

        self.update_state(details)

    def __repr__(self):
        # Representation string of object.
        return f"<{self.__class__.__name__}:{self._id}:{self._name}>"
    
    @property
    def name(self):
        return self._name

    @property
    def enabled(self):
        return self._enabled
    
    @enabled.setter
    def enabled(self, value: bool):
        self._raw_details["enable"] = value
        response, status_code = self._uiProtectAlarms.call_uiprotect_api(UIProtectApi.UPDATE_AUTOMATION, self._id, self._raw_details)
        if (status_code == 200):
            self.update_state(response)

    @property
    def id(self):
        return self._id

    @property
    def raw_details(self):
        return self._raw_details

    def refresh(self):
        """Refresh the state of the device."""
        _LOGGER.debug("PyUIProtectAutomation:refresh")
        response, status_code = self._uiProtectAlarms.call_uiprotect_api(UIProtectApi.GET_AUTOMATIONS, self._id)
        if status_code == 200:
            self.update_state(response)
        

        self._raw_details = self._uiProtectAlarms.automations[self._id].raw_details

    def update_state(self, state: dict):
        _LOGGER.debug("PyUIProtectAutomation:update_state: %s", state.get("id"))
        super().update_state(state)

        self._raw_details = state
        self._id = state.get("id")
        self._enabled = state.get("enable")
        self._name = state.get("name")