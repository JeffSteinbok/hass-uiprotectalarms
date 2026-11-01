"""Test helpers for PyUIProtectAlarms."""
import logging
from unittest.mock import MagicMock, patch

from  .imports import Helpers

class TestHelpers:
    """Test helpers for PyUIProtectAlarms."""

    def test_redactor(self):
        """Test redactor function."""
        Helpers.shouldredact = True
        test_string = '{"username": "user1", "password": "mypassword", "token": "abcd1234", "data": "value"}'
        redacted_string = Helpers.redactor(test_string)
        assert 'mypassword' not in redacted_string
        assert 'abcd1234' not in redacted_string
        assert 'user1' not in redacted_string
        assert '##_REDACTED_##' in redacted_string

    def test_decode_token_cookie(self):
        """Test decode_token_cookie function."""
        import jwt
        import time

        # Create a valid token
        payload = {
            "sub": "1234567890",
            "name": "John Doe",
            "iat": int(time.time()),
            "exp": int(time.time()) + 60  # Expires in 60 seconds
        }
        secret = 'secret'
        valid_token = jwt.encode(payload, secret, algorithm='HS256')

        decoded = Helpers.decode_token_cookie(valid_token)
        assert decoded is not None
        assert decoded['sub'] == "1234567890"

        # Create an expired token
        expired_payload = {
            "sub": "1234567890",
            "name": "John Doe",
            "iat": int(time.time()) - 120,
            "exp": int(time.time()) - 60  # Expired 60 seconds ago
        }
        expired_token = jwt.encode(expired_payload, secret, algorithm='HS256')

        decoded_expired = Helpers.decode_token_cookie(expired_token)
        assert decoded_expired is None

    def test_call_json_api_returns_actual_status_code_and_logs_body_on_failure(self, caplog):
        """Test that call_json_api surfaces the real HTTP status code on failure (instead of
        always returning 0), and that the status code and body get logged for debugging."""
        caplog.set_level(logging.DEBUG)

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = (
            '{"error": "This operation is not available when global alarm manager '
            'is enabled", "name": "BAD_REQUEST"}'
        )
        mock_response.content = mock_response.text.encode()

        with patch("requests.get", return_value=mock_response):
            response, status_code = Helpers.call_json_api(
                "https://example.com", "/some/path", "get", {}, {}
            )

        assert status_code == 400
        assert response is None
        assert "status=400" in caplog.text
        assert "global alarm manager" in caplog.text
