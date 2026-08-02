"""
This tests all requests made by the PyUIProtectAlarms library with pytest.

All tests inherit from the TestBase class which contains the fixtures
and methods needed to run the tests.
"""
# import utils
import logging
from unittest.mock import call
from .testbase import TestBase
from .imports import UIProtectApi


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

        # Verify that a GET call was made to refresh the specific automation
        # before the PATCH call to update it.
        api_calls = self.mock_api.call_args_list
        call_apis = [c[0][0] for c in api_calls]  # first positional arg of each call

        # Find the refresh GET and the update PATCH calls
        get_calls = [c for c in api_calls
                     if c[0][0] == UIProtectApi.GET_AUTOMATIONS
                     and len(c[0]) > 1 and c[0][1] == co_alarm_id]
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
                     and len(c[0]) > 1 and c[0][1] == co_alarm_id]
        assert len(get_calls) >= 1, "Expected a GET refresh call when re-enabling"
