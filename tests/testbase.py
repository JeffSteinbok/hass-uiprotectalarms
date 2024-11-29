"""Base class for all tests. Contains a mock for call_dreo_api() function and instantiated Dreo object."""
# pylint: disable=W0201
import logging
import os
from typing import Optional
from unittest.mock import patch
import pytest
from  .imports import * # pylint: disable=W0401,W0614
from . import defaults
from . import call_json

logger = logging.getLogger(__name__)

API_REPONSE_BASE_PATH = 'tests/api_responses/'

PATCH_BASE_PATH = 'custom_components.uiprotectalarms.pyuiprotectalarms'
PATCH_SEND_COMMAND = f'{PATCH_BASE_PATH}.PyUIProtectAlarms.send_command'
PATCH_CALL_UIPROTECT_API = f'{PATCH_BASE_PATH}.PyUIProtectAlarms.call_uiprotect_api'

Defaults = defaults.Defaults

class TestBase:
    """Base class for all tests.

    Contains instantiated PyDreo object and mocked
    API call for call_api() function."""

    @pytest.fixture(autouse=True, scope='function')
    def setup(self, caplog):
        """Fixture to instantiate Dreo object, start logging and start Mock.

        Attributes
        ----------
        self.mock_api : Mock
        self.pydreo_manager : PyDreo
        self.caplog : LogCaptureFixture

        Yields
        ------
        Class instance with mocked call_api() function and Dreo object
        """
        self._api_response_file_name = None
        self.mock_api_call = patch(PATCH_CALL_UIPROTECT_API)
        self.caplog = caplog
        self.mock_api = self.mock_api_call.start()
        self.mock_api.side_effect = self.call_uiprotect_api
        self.mock_api.create_autospect()
        self.mock_api.return_value.ok = True


        self.uiProtectApiClient = PyUIProtectAlarms(
            username='USERNAME', 
            password='PASSWORD',
            host='192.168.1.123',
            port=443
            )
        
        caplog.set_level(logging.DEBUG)
        yield
        self.mock_api_call.stop()


    @property
    def api_response_file_name(self):
        """Get the file name for the devices file."""
        return self._api_response_file_name

    @api_response_file_name.setter
    def api_response_file_name(self, value: str):
        """Set the file name for the devices file."""
        self._api_response_file_name = value


    def call_uiprotect_api(self,
        api: str,
        json_object: Optional[dict] = None):
        """Call Dreo REST API"""
        print(f'API call: {api} {json_object}')
        logger.debug('API call: %s %s', api, json_object)

        if api == UIProtectApi.GET_AUTOMATIONS:
            return (call_json.get_response_from_file(self._api_response_file_name), 200)

