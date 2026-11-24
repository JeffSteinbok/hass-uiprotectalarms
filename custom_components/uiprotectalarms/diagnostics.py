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
    r"^ip$|ipaddress|ipv4|ipv6|^user$|userid|^users$|^device$|^devices$|deviceid|"
    r"^sn$|serial|productid",
    re.IGNORECASE,
)

# The only alarm action whose settings are useful for debugging this
# integration, and only its known fields. Every other action (webhooks,
# HTTP requests, ...) is reduced to its type, as its settings can hold URLs
# and credentials under any key.
_NOTIFICATION_ACTION = "SEND_NOTIFICATION"

# Of a notification action, only these receiver settings are kept (the
# receiver's user id is redacted); anything else in it is redacted, whatever
# its key, as notification settings are not documented either.
_RECEIVER_KEYS = ("channels", "schedules")


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
        alarm["actions"] = [_redact_action(action) for action in actions]
    return _redact(alarm)


def _redact_action(action: Any) -> Any:
    """Keep only the known notification settings of an alarm action."""
    if not isinstance(action, dict):
        return action
    if action.get("type") != _NOTIFICATION_ACTION:
        return {"type": action.get("type"), "metadata": REDACTED}

    redacted = {
        key: value if key in ("type", "metadata") else REDACTED
        for key, value in action.items()
    }
    metadata = action.get("metadata")
    if isinstance(metadata, dict):
        redacted["metadata"] = {
            key: _redact_receivers(value) if key == "receivers" else REDACTED
            for key, value in metadata.items()
        }
    elif metadata is not None:
        redacted["metadata"] = REDACTED
    return redacted


def _redact_receivers(receivers: Any) -> Any:
    """Keep only the channels and schedules of each notification receiver."""
    if not isinstance(receivers, list):
        return REDACTED
    return [
        {
            key: value if key in _RECEIVER_KEYS else REDACTED
            for key, value in receiver.items()
        }
        if isinstance(receiver, dict)
        else REDACTED
        for receiver in receivers
    ]


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
