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
    CONF_NOTIFICATION_SWITCHES,
    DEFAULT_NOTIFICATION_SWITCHES,
    SERVICE_REFRESH_ALARMS
)
from homeassistant.helpers import entity_registry as er

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

    notification_switches = config_entry.options.get(
        CONF_NOTIFICATION_SWITCHES, DEFAULT_NOTIFICATION_SWITCHES
    )

    if notification_switches:
        # Load users first (needed for updating notifications for all users)
        load_users = await hass.async_add_executor_job(pyuiprotectalarms_manager.load_users)
        if load_users:
            _LOGGER.info("%d UIProtect users found", len(pyuiprotectalarms_manager.users))

        # Load notifications (non-blocking, continue even if it fails)
        load_notifications = await hass.async_add_executor_job(pyuiprotectalarms_manager.load_notifications)
        if load_notifications:
            _LOGGER.info("%d UIProtect notifications found", len(pyuiprotectalarms_manager.notifications))
            # Only clean up when the notification list loaded completely
            _async_remove_stale_entities(
                hass,
                config_entry,
                ("-push", "-email"),
                {
                    f"{notification_id}-{channel}"
                    for notification_id in pyuiprotectalarms_manager.notifications
                    for channel in ("push", "email")
                },
            )
        else:
            _LOGGER.warning("Unable to load notifications, continuing without notification controls")
    else:
        _LOGGER.info("Push/email notification switches disabled in options")
        _async_remove_notification_entities(hass, config_entry)

    # load_automations() raises on any error, so the alarm list is complete here:
    # remove switches of alarms that were deleted in UniFi Protect
    _async_remove_stale_entities(
        hass,
        config_entry,
        ("-Enabled",),
        {f"{automation_id}-Enabled" for automation_id in pyuiprotectalarms_manager.automations},
    )

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
            if notification_switches:
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

    # Apply changed options (e.g. notification switches on/off) right away
    config_entry.async_on_unload(config_entry.add_update_listener(_async_options_updated))

    return True


async def _async_options_updated(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Reload the integration when its options change."""
    await hass.config_entries.async_reload(config_entry.entry_id)


def _async_remove_stale_entities(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    suffixes: tuple[str, ...],
    valid_unique_ids: set[str],
) -> None:
    """Remove switches whose alarm/notification no longer exists in Protect.

    Only entries of this config entry whose unique_id ends with one of the
    given suffixes are considered, so the two switch types never affect
    each other.
    """
    registry = er.async_get(hass)
    for entry in er.async_entries_for_config_entry(registry, config_entry.entry_id):
        if (
            entry.domain == "switch"
            and entry.unique_id.endswith(suffixes)
            and entry.unique_id not in valid_unique_ids
        ):
            _LOGGER.info("Removing %s, it no longer exists in UniFi Protect", entry.entity_id)
            registry.async_remove(entry.entity_id)


def _async_remove_notification_entities(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Remove push/email switches left over from when they were enabled.

    Notification switches use the unique_id "<id>-push" / "<id>-email",
    alarm switches use "<id>-Enabled", so only notification switches match.
    """
    registry = er.async_get(hass)
    for entry in er.async_entries_for_config_entry(registry, config_entry.entry_id):
        if entry.domain == "switch" and entry.unique_id.endswith(("-push", "-email")):
            _LOGGER.info("Removing notification switch %s", entry.entity_id)
            registry.async_remove(entry.entity_id)

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
