"""BaseDevice utilities for Dreo Component."""

from .pyuiprotectalarms import PyUIProtectAlarms
from .pyuiprotectalarms.pyuiprotectbaseobject import PyUIProtectBaseObject

from .haimports import * # pylint: disable=W0401,W0614

from .const import (
    DOMAIN
)

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

        # Create a callback to update state in HA and add it a callback in
        # the PyDreo device. This will cause all handle_server_update responses
        # to update the state in HA.
        @callback
        def update_state():
            # Tell HA we're ready to update
            self.schedule_update_ha_state(True)

        self.pyuiprotect_base_obj.add_attr_callback(update_state)        