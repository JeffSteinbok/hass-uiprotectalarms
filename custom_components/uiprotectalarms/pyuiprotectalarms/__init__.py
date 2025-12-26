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
from .pyuiprotectnotification import PyUIProtectNotification

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
        self._notifications : dict[str, PyUIProtectNotification] = {}
        self._users : list[dict] = []

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

    @property
    def notifications(self) -> dict[PyUIProtectNotification]:
        """Return the notifications."""
        return self._notifications

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

    def load_users(self) -> bool:
        """Load list of users from the Unifi Protect API."""
        _LOGGER.debug("PyUIProtectAlarms: load_users")

        response, status_code = self.call_uiprotect_api(UIProtectApi.GET_USERS)
        if status_code != 200:  
            _LOGGER.warning("Unable to load users, status code: %s", status_code)
            return False

        if not isinstance(response, list):
            _LOGGER.warning("Users response is not a list: %s", type(response))
            return False

        self._users = response
        _LOGGER.info("Loaded %d users from UniFi Protect", len(self._users))
        return True

    def load_notifications(self) -> bool:
        """Load notifications from the Unifi Protect API.
        
        Note: This loads notification settings for the authenticated user.
        When updating, we will update for all users.
        
        First tries the dedicated notifications endpoint, if that fails,
        extracts notifications from automations.
        """
        _LOGGER.debug("PyUIProtectAlarms: load_notifications")

        # First, try to load users if not already loaded
        if not self._users:
            self.load_users()

        # Try dedicated notifications endpoint first
        response, status_code = self.call_uiprotect_api(UIProtectApi.GET_NOTIFICATIONS)
        _LOGGER.debug("Notifications endpoint response: status_code=%s, response_type=%s", status_code, type(response))
        
        if status_code == 200 and isinstance(response, list) and len(response) > 0:
            _LOGGER.info("Loaded %d notifications from dedicated endpoint", len(response))
            for notification_details in response:
                notification_id = notification_details.get("id")
                if notification_id is None:
                    notification_id = notification_details.get("type") or notification_details.get("name", "unknown")
                
                notification_obj = self._notifications.get(notification_id) or None
                if notification_obj is None:
                    notification_obj = PyUIProtectNotification(notification_details, self)
                    self._notifications[notification_obj.id] = notification_obj
                else:
                    notification_obj.handle_server_update_base(notification_details)
            return True
        
        # If dedicated endpoint doesn't work, extract from automations
        _LOGGER.info("Notifications endpoint not available (status_code=%s), extracting from automations", status_code)
        return self._extract_notifications_from_automations()
    
    def _extract_notifications_from_automations(self) -> bool:
        """Extract notification settings from automations."""
        _LOGGER.debug("Extracting notifications from automations")
        
        if not self._automations:
            _LOGGER.warning("No automations available to extract notifications from")
            return False
        
        # Group automations by notification type
        notification_types = {}
        
        for automation in self._automations.values():
            if not hasattr(automation, 'raw_details') or not automation.raw_details:
                _LOGGER.debug("Automation %s has no raw_details, skipping", automation.name)
                continue
                
            automation_name = automation.name
            _LOGGER.debug("Processing automation: %s", automation_name)
            
            # Extract notification actions from automation
            actions = automation.raw_details.get("actions", [])
            _LOGGER.debug("Automation %s has %d actions", automation_name, len(actions))
            
            for action in actions:
                if action.get("type") == "SEND_NOTIFICATION":
                    _LOGGER.debug("Found SEND_NOTIFICATION action in automation %s", automation_name)
                    metadata = action.get("metadata", {})
                    receivers = metadata.get("receivers", [])
                    
                    # Collect all channels from all receivers
                    all_channels = set()
                    for receiver in receivers:
                        receiver_channels = receiver.get("channels", [])
                        all_channels.update(receiver_channels)
                    
                    channels = list(all_channels) if all_channels else []
                    _LOGGER.debug("Automation %s has channels: %s", automation_name, channels)
                    
                    # Use automation name as notification type
                    notification_type = automation_name
                    
                    if notification_type not in notification_types:
                        notification_types[notification_type] = {
                            "id": automation.id,
                            "name": notification_type,
                            "type": notification_type,
                            "channels": channels.copy() if channels else [],
                            "automation_id": automation.id  # Store automation ID for updates
                        }
                    else:
                        # Merge channels if notification type already exists
                        existing_channels = set(notification_types[notification_type]["channels"])
                        existing_channels.update(channels)
                        notification_types[notification_type]["channels"] = list(existing_channels)
        
        # Create notification objects
        for notification_type, notification_data in notification_types.items():
            _LOGGER.debug("Creating notification object for: %s with channels: %s", 
                         notification_type, notification_data["channels"])
            notification_obj = self._notifications.get(notification_type) or None
            if notification_obj is None:
                notification_obj = PyUIProtectNotification(notification_data, self)
                self._notifications[notification_obj.id] = notification_obj
            else:
                notification_obj.handle_server_update_base(notification_data)
        
        _LOGGER.info("Extracted %d notification types from automations: %s", 
                    len(notification_types), list(notification_types.keys()))
        return len(notification_types) > 0

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
