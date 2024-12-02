"""UniFi Protect Server Wrapper."""
from http import HTTPStatus
from http.cookies import SimpleCookie
from pathlib import Path
from typing import Optional, Any, cast
from urllib.parse import SplitResult

import threading
import hashlib
import logging
import re
import time
import requests

import aiohttp
from yarl import URL
from .constants import (
    LOGGER_NAME,
    UIProtectApi,
    UIPROTECT_APIS,
    UIPROTECT_API_PATH,
    UIPROTECT_API_METHOD
)

from .helpers import Helpers
from .exceptions import (NvrError, NotAuthorized, BadRequest)
from .pyuiprotectautomation import PyUIProtectAutomation

TOKEN_COOKIE_MAX_EXP_SECONDS = 60

# retry timeout for thumbnails/heatmaps
RETRY_TIMEOUT = 10
PROTECT_APT_URLS = [
    "https://apt.artifacts.ui.com/dists/stretch/release/binary-arm64/Packages",
    "https://apt.artifacts.ui.com/dists/bullseye/release/binary-arm64/Packages",
]

_LOGGER = logging.getLogger(LOGGER_NAME)
_COOKIE_RE = re.compile(r"^set-cookie: ", re.IGNORECASE)

def get_user_hash(host: str, username: str) -> str:
    session = hashlib.sha256()
    session.update(host.encode("utf8"))
    session.update(username.encode("utf8"))
    return session.hexdigest()

