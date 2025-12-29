"""Base class for all integration tests.

Contains mocks for API calls and PyUIProtectAlarms setup.
"""
# pylint: disable=W0201
import logging
import os
from typing import Optional
from unittest.mock import patch
import pytest

from .imports import PyUIProtectAlarms
from . import defaults

logger = logging.getLogger(__name__)

PATCH_BASE_PATH = 'custom_components.uiprotectalarms.pyuiprotectalarms'
PATCH_CALL_UIPROTECT_API = f'{PATCH_BASE_PATH}.PyUIProtectAlarms.call_uiprotect_api'

Defaults = defaults.Defaults
API_RESPONSE_BASE_PATH = Defaults.api_response_base_path


class IntegrationTestBase:
    """Base class for all integration tests.
    
    Contains instantiated PyUIProtectAlarms object and mocked
    API calls for testing Home Assistant integration.
    """

    @property
    def api_response_file_name(self):
        """Get the file name for the API response."""
        return self._api_response_file_name

    @api_response_file_name.setter
    def api_response_file_name(self, value: str):
        """Set the file name for the API response."""
        self._api_response_file_name = value

    @pytest.fixture(autouse=True, scope='function')
    def setup(self, caplog):
        """Fixture to instantiate PyUIProtectAlarms object and start Mock.
        
        Attributes
        ----------
        self.mock_api : Mock
        self.manager : PyUIProtectAlarms
        self.caplog : LogCaptureFixture
        
        Yields
        ------
        Class instance with mocked call_api() function and PyUIProtectAlarms object
        """
        self._api_response_file_name = None
        self.mock_api_call = patch(PATCH_CALL_UIPROTECT_API)
        self.caplog = caplog
        self.mock_api = self.mock_api_call.start()
        self.mock_api.side_effect = self.call_uiprotect_api
        self.mock_api.create_autospect()
        self.mock_api.return_value.ok = True
        
        self.manager = PyUIProtectAlarms(
            host=Defaults.host,
            username=Defaults.username,
            password=Defaults.password
        )
        
        caplog.set_level(logging.DEBUG)
        yield
        self.mock_api_call.stop()

    def call_uiprotect_api(self, api: str, path: str = None, json_object: Optional[dict] = None):
        """Mock call to UIProtect API.
        
        Args:
            api: API endpoint name
            path: Optional API path
            json_object: Optional JSON payload
            
        Returns:
            Tuple of (response dict, status code)
        """
        logger.debug('API call: %s %s %s', api, path, json_object)
        
        if self._api_response_file_name:
            import json
            file_path = API_RESPONSE_BASE_PATH + self._api_response_file_name
            if os.path.exists(file_path):
                with open(file_path, 'r') as file:
                    return (json.load(file), 200)
        
        return ({}, 200)
