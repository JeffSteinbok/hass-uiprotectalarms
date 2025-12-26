"""BaseDevice utilities for Dreo Component."""

import asyncio
import logging

from .pyuiprotectalarms import PyUIProtectAlarms
from .pyuiprotectalarms.pyuiprotectbaseobject import PyUIProtectBaseObject

from .haimports import * # pylint: disable=W0401,W0614

from .const import (
    DOMAIN,
    LOGGER
)

_LOGGER = logging.getLogger(LOGGER)

class UIProtectAlarmsBaseEntityHA(Entity):
    """Base class for all UIProtectAlarms entities."""

    def __init__(self, pyuiprotect_base_obj: PyUIProtectBaseObject) -> None:
        """Initialize the entity."""
        self.pyuiprotect_base_obj = pyuiprotect_base_obj

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""

        return DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self.pyuiprotect_base_obj._uiProtectAlarms._host)
            },
            name="NVR - " + self.pyuiprotect_base_obj._uiProtectAlarms._host,
            manufacturer="Ubiquiti",
            model="NVR"
        )

    @property
    def available(self) -> bool:
        """Return True if device is available."""
        # return self.device.connection_status == "online"
        return True
    
    async def async_added_to_hass(self):
        """Register callbacks."""

        # Store hass reference for thread-safe updates
        hass_ref = self.hass

        # Create a callback to update state in HA and add it a callback in
        # the PyDreo device. This will cause all handle_server_update responses
        # to update the state in HA.
        def update_state():
            # Schedule the state update in the event loop
            # This ensures we're not calling async_write_ha_state from a thread
            if hass_ref and hass_ref.loop and hass_ref.loop.is_running():
                # Create a task in the event loop using call_soon_threadsafe
                # We need to create the coroutine and schedule it properly
                def schedule_update():
                    # This function runs in the event loop thread
                    # Use hass.async_create_task which is the proper way to schedule
                    # async operations in Home Assistant
                    hass_ref.async_create_task(self.async_write_ha_state())
                
                # Schedule the function to run in the event loop
                hass_ref.loop.call_soon_threadsafe(schedule_update)
            else:
                # Fallback: try to schedule directly if loop is not available
                _LOGGER.warning("Cannot schedule state update: hass or loop not available")

        self.pyuiprotect_base_obj.add_attr_callback(update_state)        