"""UIprotectalarms HomeAssistant Integration."""

import logging
import time

from .haimports import *  # pylint: disable=W0401,W0614
from .const import (
    LOGGER,
    DOMAIN,
    PYUIPROTECTALARMS_MANAGER,
    UIPROTECTALARMS_PLATFORMS,
    CONF_RULE_PREFIX
)

_LOGGER = logging.getLogger(LOGGER)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    "HomeAssistant EntryPoint"
    _LOGGER.debug("async_setup_entry")

    _LOGGER.debug(config_entry.data.get(CONF_USERNAME))
    host = config_entry.data.get(CONF_HOST)
    username = config_entry.data.get(CONF_USERNAME)
    password = config_entry.data.get(CONF_PASSWORD)
    rule_prefix = config_entry.options.get(CONF_RULE_PREFIX)

    from .pyuiprotectalarms import PyUIProtectAlarms  # pylint: disable=C0415

    pyuiprotectalarms_manager = PyUIProtectAlarms(host, username, password)
    pyuiprotectalarms_manager.automation_rule_prefix = rule_prefix

    authenticate = await hass.async_add_executor_job(pyuiprotectalarms_manager.authenticate)

    if not authenticate:
        _LOGGER.error("Unable to login to the UIProtect server")
        return False

    load_automations = await hass.async_add_executor_job(pyuiprotectalarms_manager.load_automations)

    if not load_automations:
        _LOGGER.error("Unable to load automation list from the uiprotectalarms server")
        return False

    _LOGGER.debug("Checking for supported installed device types")

    _LOGGER.info("%d UIProtect automations found", len(pyuiprotectalarms_manager.automations))

    platforms = set()
    platforms.add(Platform.SWITCH)

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][PYUIPROTECTALARMS_MANAGER] = pyuiprotectalarms_manager
    hass.data[DOMAIN][UIPROTECTALARMS_PLATFORMS] = platforms

    _LOGGER.debug("Platforms are: %s", platforms)

    await hass.config_entries.async_forward_entry_setups(config_entry, platforms)

    async def _update_listener(hass: HomeAssistant, config_entry: ConfigEntry):
        """Handle options update."""
        await hass.config_entries.async_reload(config_entry.entry_id)

    ## Create update listener
    config_entry.async_on_unload(config_entry.add_update_listener(_update_listener))

    return True

async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    pyuiprotectalarms_manager = hass.data[DOMAIN][PYUIPROTECTALARMS_MANAGER]
    if unload_ok := await hass.config_entries.async_unload_platforms(
        config_entry,
        hass.data[DOMAIN][UIPROTECTALARMS_PLATFORMS],
    ):
        hass.data.pop(DOMAIN)

    return unload_ok
