"""Diagnostics support for the Uiprotectalarms HomeAssistant Integration."""

# Suppress warnings about unused function arguments
# pylint: disable=W0613

from __future__ import annotations

import re
from typing import Any

from homeassistant.components.diagnostics import async_redact_data

from .pyuiprotectalarms import PyUIProtectAlarms
from .haimports import * # pylint: disable=W0401,W0614
from .const import (
    DOMAIN,
    PYUIPROTECTALARMS_MANAGER
)

# Config entry keys to redact: the credentials, and the console host, which
# is also used as the entry title.
ENTRY_TO_REDACT = {CONF_HOST, CONF_PASSWORD, CONF_USERNAME, "title"}

# Keys to redact anywhere in the alarm payloads from Protect, compared
# case-insensitively against any part of the key. These payloads are not
# documented, so match broadly: credentials and session data, URLs and
# headers (webhook ids, API keys), and anything identifying a person,
# device or the network.
_SECRET_KEY_RE = re.compile(
    r"token|password|passwd|secret|cookie|csrf|auth|api[_-]?key|"
    r"url|uri|webhook|header|body|host|email|phone|mac|"
    r"^ip$|ipaddress|^user$|userid|^users$|^device$|^sn$|serial|productid",
    re.IGNORECASE,
)

# The only alarm action whose settings are useful for debugging this
# integration. Every other action (webhooks, HTTP requests, ...) is reduced
# to its type, as its settings can hold URLs and credentials under any key.
_NOTIFICATION_ACTION = "SEND_NOTIFICATION"


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    manager: PyUIProtectAlarms | None = hass.data.get(DOMAIN, {}).get(PYUIPROTECTALARMS_MANAGER)

    return {
        "entry": async_redact_data(entry.as_dict(), ENTRY_TO_REDACT),
        DOMAIN: _get_diagnostics(manager) if manager is not None else None,
    }


def _get_diagnostics(manager: PyUIProtectAlarms) -> dict[str, Any]:
    """Describe the alarms and notification settings the manager knows about."""
    # Copy first: the alarm list can be replaced by a refresh in another thread
    alarms = list(manager.automations.values())
    notifications = list(manager.notifications.values())

    return {
        "automation_rule_prefix": manager.automation_rule_prefix,
        "alarm_count": len(alarms),
        "alarms": [
            {
                "id": alarm.id,
                "name": alarm.name,
                "enabled": alarm.enabled,
                "raw_details": _redact_alarm(alarm.raw_details),
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
    }


def _redact_alarm(raw_details: Any) -> Any:
    """Return a redacted copy of an alarm payload from Protect."""
    if not isinstance(raw_details, dict):
        return _redact(raw_details)

    alarm = dict(raw_details)
    actions = alarm.get("actions")
    if isinstance(actions, list):
        alarm["actions"] = [
            action
            if not isinstance(action, dict) or action.get("type") == _NOTIFICATION_ACTION
            else {"type": action.get("type"), "metadata": REDACTED}
            for action in actions
        ]
    return _redact(alarm)


def _redact(data: Any) -> Any:
    """Return a copy of data with the values of sensitive keys redacted."""
    if isinstance(data, dict):
        return {
            key: REDACTED
            if isinstance(key, str) and _SECRET_KEY_RE.search(key) and value not in (None, "")
            else _redact(value)
            for key, value in data.items()
        }
    if isinstance(data, list):
        return [_redact(item) for item in data]
    return data
