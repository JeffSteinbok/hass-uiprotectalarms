"""Support notification switches for Uiprotectalarms devices"""
# Suppress warnings about DataClass constructors
# pylint: disable=E1123

# Suppress warnings about unused function arguments
# pylint: disable=W0613
from __future__ import annotations

from typing import Any, Callable
from dataclasses import dataclass
import logging

from .haimports import *  # pylint: disable=W0401,W0614
from .pyuiprotectalarms import PyUIProtectAlarms
from .pyuiprotectalarms.pyuiprotectnotification import PyUIProtectNotification
from .baseentity import UIProtectAlarmsBaseEntityHA

from .const import LOGGER, DOMAIN, PYUIPROTECTALARMS_MANAGER

_LOGGER = logging.getLogger(LOGGER)


@dataclass
class UIProtectAlarmsNotificationSwitchHAEntityDescription(SwitchEntityDescription):
    """Describe UIProtectAlarms Notification Switch entity."""

    attr_name: str = None
    icon: str = None
    channel_type: str = None  # "push" or "email"

NOTIFICATION_SWITCHES: list[UIProtectAlarmsNotificationSwitchHAEntityDescription] = [
    UIProtectAlarmsNotificationSwitchHAEntityDescription(
        key="Push",
        translation_key="notification_push",
        attr_name="push_enabled",
        icon="mdi:bell",
        channel_type="push"
    ),
    UIProtectAlarmsNotificationSwitchHAEntityDescription(
        key="Email",
        translation_key="notification_email",
        attr_name="email_enabled",
        icon="mdi:email",
        channel_type="email"
    )
]

def get_notification_entries(pyuiprotectalarms_notifications : dict[PyUIProtectNotification]) -> list[UIProtectAlarmsNotificationSwitchHA]:
    """Get the Uiprotectalarms Notification Switches."""
    switch_ha_collection : list[UIProtectAlarmsNotificationSwitchHA] = []

    for pyuiprotectalarms_notification in pyuiprotectalarms_notifications.values():

        _LOGGER.debug("NotificationSwitch:get_entries: Adding switches for %s", pyuiprotectalarms_notification.name)
        switch_keys : list[str] = []

        for switch_definition in NOTIFICATION_SWITCHES:
            _LOGGER.debug("NotificationSwitch:get_entries: checking attribute: %s on %s", switch_definition.attr_name, pyuiprotectalarms_notification.name)

            if (switch_definition.key in switch_keys):
                _LOGGER.error("NotificationSwitch:get_entries: Duplicate switch key %s", switch_definition.key)
                continue
            
            _LOGGER.debug("NotificationSwitch:get_entries: Adding switch %s", switch_definition.key)
            switch_keys.append(switch_definition.key)
            switch_ha_collection.append(UIProtectAlarmsNotificationSwitchHA(pyuiprotectalarms_notification, switch_definition))

    return switch_ha_collection


class UIProtectAlarmsNotificationSwitchHA(UIProtectAlarmsBaseEntityHA, SwitchEntity):

    def __init__(
        self, 
        pyuiprotectalarms_notification: PyUIProtectNotification, 
        description: UIProtectAlarmsNotificationSwitchHAEntityDescription
    ) -> None:
        super().__init__(pyuiprotectalarms_notification)

        self.pyuiprotectalarms_notification = pyuiprotectalarms_notification

        # Note this is a "magic" HA property.  Don't rename
        self.entity_description = description

        notification_name = pyuiprotectalarms_notification.name
        self._attr_name = f"{notification_name} {description.key}"
        self._attr_unique_id = f"{pyuiprotectalarms_notification.id}-{description.channel_type}"
        self._attr_should_poll = False
        if description.icon:
            self._attr_icon = description.icon

    @property
    def is_on(self) -> bool:
        """Return True if notification channel is enabled."""
        _LOGGER.debug(
            "UiprotectalarmsNotificationSwitchHA:is_on for %s %s is %s",
            self.pyuiprotectalarms_notification.name,
            self.entity_description.key,
            getattr(self.pyuiprotectalarms_notification, self.entity_description.attr_name),
        )
        
        return getattr(self.pyuiprotectalarms_notification, self.entity_description.attr_name)

    def turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the notification channel on."""
        _LOGGER.debug("Turning on %s %s", self.pyuiprotectalarms_notification.name, self.entity_description.key)
        setattr(self.pyuiprotectalarms_notification, self.entity_description.attr_name, True)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the notification channel off."""
        _LOGGER.debug(
            "Turning off %s %s", self.pyuiprotectalarms_notification.name, self.entity_description.key
        )
        setattr(self.pyuiprotectalarms_notification, self.entity_description.attr_name, False)

