"""Tests for the diagnostics download (#24)."""
# pylint: disable=protected-access
import asyncio
import json
from types import MappingProxyType
from unittest.mock import MagicMock

from homeassistant.components.diagnostics import REDACTED
from homeassistant.config_entries import ConfigEntry

from custom_components.uiprotectalarms.const import DOMAIN, PYUIPROTECTALARMS_MANAGER
from custom_components.uiprotectalarms.diagnostics import (
    async_get_config_entry_diagnostics,
)
from custom_components.uiprotectalarms.pyuiprotectalarms.pyuiprotectnotification import (
    PyUIProtectNotification,
)

from .integrationtestbase import IntegrationTestBase

# Obviously fake values, so any of them in the output is a leak.
FAKE_HOST = "protect.invalid"
FAKE_USERNAME = "fake-diag-user"
FAKE_PASSWORD = "fake-diag-password"
FAKE_COOKIE = "fake-diag-cookie"
FAKE_CSRF = "fake-diag-csrf"
FAKE_WEBHOOK_URL = "https://ha.invalid/api/webhook/fake-webhook-id"
FAKE_AUTHORIZATION = "Bearer fake-diag-authorization"
FAKE_API_KEY = "fake-diag-api-key"
FAKE_TARGET = "fake-diag-target-value"

# An alarm that also calls a webhook. Protect's exact field names for this are
# not documented, so the action uses a mix of names the redaction must catch.
WEBHOOK_ALARM = {
    "id": "alarm-webhook",
    "name": "Webhook Alarm",
    "enable": True,
    "actions": [
        {
            "type": "SEND_NOTIFICATION",
            "metadata": {"receivers": [{"user": "fake-receiver-id", "channels": ["push"]}]},
        },
        {
            "type": "WEBHOOK",
            "metadata": {
                "url": FAKE_WEBHOOK_URL,
                "method": "POST",
                "headers": {"Authorization": FAKE_AUTHORIZATION, "X-Api-Key": FAKE_API_KEY},
                "target": FAKE_TARGET,
            },
        },
        {"type": "HTTP_REQUEST", "Metadata": {"URL": FAKE_WEBHOOK_URL}},
    ],
    "Webhook": {"Url": FAKE_WEBHOOK_URL, "X-API-KEY": FAKE_API_KEY},
}


def _config_entry():
    """A real ConfigEntry, so as_dict() has its real shape."""
    return ConfigEntry(
        data={"host": FAKE_HOST, "username": FAKE_USERNAME, "password": FAKE_PASSWORD},
        discovery_keys=MappingProxyType({}),
        domain=DOMAIN,
        minor_version=1,
        options={"rule_prefix": None, "notification_switches": True},
        source="user",
        subentries_data=None,
        title=FAKE_HOST,
        unique_id=None,
        version=1,
    )


def _hass(manager):
    hass = MagicMock()
    hass.data = {DOMAIN: {PYUIPROTECTALARMS_MANAGER: manager}}
    return hass


