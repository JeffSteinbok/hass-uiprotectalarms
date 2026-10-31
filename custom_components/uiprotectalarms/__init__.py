"""UIprotectalarms HomeAssistant Integration."""

import logging
import time
from datetime import timedelta

from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers.event import async_track_time_interval

from .haimports import *  # pylint: disable=W0401,W0614
from .const import (
    LOGGER,
    DOMAIN,
    PYUIPROTECTALARMS_MANAGER,
    UIPROTECTALARMS_PLATFORMS,
    CONF_RULE_PREFIX,
    SERVICE_REFRESH_ALARMS
)

_LOGGER = logging.getLogger(LOGGER)

# How often alarm states are re-read from Protect
SYNC_INTERVAL = timedelta(minutes=5)


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

    from .pyuiprotectalarms.exceptions import UnifiProtectError  # pylint: disable=C0415

    try:
        await hass.async_add_executor_job(pyuiprotectalarms_manager.authenticate)
        await hass.async_add_executor_job(pyuiprotectalarms_manager.load_automations)
    except UnifiProtectError as err:
        # HA retries the setup later instead of leaving the integration dead
        raise ConfigEntryNotReady(f"UniFi Protect not reachable: {err}") from err

    _LOGGER.info("%d UIProtect automations found", len(pyuiprotectalarms_manager.automations))

    # Load users first (needed for updating notifications for all users)
    load_users = await hass.async_add_executor_job(pyuiprotectalarms_manager.load_users)
    if load_users:
        _LOGGER.info("%d UIProtect users found", len(pyuiprotectalarms_manager.users))
    
    # Load notifications (non-blocking, continue even if it fails)
    load_notifications = await hass.async_add_executor_job(pyuiprotectalarms_manager.load_notifications)
    if load_notifications:
        _LOGGER.info("%d UIProtect notifications found", len(pyuiprotectalarms_manager.notifications))
    else:
        _LOGGER.warning("Unable to load notifications, continuing without notification controls")

    platforms = set()
    platforms.add(Platform.SWITCH)

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][PYUIPROTECTALARMS_MANAGER] = pyuiprotectalarms_manager
    hass.data[DOMAIN][UIPROTECTALARMS_PLATFORMS] = platforms

    _LOGGER.debug("Platforms are: %s", platforms)

    await hass.config_entries.async_forward_entry_setups(config_entry, platforms)

    async def async_refresh_automations(service: ServiceCall) -> None:
        """Refresh the automations, notifications, and users."""
        _LOGGER.debug("Refreshing automations, notifications, and users")
        try:
            await hass.async_add_executor_job(pyuiprotectalarms_manager.load_automations)
            await hass.async_add_executor_job(pyuiprotectalarms_manager.load_users)
            await hass.async_add_executor_job(pyuiprotectalarms_manager.load_notifications)
        except UnifiProtectError as err:
            raise HomeAssistantError(f"UniFi Protect refresh failed: {err}") from err

    hass.services.async_register(
        DOMAIN, SERVICE_REFRESH_ALARMS, async_refresh_automations
    )

    async def _async_periodic_sync(_now) -> None:
        """Keep HA in sync with changes made directly in Protect."""
        try:
            await hass.async_add_executor_job(pyuiprotectalarms_manager.load_automations)
        except UnifiProtectError as err:
            _LOGGER.warning("Periodic UniFi Protect alarm sync failed: %s", err)

    config_entry.async_on_unload(
        async_track_time_interval(hass, _async_periodic_sync, SYNC_INTERVAL)
    )

    return True

async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if DOMAIN not in hass.data:
        return True
    
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry,
        hass.data[DOMAIN][UIPROTECTALARMS_PLATFORMS],
    )
    
    if unload_ok:
        hass.services.async_remove(DOMAIN, SERVICE_REFRESH_ALARMS)
        hass.data.pop(DOMAIN)

    return unload_ok
