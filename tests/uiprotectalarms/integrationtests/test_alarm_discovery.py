"""Tests for picking up alarms created/deleted in Protect without a reload (#16)."""
# pylint: disable=protected-access
import asyncio
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.exceptions import HomeAssistantError

import custom_components.uiprotectalarms as integration
from custom_components.uiprotectalarms import _async_alarms_updated
from custom_components.uiprotectalarms import switch as switch_platform
from custom_components.uiprotectalarms.const import (
    CONF_NOTIFICATION_SWITCHES,
    DOMAIN,
    PYUIPROTECTALARMS_MANAGER,
    SIGNAL_ALARMS_UPDATED,
)
from custom_components.uiprotectalarms.pyuiprotectalarms.constants import UIProtectApi

from .imports import *  # pylint: disable=W0401,W0614
from .integrationtestbase import IntegrationTestBase

logger = logging.getLogger(__name__)

ENTRY_ID = "test_entry_id"
# automations_2.json = automations_1.json without this alarm ...
REMOVED_ALARM_ID = "6746a0a203df5603e4001e3b"
# ... and with this new one added
NEW_ALARM_ID = "6900aaaa01584d03e4009999"
NEW_ALARM_NAME = "New Driveway Alarm"


def _config_entry():
    entry = MagicMock()
    entry.entry_id = ENTRY_ID
    entry.options = {CONF_NOTIFICATION_SWITCHES: False}
    return entry


