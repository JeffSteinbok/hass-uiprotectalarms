"""Helper functions for PyUIProtectAlarms library."""

import logging
import time
import json
from typing import Optional, Union
import re
import requests
import jwt
from http.cookies import Morsel


from .constants import LOGGER_NAME
from .exceptions import *


_LOGGER = logging.getLogger(LOGGER_NAME)

API_TIMEOUT = 30

NUMERIC = Optional[Union[int, float, str]]


class Helpers:
    """Helper functions for PyUIProtectAlarms library."""
    
    shouldredact = False

    @classmethod
    def redactor(cls, stringvalue: str) -> str:
        """Redact sensitive strings from debug output."""
        if cls.shouldredact:
            stringvalue = re.sub(
                r"".join(
                    (
                        "(?i)",
                        '((?<=token": ")|',
                        '(?<=password": ")|',
                        '(?<=email": ")|',
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
        """Make API calls by passing endpoint, header and body."""
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
        """Make API calls by passing endpoint, header and body."""
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
        """Decode a token cookie if it is still valid."""
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
