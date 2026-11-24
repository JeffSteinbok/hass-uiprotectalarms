"""Helper functions for PyUIProtectAlarms library."""

import json
import logging
import re
from typing import Optional, Union

import jwt
import requests
import urllib3

from .exceptions import *

# Initialize logger using standard Python logging pattern
_LOGGER = logging.getLogger(__name__)

# UniFi Protect controllers typically use self-signed certificates, so
# certificate verification is intentionally disabled for all API calls.
# Suppress the resulting InsecureRequestWarning to avoid log spam.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Timeout for API calls in seconds
API_TIMEOUT = 30

# Type alias for numeric values
NUMERIC = Optional[Union[int, float, str]]


class Helpers:
    """Helper class providing utility functions for PyUIProtectAlarms library.
    
    Includes methods for making HTTP API calls, redacting sensitive information,
    and decoding authentication tokens.
    """
    
    # Flag to also redact personal details (email, username, ids) in logs.
    # Credentials (cookies, CSRF/auth tokens, passwords) are always redacted,
    # whatever this flag says.
    shouldredact = False

    REDACTED = "##_REDACTED_##"

    # Header names, or field names in a JSON body, that carry credentials.
    # Matched case-insensitively anywhere in the name, so "Cookie",
    # "Set-Cookie", "X-CSRF-Token", "Authorization", "csrfToken" and
    # "accessToken" all match.
    _SECRET_KEY_RE = re.compile(
        r"token|password|passwd|secret|cookie|csrf|authorization|authkey|api[_-]?key|^tk$",
        re.IGNORECASE,
    )

    # Personal details, only redacted when shouldredact is enabled.
    _PERSONAL_KEYS = frozenset(("email", "username", "accountid", "uuid", "cid"))

    # A "key": "string value" pair inside a JSON string.
    _JSON_STRING_FIELD_RE = re.compile(r'"((?:[^"\\]|\\.)*)"(\s*:\s*)"((?:[^"\\]|\\.)*)"')

    @classmethod
    def _should_redact_key(cls, key) -> bool:
        """Return True if the value stored under this key must not be logged."""
        if not isinstance(key, str):
            return False
        if cls._SECRET_KEY_RE.search(key):
            return True
        return cls.shouldredact and key.lower() in cls._PERSONAL_KEYS

    @classmethod
    def redact_data(cls, data):
        """Return a copy of request headers or a JSON body that is safe to log.

        Values under credential keys are always replaced with '##_REDACTED_##',
        personal details only when shouldredact is enabled. Nested dicts and
        lists are handled; the input is not modified.
        """
        if isinstance(data, dict):
            return {
                key: cls.REDACTED if cls._should_redact_key(key) else cls.redact_data(value)
                for key, value in data.items()
            }
        if isinstance(data, (list, tuple)):
            return [cls.redact_data(item) for item in data]
        return data

    @classmethod
    def redactor(cls, stringvalue: str) -> str:
        """Redact sensitive information from a JSON string for safe logging.

        String values of credential fields are always replaced with
        '##_REDACTED_##'; personal details (email, username, ids) only when
        shouldredact is enabled. Prefer redact_data() on the object before
        serializing it, which also catches non-string values.

        Args:
            stringvalue: The string containing potentially sensitive information

        Returns:
            The string with sensitive values redacted
        """

        def _replace(match: re.Match) -> str:
            if cls._should_redact_key(match.group(1)):
                return f'"{match.group(1)}"{match.group(2)}"{cls.REDACTED}"'
            return match.group(0)

        return cls._JSON_STRING_FIELD_RE.sub(_replace, stringvalue)

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
                "API call headers: \n  %s", json.dumps(Helpers.redact_data(headers))
            )
            _LOGGER.debug(
                "API call json: \n  %s", json.dumps(Helpers.redact_data(json_object))
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
                    url + api,
                    json=json_object,
                    headers=headers,
                    timeout=API_TIMEOUT,
                    verify=False
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
                        json.dumps(Helpers.redact_data(response)),
                    )
            else:
                # Return the real status code (e.g. 401) so callers can re-authenticate
                status_code = response_object.status_code
                _LOGGER.debug("Unable to fetch %s%s (status %s)", url, api, status_code)
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