class TestAlarmDiscovery(IntegrationTestBase):
    """Alarms added or removed in Protect are synced during a refresh."""

    def test_load_automations_tracks_added_and_removed_alarms(self):
        """A re-read adds new alarms, drops deleted ones and keeps existing objects."""
        self.api_response_file_name = "automations_1.json"
        self.manager.load_automations()
        before = dict(self.manager.automations)
        assert REMOVED_ALARM_ID in before
        assert NEW_ALARM_ID not in before

        self.api_response_file_name = "automations_2.json"
        self.manager.load_automations()

        assert NEW_ALARM_ID in self.manager.automations
        assert self.manager.automations[NEW_ALARM_ID].name == NEW_ALARM_NAME
        assert REMOVED_ALARM_ID not in self.manager.automations
        assert len(self.manager.automations) == 33
        # Existing alarms keep their object, so their entities stay wired up
        for automation_id, automation in self.manager.automations.items():
            if automation_id != NEW_ALARM_ID:
                assert automation is before[automation_id]

    def test_refresh_adds_switch_for_new_alarm(self):
        """The switch platform adds a switch for a new alarm only, once."""
        self.api_response_file_name = "automations_1.json"
        self.manager.load_automations()

        hass = MagicMock()
        hass.data = {DOMAIN: {PYUIPROTECTALARMS_MANAGER: self.manager}}
        config_entry = _config_entry()
        async_add_entities = MagicMock()

        with patch.object(switch_platform, "async_dispatcher_connect") as connect:
            asyncio.run(switch_platform.async_setup_entry(hass, config_entry, async_add_entities))

        connect.assert_called_once()
        assert connect.call_args.args[1] == SIGNAL_ALARMS_UPDATED.format(ENTRY_ID)
        on_alarms_updated = connect.call_args.args[2]
        # The dispatcher listener is disconnected when the entry unloads
        config_entry.async_on_unload.assert_called_once_with(connect.return_value)

        async_add_entities.assert_called_once()
        initial_entities = async_add_entities.call_args.args[0]
        assert len(initial_entities) == 33
        initial_automations = {
            e.unique_id: e.pyuiprotectalarms_automation for e in initial_entities
        }

        # Refresh with nothing new: nothing is added
        async_add_entities.reset_mock()
        on_alarms_updated()
        async_add_entities.assert_not_called()

        # Refresh returns a new alarm (and one alarm was deleted)
        self.api_response_file_name = "automations_2.json"
        self.manager.load_automations()
        on_alarms_updated()

        async_add_entities.assert_called_once()
        new_entities = async_add_entities.call_args.args[0]
        assert [e.unique_id for e in new_entities] == [f"{NEW_ALARM_ID}-Enabled"]
        assert new_entities[0].name == f"{NEW_ALARM_NAME} Enabled"
        assert new_entities[0].is_on is False

        # Existing entities still point at the same, updated alarm objects
        for entity in initial_entities:
            automation_id = entity.unique_id[: -len("-Enabled")]
            if automation_id == REMOVED_ALARM_ID:
                continue
            assert entity.pyuiprotectalarms_automation is self.manager.automations[automation_id]
            assert entity.pyuiprotectalarms_automation is initial_automations[entity.unique_id]

        # A second refresh does not add the new alarm again
        async_add_entities.reset_mock()
        self.manager.load_automations()
        on_alarms_updated()
        async_add_entities.assert_not_called()

    def test_alarms_updated_removes_deleted_alarm_switch_and_signals(self):
        """Switches of deleted alarms are removed, other switches are kept."""
        self.api_response_file_name = "automations_2.json"
        self.manager.load_automations()

        registry_entries = [
            SimpleNamespace(domain="switch", unique_id=f"{REMOVED_ALARM_ID}-Enabled",
                            entity_id="switch.person_at_front_door_enabled"),
            SimpleNamespace(domain="switch", unique_id=f"{NEW_ALARM_ID}-Enabled",
                            entity_id="switch.new_driveway_alarm_enabled"),
            SimpleNamespace(domain="switch", unique_id="some_notification-push",
                            entity_id="switch.some_notification_push"),
        ]
        registry = MagicMock()
        hass = MagicMock()
        config_entry = _config_entry()

        with patch("custom_components.uiprotectalarms.er.async_get", return_value=registry), \
             patch("custom_components.uiprotectalarms.er.async_entries_for_config_entry",
                   return_value=registry_entries), \
             patch("custom_components.uiprotectalarms.async_dispatcher_send") as send:
            _async_alarms_updated(hass, config_entry, self.manager)

        registry.async_remove.assert_called_once_with("switch.person_at_front_door_enabled")
        send.assert_called_once_with(hass, SIGNAL_ALARMS_UPDATED.format(ENTRY_ID))

    def test_new_alarm_can_be_toggled(self):
        """A newly discovered alarm uses the same fresh-read setter as existing ones."""
        self.api_response_file_name = "automations_1.json"
        self.manager.load_automations()
        self.api_response_file_name = "automations_2.json"
        self.manager.load_automations()
        automation = self.manager.automations[NEW_ALARM_ID]

        fresh = dict(automation.raw_details)
        calls = []

        def fake_api(api, path=None, json_object=None):
            calls.append((api, path, json_object))
            if api == UIProtectApi.GET_AUTOMATIONS:
                return (fresh, 200)
            return (json_object, 200)

        with patch.object(self.manager, "call_uiprotect_api", side_effect=fake_api):
            automation.enabled = True

        assert calls[0][:2] == (UIProtectApi.GET_AUTOMATIONS, NEW_ALARM_ID)
        assert calls[-1][0] == UIProtectApi.UPDATE_AUTOMATION
        assert calls[-1][2]["enable"] is True
        assert automation.enabled is True

    def test_empty_alarm_list_keeps_known_alarms(self):
        """An empty list from Protect does not remove alarms or their switches."""
        self.api_response_file_name = "automations_1.json"
        self.manager.load_automations()
        before = dict(self.manager.automations)

        with patch.object(self.manager, "call_uiprotect_api", return_value=([], 200)):
            assert self.manager.load_automations() is True

        assert self.manager.automations == before
        assert "UniFi Protect returned no alarms, keeping the 33 known alarm(s)" in self.caplog.text

        registry_entries = [
            SimpleNamespace(domain="switch", unique_id=f"{automation_id}-Enabled",
                            entity_id=f"switch.alarm_{automation_id}")
            for automation_id in before
        ]
        registry = MagicMock()
        with patch("custom_components.uiprotectalarms.er.async_get", return_value=registry), \
             patch("custom_components.uiprotectalarms.er.async_entries_for_config_entry",
                   return_value=registry_entries), \
             patch("custom_components.uiprotectalarms.async_dispatcher_send"):
            _async_alarms_updated(MagicMock(), _config_entry(), self.manager)

        registry.async_remove.assert_not_called()

    def _setup_integration(self):
        """Run the integration's async_setup_entry against self.manager.

        Returns the refresh service handler and the periodic sync callback.
        """
        self.api_response_file_name = "automations_1.json"

        async def run_in_executor(func, *args):
            return func(*args)

        hass = MagicMock()
        hass.async_add_executor_job = AsyncMock(side_effect=run_in_executor)
        hass.config_entries.async_forward_entry_setups = AsyncMock()
        config_entry = _config_entry()
        config_entry.data = {}

        with patch(f"{integration.__name__}.pyuiprotectalarms.PyUIProtectAlarms",
                   return_value=self.manager), \
             patch.object(self.manager, "authenticate", return_value=True), \
             patch(f"{integration.__name__}.er.async_get"), \
             patch(f"{integration.__name__}.er.async_entries_for_config_entry", return_value=[]), \
             patch(f"{integration.__name__}.async_track_time_interval") as track:
            assert asyncio.run(integration.async_setup_entry(hass, config_entry)) is True

        refresh_service = hass.services.async_register.call_args.args[2]
        periodic_sync = track.call_args.args[1]
        return refresh_service, periodic_sync

    def test_successful_sync_and_refresh_update_alarm_switches(self):
        """Both the periodic sync and the refresh action sync the alarm switches."""
        refresh_service, periodic_sync = self._setup_integration()

        with patch(f"{integration.__name__}._async_alarms_updated") as alarms_updated:
            asyncio.run(periodic_sync(None))
            asyncio.run(refresh_service(MagicMock()))

        assert alarms_updated.call_count == 2

    def test_failed_sync_and_refresh_skip_alarm_switch_update(self):
        """A failed load never adds or removes alarm switches."""
        refresh_service, periodic_sync = self._setup_integration()
        known = dict(self.manager.automations)
        # No fixture: the mocked API returns a dict, so load_automations raises NvrError
        self.api_response_file_name = None

        with patch(f"{integration.__name__}._async_alarms_updated") as alarms_updated:
            asyncio.run(periodic_sync(None))
            with pytest.raises(HomeAssistantError):
                asyncio.run(refresh_service(MagicMock()))

        alarms_updated.assert_not_called()
        assert "Periodic UniFi Protect alarm sync failed" in self.caplog.text
        assert self.manager.automations == known
