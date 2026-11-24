"""Tests for the diagnostics download (#24)."""
# pylint: disable=protected-access
import asyncio
import json
from unittest.mock import MagicMock

from homeassistant.components.diagnostics import REDACTED

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


def _config_entry():
    entry = MagicMock()
    entry.as_dict.return_value = {
        "entry_id": "test_entry_id",
        "domain": DOMAIN,
        "title": FAKE_HOST,
        "data": {"host": FAKE_HOST, "username": FAKE_USERNAME, "password": FAKE_PASSWORD},
        "options": {"rule_prefix": None, "notification_switches": True},
    }
    return entry


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
