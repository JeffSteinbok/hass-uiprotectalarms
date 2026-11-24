"""Credentials must never reach the log, even with debug logging on (#23)."""
import json
import logging
import time
from unittest.mock import MagicMock, patch

import jwt
import pytest

from .imports import Helpers, PyUIProtectAlarms, UIProtectApi

REQUESTS_PATH = "custom_components.uiprotectalarms.pyuiprotectalarms.helpers.requests"

# Obviously fake values, so any of them showing up in the log is a leak.
FAKE_COOKIE = "fake-session-cookie-0000"
FAKE_SET_COOKIE = "TOKEN=fake-set-cookie-1111; Path=/; HttpOnly"
FAKE_CSRF = "fake-csrf-token-2222"
FAKE_AUTHORIZATION = "Bearer fake-authorization-3333"
FAKE_PASSWORD = "fake-password-4444"
FAKE_BODY_TOKEN = "fake-body-token-5555"
FAKE_ACCESS_TOKEN = "fake-access-token-6666"
FAKE_RESPONSE_CSRF = "fake-response-csrf-7777"

SECRETS = (
    FAKE_COOKIE,
    FAKE_SET_COOKIE,
    "fake-set-cookie-1111",
    FAKE_CSRF,
    FAKE_AUTHORIZATION,
    "fake-authorization-3333",
    FAKE_PASSWORD,
    FAKE_BODY_TOKEN,
    FAKE_ACCESS_TOKEN,
    FAKE_RESPONSE_CSRF,
)

HEADERS = {
    "Cookie": f"TOKEN={FAKE_COOKIE}",
    "Set-Cookie": FAKE_SET_COOKIE,
    "X-CSRF-Token": FAKE_CSRF,
    "Authorization": FAKE_AUTHORIZATION,
    "Accept": "application/json",
}

BODY = {
    "username": "someone",
    "password": FAKE_PASSWORD,
    "token": FAKE_BODY_TOKEN,
    "nested": {"accessToken": FAKE_ACCESS_TOKEN, "keep": "visible-value"},
    "items": [{"csrfToken": FAKE_RESPONSE_CSRF}],
}


def _mock_response(payload) -> MagicMock:
    response = MagicMock()
    response.status_code = 200
    response.content = json.dumps(payload).encode()
    response.json.return_value = payload
    response.headers = {}
    response.cookies = {}
    return response


def _assert_no_secrets(text: str) -> None:
    for secret in SECRETS:
        assert secret not in text, f"secret leaked into the log: {secret!r}"


@pytest.fixture(name="debug_log")
def fixture_debug_log(caplog):
    """Capture all debug logging, with the optional redaction flag off."""
    caplog.set_level(logging.DEBUG)
    with patch.object(Helpers, "shouldredact", False):
        yield caplog


class TestLogRedaction:
    """Debug logs of requests and responses contain no credentials."""

    @pytest.mark.parametrize("method", ["get", "post", "put", "patch"])
    def test_call_api_debug_log_has_no_secrets(self, debug_log, method):
        """Request headers and body are logged without their credentials."""
        with patch(REQUESTS_PATH) as mock_requests:
            getattr(mock_requests, method).return_value = _mock_response({})
            Helpers.call_api("https://protect.invalid", "/api/test", method, dict(BODY), dict(HEADERS))

        assert "API call headers" in debug_log.text
        assert "API call json" in debug_log.text
        _assert_no_secrets(debug_log.text)
        # Non-secret data is still logged, so the debug log stays useful
        assert "application/json" in debug_log.text
        assert "visible-value" in debug_log.text
        assert Helpers.REDACTED in debug_log.text

    def test_call_json_api_response_log_has_no_secrets(self, debug_log):
        """A response body carrying tokens is logged without them."""
        with patch(REQUESTS_PATH) as mock_requests:
            mock_requests.get.return_value = _mock_response(BODY)
            response, status = Helpers.call_json_api(
                "https://protect.invalid", "/api/test", "get", {}, dict(HEADERS)
            )

        # The caller still gets the real data, only the log is redacted
        assert status == 200
        assert response["token"] == FAKE_BODY_TOKEN
        assert "API response" in debug_log.text
        _assert_no_secrets(debug_log.text)

    def test_call_uiprotect_api_debug_log_has_no_session_secrets(self, debug_log):
        """The session cookie and CSRF token sent with every call stay out of the log."""
        session_cookie = jwt.encode({"exp": int(time.time()) + 3600}, "test", algorithm="HS256")
        manager = PyUIProtectAlarms("protect.invalid", "someone", FAKE_PASSWORD)
        manager._is_authenticated = True  # pylint: disable=protected-access
        manager._last_token_cookie = session_cookie  # pylint: disable=protected-access
        manager._last_csrf_token = FAKE_CSRF  # pylint: disable=protected-access

        with patch(REQUESTS_PATH) as mock_requests:
            mock_requests.get.return_value = _mock_response([])
            _response, status = manager.call_uiprotect_api(UIProtectApi.GET_AUTOMATIONS)

        assert status == 200
        sent_headers = mock_requests.get.call_args.kwargs["headers"]
        assert session_cookie in sent_headers["Cookie"]
        assert "API call headers" in debug_log.text
        assert session_cookie not in debug_log.text
        _assert_no_secrets(debug_log.text)

    def test_login_debug_log_has_no_password(self, debug_log):
        """The login request body is logged without the password."""
        manager = PyUIProtectAlarms("protect.invalid", "someone", FAKE_PASSWORD)
        login_response = _mock_response({})
        login_response.headers = {"x-csrf-token": FAKE_RESPONSE_CSRF}

        with patch(REQUESTS_PATH) as mock_requests:
            mock_requests.post.return_value = login_response
            manager.authenticate()

        assert "API call json" in debug_log.text
        _assert_no_secrets(debug_log.text)

    def test_redact_data_does_not_modify_input(self):
        """Redaction works on a copy: the real request still has its headers."""
        headers = dict(HEADERS)
        redacted = Helpers.redact_data(headers)
        assert headers == HEADERS
        for key in ("Cookie", "Set-Cookie", "X-CSRF-Token", "Authorization"):
            assert redacted[key] == Helpers.REDACTED
        assert redacted["Accept"] == "application/json"

    def test_redactor_always_redacts_credentials(self):
        """The string redactor hides credentials even with shouldredact off."""
        with patch.object(Helpers, "shouldredact", False):
            redacted = Helpers.redactor(json.dumps({**HEADERS, **BODY}))
        _assert_no_secrets(redacted)
        # Personal details only go when the flag is on
        assert "someone" in redacted
        with patch.object(Helpers, "shouldredact", True):
            assert "someone" not in Helpers.redactor(json.dumps(BODY))
