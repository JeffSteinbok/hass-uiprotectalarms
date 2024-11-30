"""Config (and Options) flow for Uiprotectalarms integration."""
import logging
from typing import Any, Dict
from collections import OrderedDict
import voluptuous as vol

from .haimports import * # pylint: disable=W0401,W0614
from .const import (
    DOMAIN,
    CONF_AUTO_RECONNECT
)
from .pyuiprotectalarms import PyUIProtectAlarms

_LOGGER = logging.getLogger("uiprotectalarms")


class UiprotectalarmsFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Uiprotectalarms Custom config flow."""

    # The schema version of the entries that it creates
    # Home Assistant will call your migrate method if the version changes
    VERSION = 1

    def __init__(self) -> None:
        """Instantiate config flow."""
        self._username = None
        self._password = None
        self._host = None
        self._port = 443
        self.data_schema = OrderedDict()
        self.data_schema[vol.Required(CONF_USERNAME)] = str
        self.data_schema[vol.Required(CONF_PASSWORD)] = str
        self.data_schema[vol.Required(CONF_HOST)] = str

    @callback
    def _show_form(self, errors=None):
        """Show form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(self.data_schema),
            errors=errors if errors else {},
        )

    async def async_step_user(self, user_input=None):
        """Handle a flow start."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if not user_input:
            return self._show_form()

        self._username = user_input[CONF_USERNAME]
        self._password = user_input[CONF_PASSWORD]
        self._host = user_input[CONF_HOST]

        pyuiprotectalarms_manager = PyUIProtectAlarms(self._host,
                                                      self._username, 
                                                      self._password)
        authenticate = await self.hass.async_add_executor_job(pyuiprotectalarms_manager.authenticate)
        if not authenticate:
            return self._show_form(errors={"base": "invalid_auth"})

        return self.async_create_entry(
            title=self._host,
            data={CONF_USERNAME: self._username, 
                  CONF_PASSWORD: self._password,
                  CONF_HOST: self._host
                  }
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)

class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handles options flow for the component."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input: Dict[str, Any] = None) -> Dict[str, Any]:
        """Manage the options for the custom component."""
        errors: Dict[str, str] = {}

        _LOGGER.debug("Options Flow Step Init")
        if user_input is not None:
            _LOGGER.debug("UserInput is not none")
            return self.async_create_entry(title="", data=user_input)

        auto_reconnect = self.config_entry.options.get(CONF_AUTO_RECONNECT)
        if auto_reconnect is None:
            _LOGGER.debug("auto_reconnect not set, setting it to True")
            auto_reconnect = True

        options_schema = vol.Schema(
            {
                vol.Required(CONF_AUTO_RECONNECT, default=auto_reconnect): bool
            }
        )
        return self.async_show_form(
            step_id="init", data_schema=options_schema, errors=errors
        )
