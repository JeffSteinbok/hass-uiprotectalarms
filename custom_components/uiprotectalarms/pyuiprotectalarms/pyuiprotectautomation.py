"""Uiprotectalarms API for controling fans."""

import logging
from typing import TYPE_CHECKING, Dict

from .constants import (
        UIProtectApi
)

from .pyuiprotectbaseobject import PyUIProtectBaseObject
from .exceptions import NvrError

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from pyuiprotectalarms import PyUIProtectAlarms


class PyUIProtectAutomation(PyUIProtectBaseObject):
    """Class to represent a Unifi Protect Alarm Automation."""

    def __init__(self, details: Dict[str, list], PyUIProtectAlarms: "PyUIProtectAlarms"):
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

        # Refresh from the server before updating to avoid overwriting concurrent changes
        # made directly in UniFi Protect since the integration was last loaded.
        refresh_response, refresh_status = self._uiProtectAlarms.call_uiprotect_api(
            UIProtectApi.GET_AUTOMATIONS, self._id
        )
        if refresh_status != 200 or not isinstance(refresh_response, dict):
            # Some Protect versions have no single-alarm endpoint (404):
            # read the full list and pick this alarm from it
            _LOGGER.debug("Single alarm read failed (status %s), reading full list", refresh_status)
            list_response, list_status = self._uiProtectAlarms.call_uiprotect_api(
                UIProtectApi.GET_AUTOMATIONS
            )
            if list_status != 200 or not isinstance(list_response, list):
                raise NvrError(f"Unable to read alarm {self._id} before update (status {list_status})")
            refresh_response = next((a for a in list_response if a.get("id") == self._id), None)
            if refresh_response is None:
                raise NvrError(f"Alarm {self._id} no longer exists in UniFi Protect")

        _LOGGER.debug("Refreshed automation %s before update", self._id)
        details = dict(refresh_response)
        name = details.get("name", self._name) or ""

        # If the automation is disabled, add (Disabled) to the name, and remove it if enabled.
        if value is True:
            if name.endswith(" (Disabled)"):
                name = name[:-11]
        elif not name.endswith(" (Disabled)"):
            name = name + " (Disabled)"
        details["name"] = name
        details["enable"] = value

        response, status_code = self._uiProtectAlarms.call_uiprotect_api(
            UIProtectApi.UPDATE_AUTOMATION, self._id, details
        )
        if status_code != 200:
            raise NvrError(f"Unable to update alarm {self._id} (status {status_code})")

        # Only change local state once Protect accepted the change
        self.handle_server_update_base(response if response else details)

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