class PyUIProtectAlarms:
    """Class to communicate with the Unifi Protect server."""
    _host: str
    _port: int
    _username: str
    _password: str
    _verify_ssl: bool

    _is_authenticated: bool = False
    _last_token_cookie: str = None
    _last_token_cookie_decode: dict[str, Any] | None = None
    _last_csrf_token: str = None
    _cookiename = "TOKEN"

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
    ) -> None:
        self._auth_lock = threading.Lock()
        self._host = host
        self._port = 443

        self._username = username
        self._password = password
        
        self._automation_rule_prefix = None
        self._automations : dict[str, PyUIProtectAutomation] = {}

        self._update_url()

    @property
    def automation_rule_prefix(self):
        """For filtering automations by name."""
        return self._automation_rule_prefix
    
    @automation_rule_prefix.setter
    def automation_rule_prefix(self, value: str):
        """For filtering automations by name."""
        self._automation_rule_prefix = value

    @property
    def automations(self) -> dict[PyUIProtectAutomation]:
        """Return the automations."""
        return self._automations

    def _update_cookiename(self, cookie: SimpleCookie) -> None:
        if "UOS_TOKEN" in cookie:
            self._cookiename = "UOS_TOKEN"

    def _update_url(self) -> None:
        """Updates the url after changing _host or _port."""
        if self._port != 443:
            self._url = URL(f"https://{self._host}:{self._port}")
        else:
            self._url = URL(f"https://{self._host}")

        self.base_url = str(self._url)

    def _raise_for_status(
        self, response: aiohttp.ClientResponse, raise_exception: bool = True
    ) -> None:
        """Raise an exception based on the response status."""
        url = response.url
        reason = get_response_reason(response)
        msg = "Request failed: %s - Status: %s - Reason: %s"
        status = response.status

        if raise_exception:
            if status in {
                HTTPStatus.UNAUTHORIZED.value,
                HTTPStatus.FORBIDDEN.value,
            }:
                raise NotAuthorized(msg % (url, status, reason))
            elif status == HTTPStatus.TOO_MANY_REQUESTS.value:
                _LOGGER.debug("Too many requests - Login is rate limited: %s", response)
                raise NvrError(msg % (url, status, reason))
            elif (
                status >= HTTPStatus.BAD_REQUEST.value
                and status < HTTPStatus.INTERNAL_SERVER_ERROR.value
            ):
                raise BadRequest(msg % (url, status, reason))
            raise NvrError(msg % (url, status, reason))

        _LOGGER.debug(msg, url, status, reason)

    def ensure_authenticated(self) -> None:
        """Ensure we are authenticated."""
        if self.is_authenticated() is False:
            self.authenticate()
    
    def call_uiprotect_api(self, api: str, path:str = None, json_object: Optional[dict] = None) -> tuple[dict, int]:
        """Call the UIProtect API. This is used for login and the initial device list and states as well
           as device settings."""
        _LOGGER.debug("Calling UIProtect API: {%s}", api)
        _LOGGER.debug("Calling UIProtect API - path={%s}", path)

        if json_object is None:
            json_object = {}

        if (api == UIProtectApi.LOGIN):
            response_obj = Helpers.call_api(
                self.base_url,
                UIPROTECT_APIS[api][UIPROTECT_API_PATH],
                UIPROTECT_APIS[api][UIPROTECT_API_METHOD],
                json_object,
                None,
            )
            if (response_obj.status_code == 200):
                # Unfortunate hack here to set the last token cookie here...
                self._update_last_token_cookie(response_obj)
                self._is_authenticated = True
                return response_obj.json(), response_obj.status_code
        else:
            full_path = UIPROTECT_APIS[api][UIPROTECT_API_PATH]
            if (path is not None):
                full_path = f"{full_path}/{path}"
                _LOGGER.debug("call_uiprotect_api: full_path={%s}", full_path)

            return Helpers.call_json_api(
                self.base_url,
                full_path,
                UIPROTECT_APIS[api][UIPROTECT_API_METHOD],
                json_object,
                {"Cookie": f"{self._cookiename}={self._last_token_cookie}",
                 "X-CSRF-Token": self._last_csrf_token},
        )


    def authenticate(self) -> bool:
        """Authenticate and get a token."""
        if self._auth_lock.locked():
            # If an auth is already in progress
            # do not start another one
            with self._auth_lock:
                return

        with self._auth_lock:
            auth = {
                "username": self._username,
                "password": self._password,
                "rememberMe": True,
            }

            response, status_code  = self.call_uiprotect_api(UIProtectApi.LOGIN, json_object=auth)
            if status_code == 200:
                self._is_authenticated = True
                _LOGGER.debug("Authenticated successfully!")
            else:
                self._raise_for_status(response, True)

        return self._is_authenticated
            
    def load_automations(self) -> bool:
        """Load automations from the Unifi Protect API."""
        _LOGGER.debug("PyUIProtectAlarms: load_automations")

        response, status_code  = self.call_uiprotect_api(UIProtectApi.GET_AUTOMATIONS)
        if status_code != 200:  
            self._raise_for_status(response, True)


        for automation_details in response:
            automation_id : str = automation_details.get("id")
            automation_obj : PyUIProtectAutomation = self._automations.get(automation_id) or None
            _LOGGER.debug("PyUIProtectAlarms: load_automations: automation_id=%s, automation_obj=%s", automation_id, automation_obj)
            if (automation_obj is None):
                automation_obj = PyUIProtectAutomation(automation_details, self)

                if (self.automation_rule_prefix is None or automation_obj.name.startswith(self.automation_rule_prefix)):
                    self._automations[automation_obj.id] = automation_obj

            else:
                automation_obj.handle_server_update_base(automation_details)



        return True


    def _update_last_token_cookie(self, response: requests.Response) -> None:
        """Update the last token cookie."""

        csrf_token = response.headers.get("x-csrf-token")
        if (csrf_token is not None):
            self._last_csrf_token = csrf_token

        if (
            token_cookie := response.cookies.get(self._cookiename)
        ) and token_cookie != self._last_token_cookie:
            self._last_token_cookie = token_cookie
            self._last_token_cookie_decode = None


    def is_authenticated(self) -> bool:
        """Check to see if we are already authenticated."""
        if self._is_authenticated is False:
            return False

        if self._last_token_cookie is None:
            return False

        # Lazy decode the token cookie
        if self._last_token_cookie and self._last_token_cookie_decode is None:
            self._last_token_cookie_decode = Helpers.decode_token_cookie(self._last_token_cookie)

        if ( self._last_token_cookie_decode is None
             or "exp" not in self._last_token_cookie_decode):
            return False

        token_expires_at = cast(int, self._last_token_cookie_decode["exp"])
        max_expire_time = time.time() + TOKEN_COOKIE_MAX_EXP_SECONDS

        # Format max_expire_time as a string for logging.  
        # Is there a better lazy way to do this?
        token_expires_at_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(token_expires_at))
        max_expire_time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(max_expire_time))
        
        _LOGGER.debug("PyUIProtectAlarms:is_authenticated: Token valid until (%s)", token_expires_at_str)
        _LOGGER.debug("PyUIProtectAlarms:is_authenticated: Max expire time (%s)", max_expire_time_str)

        return token_expires_at >= max_expire_time
