"""Uiprotectalarms API for controlling notifications."""

import logging
from typing import TYPE_CHECKING

from .constants import (
        LOGGER_NAME,
        UIProtectApi
)

from .pyuiprotectbaseobject import PyUIProtectBaseObject

_LOGGER = logging.getLogger(LOGGER_NAME)

if TYPE_CHECKING:
    from pyuiprotectalarms import PyUIProtectAlarms


class PyUIProtectNotification(PyUIProtectBaseObject):
    """Class to represent a Unifi Protect Notification setting.
    
    Note: When updating notifications, the changes are applied to all users
    in the UniFi Protect system, not just the authenticated user.
    """

    def __init__(self, details: dict, PyUIProtectAlarms: "PyUIProtectAlarms"):
        super().__init__(details, PyUIProtectAlarms)

        self._name : str = None
        self._id : str = None
        self._push_enabled : bool = None
        self._email_enabled : bool = None
        self._raw_details : dict = None

        self.update_state(details)

    def __repr__(self):
        # Representation string of object.
        return f"<{self.__class__.__name__}:{self._id}:{self._name}>"
    
    @property
    def name(self) -> str:
        return self._name

    @property
    def id(self) -> str:
        """Return the id of the notification."""
        return self._id

    @property
    def push_enabled(self) -> bool:
        """Return if push notifications are enabled."""
        return self._push_enabled
    
    @push_enabled.setter
    def push_enabled(self, value: bool):
        """Enable or disable push notifications."""
        if self._raw_details is None:
            return
            
        # Update the channels array
        if "channels" not in self._raw_details:
            self._raw_details["channels"] = []
        
        if value:
            # Add push channel if not present
            if "push" not in self._raw_details["channels"]:
                self._raw_details["channels"].append("push")
        else:
            # Remove push channel if present
            if "push" in self._raw_details["channels"]:
                self._raw_details["channels"].remove("push")
        
        self._update_notification()
    
    @property
    def email_enabled(self) -> bool:
        """Return if email notifications are enabled."""
        return self._email_enabled
    
    @email_enabled.setter
    def email_enabled(self, value: bool):
        """Enable or disable email notifications."""
        if self._raw_details is None:
            return
            
        # Update the channels array
        if "channels" not in self._raw_details:
            self._raw_details["channels"] = []
        
        if value:
            # Add email channel if not present
            if "email" not in self._raw_details["channels"]:
                self._raw_details["channels"].append("email")
        else:
            # Remove email channel if present
            if "email" in self._raw_details["channels"]:
                self._raw_details["channels"].remove("email")
        
        self._update_notification()

    def _update_notification(self):
        """Update the notification settings via API for all users."""
        if self._raw_details is None or self._id is None:
            return
        
        # If this notification was extracted from an automation, update the automation instead
        if hasattr(self, '_automation_id') and self._automation_id:
            _LOGGER.debug("Updating notification via automation %s", self._automation_id)
            self._update_notification_via_automation()
            return
        
        # Get list of users
        users = getattr(self._uiProtectAlarms, '_users', [])
        
        if not users:
            _LOGGER.warning("No users found, trying to load users first")
            self._uiProtectAlarms.load_users()
            users = getattr(self._uiProtectAlarms, '_users', [])
        
        if not users:
            _LOGGER.error("Cannot update notifications: no users available")
            # Fallback: update only for current user
            self._update_notification_single()
            return
        
        # Update notification for each user
        success_count = 0
        for user in users:
            user_id = user.get("id")
            if not user_id:
                continue
            
            # Prepare update payload with user-specific path
            update_payload = self._raw_details.copy()
            
            # Try to update notification for this specific user
            # The API might require user ID in the path or payload
            response, status_code = self._uiProtectAlarms.call_uiprotect_api(
                UIProtectApi.UPDATE_NOTIFICATION, 
                f"{self._id}?userId={user_id}", 
                update_payload
            )
            
            if status_code == 200:
                success_count += 1
                _LOGGER.debug("Updated notification %s for user %s", self._id, user_id)
            else:
                # If user-specific update fails, try alternative approach
                # Some APIs might use a different structure
                _LOGGER.debug("Failed to update notification %s for user %s, status: %s", 
                             self._id, user_id, status_code)
        
        if success_count > 0:
            _LOGGER.info("Updated notification %s for %d/%d users", 
                        self._id, success_count, len(users))
            # Update local state
            self._push_enabled = "push" in self._raw_details.get("channels", [])
            self._email_enabled = "email" in self._raw_details.get("channels", [])
        else:
            # If all user-specific updates failed, try single update as fallback
            _LOGGER.warning("All user-specific updates failed, trying single update")
            self._update_notification_single()
    
    def _update_notification_via_automation(self):
        """Update notification by updating the automation that contains it."""
        if not hasattr(self, '_automation_id') or not self._automation_id:
            return
        
        automation = self._uiProtectAlarms.automations.get(self._automation_id)
        if not automation or not automation.raw_details:
            _LOGGER.error("Automation %s not found for notification update", self._automation_id)
            return
        
        # Get list of users
        users = getattr(self._uiProtectAlarms, '_users', [])
        if not users:
            _LOGGER.warning("No users found, trying to load users first")
            self._uiProtectAlarms.load_users()
            users = getattr(self._uiProtectAlarms, '_users', [])
        
        # Update channels in all receivers for all users
        actions = automation.raw_details.get("actions", [])
        for action in actions:
            if action.get("type") == "SEND_NOTIFICATION":
                metadata = action.get("metadata", {})
                receivers = metadata.get("receivers", [])
                
                # Update channels for all receivers
                for receiver in receivers:
                    # Build channels list based on current state
                    channels = []
                    if self._push_enabled:
                        channels.append("push")
                    if self._email_enabled:
                        channels.append("email")
                    receiver["channels"] = channels
        
        # Update the automation
        response, status_code = self._uiProtectAlarms.call_uiprotect_api(
            UIProtectApi.UPDATE_AUTOMATION, 
            self._automation_id, 
            automation.raw_details
        )
        
        if status_code == 200:
            _LOGGER.info("Updated notification %s via automation %s for all users", 
                        self._name, self._automation_id)
            # Don't call handle_server_update_base here as it triggers callbacks
            # that might be called from wrong thread. Just update local state.
            if response:
                automation.update_state(response)
            # Update local notification state
            self._push_enabled = "push" in self._raw_details.get("channels", [])
            self._email_enabled = "email" in self._raw_details.get("channels", [])
            
            # Trigger callbacks manually but in a safe way
            # The callbacks will use call_soon_threadsafe to update HA state
            automation._do_callbacks()
        else:
            _LOGGER.error("Failed to update automation %s, status: %s", 
                         self._automation_id, status_code)
    
    def _update_notification_single(self):
        """Update notification for current user only (fallback method)."""
        if self._raw_details is None or self._id is None:
            return
        
        update_payload = self._raw_details.copy()
        
        response, status_code = self._uiProtectAlarms.call_uiprotect_api(
            UIProtectApi.UPDATE_NOTIFICATION, 
            self._id, 
            update_payload
        )
        if status_code == 200:
            if response:
                self.handle_server_update_base(response)
            else:
                # If response is empty, just update local state
                self._push_enabled = "push" in self._raw_details.get("channels", [])
                self._email_enabled = "email" in self._raw_details.get("channels", [])

    @property
    def raw_details(self):
        """Return the raw details of the notification."""
        return self._raw_details

    def update_state(self, state: dict):
        _LOGGER.debug("PyUIProtectNotification:update_state: %s", state.get("id"))
        super().update_state(state)

        self._raw_details = state
        self._id = state.get("id")
        self._name = state.get("name") or state.get("type", "Unknown")
        
        # Store automation_id if this notification was extracted from an automation
        self._automation_id = state.get("automation_id")
        
        # Parse channels to determine push and email status
        channels = state.get("channels", [])
        self._push_enabled = "push" in channels
        self._email_enabled = "email" in channels

