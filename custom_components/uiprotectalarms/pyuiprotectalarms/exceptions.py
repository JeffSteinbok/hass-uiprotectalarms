class UnifiProtectError(Exception):
    """Base class for all other UniFi Protect errors"""

class ClientError(UnifiProtectError):
    """Base Class for all other UniFi Protect client errors"""

class BadRequest(ClientError):
    """Invalid request from API Client"""

class Invalid(ClientError):
    """Invalid return from Authorization Request."""

class NotAuthorized(PermissionError, BadRequest):
    """Wrong username, password or permission error."""

class NvrError(ClientError):
    """Other error."""