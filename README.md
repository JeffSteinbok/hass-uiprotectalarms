# HomeAssistant Plugin for Enabling/Disabling Unifi Protect Alarms

[![CI Validation](https://github.com/JeffSteinbok/hass-uiprotectalarms/actions/workflows/ci.yaml/badge.svg)](https://github.com/JeffSteinbok/hass-uiprotectalarms/actions/workflows/ci.yaml)
[![Release Automation](https://github.com/JeffSteinbok/hass-uiprotectalarms/actions/workflows/release.yaml/badge.svg)](https://github.com/JeffSteinbok/hass-uiprotectalarms/actions/workflows/release.yaml)

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)

This integration is heavily based on the work done on the official (unofficial) Unifi Protect Python library here:  https://github.com/uilibs/uiprotect.

I wanted a quick solution for enabling and disabling alarms from HomeAssistant, and I didn't have the time at the moment to
integrate it properly into the official library so I put this together.

Some key notes you should be aware of...
* This integration simply exposes all Alarms as switches and you can enable/disable them.
* This integration also doesn't automatically keep entities in sync with Unifi Protect. You'll have to manually set that up using the **Refresh** service exposed
by this integration.
* Will append *(Disabled)* to all Alarms it disables, so you can see in the UI Protect all.

## Table of Contents
- [Installation](#installation)
- [Debugging](#debugging)
- [To Do](#todo)

<a name="installation"></a>
## Installation

### HACS (Recommended)

1. Add this repository to HACS *AS A CUSTOM REPOSITORY*.
1. Search for *jeffsteinbok/hass-uiprotectalarms*, and choose type *Integration*. 
1. Reboot Home Assistant and configure from the "Add Integration" flow.

### Manually
Copy the `uiprotectalarms` directory into your `/config/custom_components` directory, then restart your HomeAssistant Core.

<a name="debugging"></a>
## Debugging
Idealy, use the Diagnostics feature in HomeAssistant to get diagnostics from the integration. Sensitive info **WILL NOT BE REDACTED** so be careful.

This integration logs to two loggers as shown below. To get verbose logs, change the log level.  Please have logs handy if you're reaching out for help.

```
logger:
    logs:
        custom_components.uiprotectalarms: debug
```

<a name="todo"></a>
## Future Ideas
* Actually keep entities in sync
* Figure out how to have the integration image work. I don't want to put it in the same domain as the real Unifi Protect integration.
