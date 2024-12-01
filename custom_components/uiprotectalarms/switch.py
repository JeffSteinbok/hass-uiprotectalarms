"""Support additional switches for some Uiprotectalarms devices"""
# Suppress warnings about DataClass constructors
# pylint: disable=E1123

# Suppress warnings about unused function arguments
# pylint: disable=W0613
from __future__ import annotations

from typing import Any
from dataclasses import dataclass
import logging

from .haimports import *  # pylint: disable=W0401,W0614
from .pyuiprotectalarms import PyUIProtectAlarms
from .pyuiprotectalarms.pyuiprotectautomation import PyUIProtectAutomation
from .baseentity import UIProtectAlarmsBaseEntityHA

from .const import LOGGER, DOMAIN, PYUIPROTECTALARMS_MANAGER

_LOGGER = logging.getLogger(LOGGER)


@dataclass
class UIProtectAlarmsSwitchHAEntityDescription(SwitchEntityDescription):
    """Describe UIProtectAlarms Switch entity."""

    attr_name: str = None
    icon: str = None

SWITCHES: list[UIProtectAlarmsSwitchHAEntityDescription] = [
    UIProtectAlarmsSwitchHAEntityDescription(
        key="Enabled",
        translation_key="enabled",
        attr_name="enabled",
        icon="mdi:alarm-light",
    )
]

def get_entries(pyuiprotectalarms_automations : dict[PyUIProtectAutomation]) -> list[UIProtectAlarmsSwitchHA]:
    """Get the Uiprotectalarms Switches for the devices."""
    switch_ha_collection : UIProtectAlarmsSwitchHA = []

    for pyuiprotectalarms_automation in pyuiprotectalarms_automations.values():

        _LOGGER.debug("Switch:get_entries: Adding switches for %s", pyuiprotectalarms_automation.name)
        switch_keys : list[str] = []

        for switch_definition in SWITCHES:
            _LOGGER.debug("Switch:get_entries: checking attribute: %s on %s", switch_definition.attr_name, pyuiprotectalarms_automation.name)

            if (switch_definition.key in switch_keys):
                _LOGGER.error("Switch:get_entries: Duplicate switch key %s", switch_definition.key)
                continue
            
            _LOGGER.debug("Switch:get_entries: Adding switch %s", switch_definition.key)
            switch_keys.append(switch_definition.key)
            switch_ha_collection.append(UIProtectAlarmsSwitchHA(pyuiprotectalarms_automation, switch_definition))

    return switch_ha_collection


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Uiprotectalarms Switch platform."""
    _LOGGER.info("Starting Uiprotectalarms Switch Platform")

    pyuiprotectalarms_manager: PyUIProtectAlarms = hass.data[DOMAIN][PYUIPROTECTALARMS_MANAGER]

    switch_entities_ha : list[SwitchEntity] = []
    switch_entities_to_add = get_entries(pyuiprotectalarms_manager.automations)

    switch_entities_ha.extend(switch_entities_to_add)

    async_add_entities(switch_entities_ha)

class UIProtectAlarmsSwitchHA(UIProtectAlarmsBaseEntityHA, SwitchEntity):

    def __init__(
        self, 
        pyuiprotectalarms_automation: PyUIProtectAutomation, 
        description: UIProtectAlarmsSwitchHAEntityDescription
    ) -> None:
        super().__init__(pyuiprotectalarms_automation)

        self.pyuiprotectalarms_automation = pyuiprotectalarms_automation

        # Note this is a "magic" HA property.  Don't rename
        self.entity_description = description

        self._attr_name = pyuiprotectalarms_automation.name + " " + description.key
        self._attr_unique_id = f"{pyuiprotectalarms_automation.id}-{description.key}"

    @property
    def is_on(self) -> bool:
        """Return True if device is on."""
        _LOGGER.debug(
            "UiprotectalarmsSwitchHA:is_on for %s %s is %s",
            self.pyuiprotectalarms_automation.name,
            self.entity_description.key,
            getattr(self.pyuiprotectalarms_automation, self.entity_description.attr_name),
        )
        
        return getattr(self.pyuiprotectalarms_automation, self.entity_description.attr_name)

    def turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the device on."""
        _LOGGER.debug("Turning on %s %s", self.pyuiprotectalarms_automation.name, self.entity_description.key)
        setattr(self.pyuiprotectalarms_automation, self.entity_description.attr_name, True)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        _LOGGER.debug(
            "Turning off %s %s", self.pyuiprotectalarms_automation.name, self.entity_description.key
        )
        setattr(self.pyuiprotectalarms_automation, self.entity_description.attr_name, False)
