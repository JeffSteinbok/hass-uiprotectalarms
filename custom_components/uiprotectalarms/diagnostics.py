"""Diagnostics support for the Uiprotectalarms HomeAssistant Integration."""

# Suppress warnings about unused function arguments
# pylint: disable=W0613

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data

from .pyuiprotectalarms import PyUIProtectAlarms
from .haimports import * # pylint: disable=W0401,W0614
from .const import (
    DOMAIN,
    PYUIPROTECTALARMS_MANAGER
)

# Keys whose values must never end up in a diagnostics download:
# credentials and the console address from the config entry, session data,
# and anything identifying a person or device in the alarm payloads.
TO_REDACT = {
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    # The config entry is titled with the console host name
    "title",
    "password",
    "username",
    "token",
    "accessToken",
    "csrfToken",
    "authorization",
    "cookie",
    "email",
    "user",
    "userId",
    "users",
    "device",
    "mac",
    "sn",
    "productId",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    manager: PyUIProtectAlarms | None = hass.data.get(DOMAIN, {}).get(PYUIPROTECTALARMS_MANAGER)

    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        DOMAIN: _get_diagnostics(manager) if manager is not None else None,
    }


def _get_diagnostics(manager: PyUIProtectAlarms) -> dict[str, Any]:
    """Describe the alarms and notification settings the manager knows about."""
    # Copy first: the alarm list can be replaced by a refresh in another thread
    alarms = list(manager.automations.values())
    notifications = list(manager.notifications.values())

    return async_redact_data(
        {
            "automation_rule_prefix": manager.automation_rule_prefix,
            "alarm_count": len(alarms),
            "alarms": [
                {
                    "id": alarm.id,
                    "name": alarm.name,
                    "enabled": alarm.enabled,
                    "raw_details": alarm.raw_details,
                }
                for alarm in alarms
            ],
            "notification_count": len(notifications),
            "notifications": [
                {
                    "id": notification.id,
                    "name": notification.name,
                    "push_enabled": notification.push_enabled,
                    "email_enabled": notification.email_enabled,
                }
                for notification in notifications
            ],
            "user_count": len(manager.users),
        },
        TO_REDACT,
    )