class TestDiagnostics(IntegrationTestBase):
    """async_get_config_entry_diagnostics works and leaks nothing."""

    def _load_manager(self):
        self.api_response_file_name = "automations_1.json"
        assert self.manager.load_automations()
        self.manager._users = [{"id": "fake-user-id", "email": "someone@example.invalid"}]
        self.manager._notifications["motion"] = PyUIProtectNotification(
            {"id": "motion", "name": "Motion", "channels": ["push"]}, self.manager
        )
        # Session secrets the manager holds at runtime
        self.manager._last_token_cookie = FAKE_COOKIE
        self.manager._last_csrf_token = FAKE_CSRF

    def _diagnostics(self, manager):
        return asyncio.run(async_get_config_entry_diagnostics(_hass(manager), _config_entry()))

    def test_diagnostics_lists_alarms(self):
        """The download contains every alarm with its state."""
        self._load_manager()

        result = self._diagnostics(self.manager)

        data = result[DOMAIN]
        assert data["alarm_count"] == len(self.manager.automations) > 0
        assert {alarm["id"] for alarm in data["alarms"]} == set(self.manager.automations)
        for alarm in data["alarms"]:
            automation = self.manager.automations[alarm["id"]]
            assert alarm["name"] == automation.name
            assert alarm["enabled"] == automation.enabled
            assert alarm["raw_details"]["name"] == automation.name
        assert data["notification_count"] == 1
        assert data["notifications"][0]["push_enabled"] is True
        assert data["notifications"][0]["email_enabled"] is False
        assert data["user_count"] == 1
        # The whole result must be JSON serializable for the download
        json.dumps(result)

    def test_diagnostics_redacts_secrets(self):
        """Credentials, session data and user ids are not in the download."""
        self._load_manager()

        result = self._diagnostics(self.manager)
        text = json.dumps(result)

        for secret in (FAKE_HOST, FAKE_USERNAME, FAKE_PASSWORD, FAKE_COOKIE, FAKE_CSRF,
                       "someone@example.invalid", "**USERID1**"):
            assert secret not in text, f"leaked into diagnostics: {secret!r}"
        assert result["entry"]["data"] == {
            "host": REDACTED, "username": REDACTED, "password": REDACTED
        }
        receivers = result[DOMAIN]["alarms"][0]["raw_details"]["actions"][0]["metadata"]["receivers"]
        assert all(receiver["user"] == REDACTED for receiver in receivers)
        # Redaction works on a copy: the live alarm data is untouched
        first = self.manager.automations[result[DOMAIN]["alarms"][0]["id"]]
        assert first.raw_details["actions"][0]["metadata"]["receivers"][0]["user"] == "**USERID1**"

    def test_diagnostics_with_no_alarms(self):
        """A manager that has not loaded anything still produces diagnostics."""
        result = self._diagnostics(self.manager)

        assert result[DOMAIN]["alarm_count"] == 0
        assert result[DOMAIN]["alarms"] == []
        assert result[DOMAIN]["notification_count"] == 0

    def test_diagnostics_with_mocked_manager(self):
        """Works against a plain mock that only offers the manager's public API."""
        alarm = MagicMock(id="alarm-1", enabled=True, raw_details={"id": "alarm-1", "userId": "fake-uid"})
        alarm.name = "Front Door"
        manager = MagicMock(
            automations={"alarm-1": alarm}, notifications={}, users=[], automation_rule_prefix="HA"
        )

        result = self._diagnostics(manager)

        assert result[DOMAIN]["automation_rule_prefix"] == "HA"
        assert result[DOMAIN]["alarms"] == [
            {"id": "alarm-1", "name": "Front Door", "enabled": True,
             "raw_details": {"id": "alarm-1", "userId": REDACTED}}
        ]

    def test_diagnostics_redacts_webhook_actions(self):
        """URLs and credentials in non-notification actions never leave the system."""
        alarm = MagicMock(id="alarm-webhook", enabled=True, raw_details=WEBHOOK_ALARM)
        alarm.name = "Webhook Alarm"
        manager = MagicMock(
            automations={"alarm-webhook": alarm}, notifications={}, users=[], automation_rule_prefix=None
        )

        result = self._diagnostics(manager)
        text = json.dumps(result)

        for secret in (FAKE_WEBHOOK_URL, "fake-webhook-id", FAKE_AUTHORIZATION, FAKE_API_KEY,
                       FAKE_TARGET, "fake-receiver-id"):
            assert secret not in text, f"leaked into diagnostics: {secret!r}"
        details = result[DOMAIN]["alarms"][0]["raw_details"]
        notification, webhook, http_request = details["actions"]
        # Notification settings stay readable, minus the user ids
        assert notification["metadata"]["receivers"] == [{"user": REDACTED, "channels": ["push"]}]
        # Other actions keep only their type
        assert webhook == {"type": "WEBHOOK", "metadata": REDACTED}
        assert http_request == {"type": "HTTP_REQUEST", "metadata": REDACTED}
        # Key matching is case-insensitive, outside of actions as well
        assert details["Webhook"] == REDACTED
        # The live alarm data is untouched
        assert WEBHOOK_ALARM["actions"][1]["metadata"]["url"] == FAKE_WEBHOOK_URL

    def test_diagnostics_keeps_only_known_notification_settings(self):
        """Unknown fields of a notification action are redacted, whatever their key."""
        notification_alarm = {
            "id": "alarm-notify",
            "actions": [
                {
                    "type": "SEND_NOTIFICATION",
                    "endpoint": FAKE_TARGET,
                    "metadata": {
                        "receivers": [
                            {
                                "user": "fake-receiver-id",
                                "channels": ["push", "email"],
                                "schedules": [],
                                "link": FAKE_WEBHOOK_URL,
                            },
                            "fake-receiver-string",
                        ],
                        "destination": FAKE_TARGET,
                    },
                },
            ],
        }
        alarm = MagicMock(id="alarm-notify", enabled=True, raw_details=notification_alarm)
        alarm.name = "Notify Alarm"
        manager = MagicMock(
            automations={"alarm-notify": alarm}, notifications={}, users=[], automation_rule_prefix=None
        )

        result = self._diagnostics(manager)
        text = json.dumps(result)

        for secret in (FAKE_TARGET, FAKE_WEBHOOK_URL, "fake-receiver-id", "fake-receiver-string"):
            assert secret not in text, f"leaked into diagnostics: {secret!r}"
        assert result[DOMAIN]["alarms"][0]["raw_details"]["actions"] == [
            {
                "type": "SEND_NOTIFICATION",
                "endpoint": REDACTED,
                "metadata": {
                    "receivers": [
                        {"user": REDACTED, "channels": ["push", "email"], "schedules": [],
                         "link": REDACTED},
                        REDACTED,
                    ],
                    "destination": REDACTED,
                },
            }
        ]

    def test_diagnostics_redacts_network_and_device_ids(self):
        """IP addresses and device ids are redacted wherever they appear."""
        raw_details = {
            "id": "alarm-net",
            "sources": [{"deviceId": "fake-device-id", "type": "camera"}],
            "conditions": [{"condition": {"devices": ["fake-device-1", "fake-device-2"]}}],
            "network": {"IPv4": "fake-ipv4-value", "ipv6": "fake-ipv6-value", "DeviceID": "fake-device-3"},
        }
        alarm = MagicMock(id="alarm-net", enabled=False, raw_details=raw_details)
        alarm.name = "Network Alarm"
        manager = MagicMock(
            automations={"alarm-net": alarm}, notifications={}, users=[], automation_rule_prefix=None
        )

        result = self._diagnostics(manager)
        text = json.dumps(result)

        for secret in ("fake-device-id", "fake-device-1", "fake-device-2", "fake-device-3",
                       "fake-ipv4-value", "fake-ipv6-value"):
            assert secret not in text, f"leaked into diagnostics: {secret!r}"
        details = result[DOMAIN]["alarms"][0]["raw_details"]
        assert details["sources"] == [{"deviceId": REDACTED, "type": "camera"}]
        assert details["conditions"] == [{"condition": {"devices": REDACTED}}]
        assert details["network"] == {"IPv4": REDACTED, "ipv6": REDACTED, "DeviceID": REDACTED}
