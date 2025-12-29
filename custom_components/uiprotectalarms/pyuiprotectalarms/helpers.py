"""Helper functions for PyUIProtectAlarms library."""

import json
import logging
import re
from typing import Optional, Union

import jwt
import requests

from .exceptions import *

# Initialize logger using standard Python logging pattern
_LOGGER = logging.getLogger(__name__)

# Timeout for API calls in seconds
API_TIMEOUT = 30

# Type alias for numeric values
NUMERIC = Optional[Union[int, float, str]]


class Helpers:
    """Helper class providing utility functions for PyUIProtectAlarms library.
    
    Includes methods for making HTTP API calls, redacting sensitive information,
    and decoding authentication tokens.
    """
    
    # Flag to enable/disable redaction of sensitive information in logs
    shouldredact = False

    @classmethod
    def redactor(cls, stringvalue: str) -> str:
        """Redact sensitive information from strings for safe logging.
        
        Replaces sensitive fields (tokens, passwords, emails, etc.) with '##_REDACTED_##'
        when shouldredact is enabled.
        
        Args:
            stringvalue: The string containing potentially sensitive information
            
        Returns:
            The string with sensitive values redacted if shouldredact is True
        """
        if cls.shouldredact:
            stringvalue = re.sub(
                r"".join(
                    (
                        "(?i)",
                        '((?<=token": ")|',
                        '(?<=password": ")|',
                        '(?<=email": ")|',
                        '(?<=username": ")|',
                        '(?<=tk": ")|',
                        '(?<=accountId": ")|',
                        '(?<=authKey": ")|',
                        '(?<=uuid": ")|',
                        '(?<=cid": ")|',
                        '(?<=authorization": "))',
                        '[^"]+',
                    )
                ),
                "##_REDACTED_##",
                stringvalue,
            )
        return stringvalue

    @staticmethod
    def call_api(
        url: str,
        api: str,
        method: str,
        json_object: Optional[dict] = None,
        headers: Optional[dict] = None,
    ) -> requests.Response:
        """Make HTTP API calls to UniFi Protect.
        
        Supports GET, POST, PUT, and PATCH methods. Logs request details at debug level.
        
        Args:
            url: Base URL of the API server
            api: API endpoint path
            method: HTTP method (get, post, put, patch)
            json_object: Optional JSON data to send with the request
            headers: Optional HTTP headers
            
        Returns:
            requests.Response object from the API call
            
        Raises:
            requests.exceptions.RequestException: If the request fails
        """
        response_object = None
        try:
            _LOGGER.debug("=======call_api=============================")
            _LOGGER.debug("[%s] calling '%s' api", method, api)
            _LOGGER.debug("API call URL: \n  %s%s", url, api)
            _LOGGER.debug(
                "API call headers: \n  %s", Helpers.redactor(
                    json.dumps(headers))
            )
            _LOGGER.debug(
                "API call json: \n  %s", Helpers.redactor(
                    json.dumps(json_object))
            )
            if method.lower() == "get":
                response_object = requests.get(
                    url + api,
                    headers=headers,
                    params={**json_object},
                    timeout=API_TIMEOUT,
                    verify = False
                )
            elif method.lower() == "post":
                response_object = requests.post(
                    url + api,
                    json=json_object,
                    headers=headers,
                    params={},
                    timeout=API_TIMEOUT,
                    verify = False
                )
            elif method.lower() == "put":
                response_object = requests.put(
                    url + api, json=json_object, headers=headers, timeout=API_TIMEOUT
                )
            elif method.lower() == "patch":
                response_object = requests.patch(
                    url + api, 
                    json=json_object, 
                    headers=headers, 
                    timeout=API_TIMEOUT,
                    verify=False
                )                
        except requests.exceptions.RequestException as exception:
            _LOGGER.debug(exception)
            raise exception
        else:
            if response_object.status_code != 200:
                _LOGGER.debug("Unable to fetch %s%s", url, api)
        return response_object
    
    @staticmethod
    def call_json_api(
        url: str,
        api: str,
        method: str,
        json_object: Optional[dict] = None,
        headers: Optional[dict] = None,
    ) -> tuple[dict, int]:
        """Make HTTP API calls and parse JSON response.
        
        Wrapper around call_api that extracts and parses JSON response data.
        
        Args:
            url: Base URL of the API server
            api: API endpoint path
            method: HTTP method (get, post, put, patch)
            json_object: Optional JSON data to send with the request
            headers: Optional HTTP headers
            
        Returns:
            Tuple of (parsed JSON response dict or None, HTTP status code)
        """
        response_object = None
        response = None
        status_code = 0
        try:
            response_object = Helpers.call_api(url, api, method, json_object, headers)
        except requests.exceptions.RequestException as exception:
            _LOGGER.debug(exception)
        else:
            if response_object.status_code == 200:
                status_code = 200
                if response_object.content:
                    response = response_object.json()
                    _LOGGER.debug(
                        "API response: \n\n  %s \n ",
                        Helpers.redactor(json.dumps(response)),
                    )
            else:
                _LOGGER.debug("Unable to fetch %s%s", url, api)
        return response, status_code

    @staticmethod
    def decode_token_cookie(token_cookie: str) -> dict[str, any] | None:
        """Decode and validate a JWT authentication token.
        
        Decodes the token without signature verification but checks expiration.
        
        Args:
            token_cookie: JWT token string to decode
            
        Returns:
            Decoded token payload as dict if valid, None if expired or invalid
        """
        try:
            return jwt.decode(
                token_cookie,
                options={"verify_signature": False, "verify_exp": True},
            )
        except jwt.ExpiredSignatureError:
            _LOGGER.debug("Authentication token has expired.")
            return None
        except Exception as broad_ex:
            _LOGGER.debug("Authentication token decode error: %s", broad_ex)
            return None
