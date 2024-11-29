"""Constants for the UIProtect Alarms integration."""
from enum import StrEnum

LOGGER_NAME = "pyuiprotectalarms"

UIPROTECT_API_PATH = "path"
UIPROTECT_API_METHOD = "method"

class UIProtectApi(StrEnum):
    """UIProtect API endpoints."""
    LOGIN = "login"
    GET_AUTOMATIONS = "get_automations"
    UPDATE_AUTOMATION = "update_automation"

UIPROTECT_APIS = {
    UIProtectApi.LOGIN: {
        UIPROTECT_API_PATH: "/api/auth/login",
        UIPROTECT_API_METHOD: "post",
    },
    UIProtectApi.GET_AUTOMATIONS: {
        UIPROTECT_API_PATH: "/proxy/protect/api/automations",
        UIPROTECT_API_METHOD: "get",
    },
    UIProtectApi.UPDATE_AUTOMATION: {
        UIPROTECT_API_PATH: "/proxy/protect/api/automations",
        UIPROTECT_API_METHOD: "patch",
    }    
}
