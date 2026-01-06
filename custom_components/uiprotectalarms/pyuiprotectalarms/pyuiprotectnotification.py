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
        
        # Update local state first
        self._push_enabled = value
        
        # Update via automation if available
        self._update_notification_channel("push", value)
    
    @property
    def email_enabled(self) -> bool:
        """Return if email notifications are enabled."""
        return self._email_enabled
    
    @email_enabled.setter
    def email_enabled(self, value: bool):
        """Enable or disable email notifications."""
        if self._raw_details is None:
            return
        
        # Update local state first
        self._email_enabled = value
        
        # Update via automation if available
        self._update_notification_channel("email", value)

    def _update_notification_channel(self, channel: str, enabled: bool):
        """Update a specific notification channel (push or email) for all users."""
        if self._raw_details is None or self._id is None:
            return
        
        # If this notification was extracted from an automation, update the automation instead
        if hasattr(self, '_automation_id') and self._automation_id:
            _LOGGER.debug("Updating notification channel %s=%s via automation %s", 
                         channel, enabled, self._automation_id)
            self._update_notification_via_automation(channel, enabled)
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
    
    def _update_notification_via_automation(self, channel: str, enabled: bool):
        """Update notification channel by updating the automation that contains it."""
        if not hasattr(self, '_automation_id') or not self._automation_id:
            return
        
        automation = self._uiProtectAlarms.automations.get(self._automation_id)
        if not automation or not automation.raw_details:
            _LOGGER.error("Automation %s not found for notification update", self._automation_id)
            return
        
        _LOGGER.debug("Updating channel %s to %s in automation %s", channel, enabled, self._automation_id)
        
        # First, read current state from automation to preserve other channels
        # This ensures we don't lose the state of the other channel
        current_push_state = False
        current_email_state = False
        
        actions = automation.raw_details.get("actions", [])
        for action in actions:
            if action.get("type") == "SEND_NOTIFICATION":
                metadata = action.get("metadata", {})
                receivers = metadata.get("receivers", [])
                
                # Read current state from first receiver (they should all be the same)
                if receivers:
                    current_channels = receivers[0].get("channels", [])
                    if isinstance(current_channels, list):
                        current_push_state = "push" in current_channels
                        current_email_state = "email" in current_channels
                        _LOGGER.debug("Current state from automation: push=%s, email=%s", 
                                     current_push_state, current_email_state)
                    break
        
        # Now update with the new value for the specific channel, preserving the other
        if channel == "push":
            new_push_state = enabled
            new_email_state = current_email_state  # Preserve email state
        else:  # channel == "email"
            new_push_state = current_push_state  # Preserve push state
            new_email_state = enabled
        
        _LOGGER.debug("New state after update: push=%s, email=%s", new_push_state, new_email_state)
        
        # Update channels in all receivers for all users
        for action in actions:
            if action.get("type") == "SEND_NOTIFICATION":
                metadata = action.get("metadata", {})
                receivers = metadata.get("receivers", [])
                
                # Update channels for all receivers with the correct state
                for receiver in receivers:
                    channels = []
                    if new_push_state:
                        channels.append("push")
                    if new_email_state:
                        channels.append("email")
                    
                    receiver["channels"] = channels
                    _LOGGER.debug("Updated receiver %s with channels: %s", receiver.get("user"), channels)
        
        # Log the automation details before update
        _LOGGER.debug("Updating automation %s with details: %s", 
                     self._automation_id, 
                     str(automation.raw_details)[:500])  # Limit log size
        
        # Update the automation
        response, status_code = self._uiProtectAlarms.call_uiprotect_api(
            UIProtectApi.UPDATE_AUTOMATION, 
            self._automation_id, 
            automation.raw_details
        )
        
        if status_code == 200:
            _LOGGER.info("Successfully updated notification %s (channel %s=%s) via automation %s for all users", 
                        self._name, channel, enabled, self._automation_id)
            # Don't call handle_server_update_base here as it triggers callbacks
            # that might be called from wrong thread. Just update local state.
            if response:
                automation.update_state(response)
                # Update local notification state from response
                # Extract channels from the response
                actions = response.get("actions", [])
                for action in actions:
                    if action.get("type") == "SEND_NOTIFICATION":
                        metadata = action.get("metadata", {})
                        receivers = metadata.get("receivers", [])
                        if receivers:
                            # Get channels from first receiver (they should all be the same)
                            updated_channels = receivers[0].get("channels", [])
                            self._push_enabled = "push" in updated_channels
                            self._email_enabled = "email" in updated_channels
                            _LOGGER.debug("Updated local state: push=%s, email=%s", 
                                         self._push_enabled, self._email_enabled)
                            break
            else:
                # If no response, just keep the local state we set
                _LOGGER.debug("No response from API, keeping local state: push=%s, email=%s", 
                             self._push_enabled, self._email_enabled)
        else:
            _LOGGER.error("Failed to update automation %s, status: %s, response: %s", 
                         self._automation_id, status_code, response)
    
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

