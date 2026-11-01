"""
This tests all requests made by the PyUIProtectAlarms library with pytest.

All tests inherit from the TestBase class which contains the fixtures
and methods needed to run the tests.
"""
# import utils
import logging
from unittest.mock import call, patch
import pytest
from .testbase import TestBase
from .imports import PyUIProtectAlarms, UIProtectApi, BadRequest


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class TestGeneralAPI(TestBase):
    def test_get_automations(self):
        """Test get_devices() method request and API response."""

        self.api_response_file_name = "automations_1.json"
        self.uiProtectApiClient.load_automations()
        assert len(self.uiProtectApiClient.automations) == 33

    def test_enabled_setter_refreshes_before_update(self):
        """Test that setting enabled on an automation refreshes from the server first."""

        self.api_response_file_name = "automations_1.json"
        self.uiProtectApiClient.load_automations()

        co_alarm_id = "6729da9901584d03e4001889"
        automation = self.uiProtectApiClient.automations[co_alarm_id]
        assert automation.name == "CO Alarm"
        assert automation.enabled is True

        # Simulate a server-side change by modifying the raw_details locally
        # (as if they drifted from what the server actually holds).
        original_raw = automation._raw_details.copy()

        # Disable the automation via the setter
        automation.enabled = False

        # Verify that a GET call was made to refresh the full automation list
        # before the PATCH call to update it. (Fetching a single automation by id
        # returns a 404 on some UniFi Protect versions, so the refresh fetches the
        # full list instead.)
        api_calls = self.mock_api.call_args_list
        call_apis = [c[0][0] for c in api_calls]  # first positional arg of each call

        # Find the refresh GET and the update PATCH calls
        get_calls = [c for c in api_calls
                     if c[0][0] == UIProtectApi.GET_AUTOMATIONS
                     and (len(c[0]) <= 1 or c[0][1] is None)]
        update_calls = [c for c in api_calls if c[0][0] == UIProtectApi.UPDATE_AUTOMATION]

        assert len(get_calls) >= 1, "Expected a GET call to refresh the automation before update"
        assert len(update_calls) >= 1, "Expected a PATCH call to update the automation"

        # The GET refresh must have occurred before the UPDATE
        get_index = api_calls.index(get_calls[0])
        update_index = api_calls.index(update_calls[0])
        assert get_index < update_index, "GET refresh must occur before PATCH update"

        # The automation should now be disabled
        assert automation.enabled is False
        assert automation.name == "CO Alarm (Disabled)"

    def test_enabled_setter_enable_removes_disabled_suffix(self):
        """Test that enabling an automation that was disabled removes the (Disabled) suffix."""

        self.api_response_file_name = "automations_1.json"
        self.uiProtectApiClient.load_automations()

        co_alarm_id = "6729da9901584d03e4001889"
        automation = self.uiProtectApiClient.automations[co_alarm_id]

        # Disable first, then re-enable
        automation.enabled = False
        assert automation.name == "CO Alarm (Disabled)"

        # Reset mock call tracking for clarity
        self.mock_api.reset_mock()

        automation.enabled = True
        assert automation.enabled is True
        assert automation.name == "CO Alarm"

        # A GET refresh must have been issued for the re-enable too
        get_calls = [c for c in self.mock_api.call_args_list
                     if c[0][0] == UIProtectApi.GET_AUTOMATIONS
                     and (len(c[0]) <= 1 or c[0][1] is None)]
        assert len(get_calls) >= 1, "Expected a GET refresh call when re-enabling"

    def test_enabled_setter_raises_when_update_fails(self):
        """Test that a failed update (e.g. Global Alarm Manager enabled) raises instead of
        silently doing nothing."""

        self.api_response_file_name = "automations_1.json"
        self.uiProtectApiClient.load_automations()

        co_alarm_id = "6729da9901584d03e4001889"
        automation = self.uiProtectApiClient.automations[co_alarm_id]

        default_side_effect = self.mock_api.side_effect

        def failing_update_side_effect(api, path=None, json_object=None):
            if api == UIProtectApi.UPDATE_AUTOMATION:
                return (
                    {
                        "error": "This operation is not available when global alarm manager is enabled",
                        "name": "BAD_REQUEST",
                    },
                    400,
                )
            return default_side_effect(api, path, json_object)

        self.mock_api.side_effect = failing_update_side_effect

        with pytest.raises(BadRequest):
            automation.enabled = False


class TestReAuthentication:
    """Test that expired sessions get re-authenticated automatically."""

    def test_non_login_api_call_ensures_authenticated(self):
        """Calling any non-login API must ensure the session is still authenticated,
        so an expired token cookie gets refreshed automatically instead of failing
        every call until the integration is reloaded."""

        client = PyUIProtectAlarms(
            username="USERNAME", password="PASSWORD", host="192.168.1.123"
        )

        with patch.object(client, "ensure_authenticated") as mock_ensure_authenticated, \
             patch(
                 "custom_components.uiprotectalarms.pyuiprotectalarms.helpers.Helpers.call_json_api",
                 return_value=({}, 200),
             ) as mock_call_json_api:
            client.call_uiprotect_api(UIProtectApi.GET_AUTOMATIONS)

        mock_ensure_authenticated.assert_called_once()
        mock_call_json_api.assert_called_once()
