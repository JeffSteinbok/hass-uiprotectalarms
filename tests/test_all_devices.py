"""
This tests all requests made by the PyUIProtectAlarms library with pytest.

All tests inherit from the TestBase class which contains the fixtures
and methods needed to run the tests.
"""
# import utils
import logging
from .testbase import TestBase


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class TestGeneralAPI(TestBase):
    """General API testing class for login() and get_devices()."""

    def test_get_automations(self):
        """Test get_devices() method request and API response."""

        self.api_response_file_name = "automations_1.json"
        self.uiProtectApiClient.load_automations()
        assert len(self.uiProtectApiClient.automations) == 33
        