"""
Unit tests for token utilities.
"""

import jwt

from miso_client.utils.token_utils import extract_client_token_info

TEST_JWT_SECRET = "test-secret-key-for-jwt-32-bytes!!"


class TestTokenUtils:
    """Test cases for token utilities."""

    def test_extract_client_token_info_with_application(self):
        """Test extracting application field."""
        payload = {"application": "my-app"}
        token = jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")

        info = extract_client_token_info(token)

        assert info["application"] == "my-app"
        assert info["environment"] is None
        assert info["applicationId"] is None
        assert info["clientId"] is None

    def test_extract_client_token_info_with_app_alias(self):
        """Test extracting application using 'app' alias."""
        payload = {"app": "my-app"}
        token = jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")

        info = extract_client_token_info(token)

        assert info["application"] == "my-app"

    def test_extract_client_token_info_with_environment(self):
        """Test extracting environment field."""
        payload = {"environment": "production"}
        token = jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")

        info = extract_client_token_info(token)

        assert info["environment"] == "production"
        assert info["application"] is None

    def test_extract_client_token_info_with_env_alias(self):
        """Test extracting environment using 'env' alias."""
        payload = {"env": "production"}
        token = jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")

        info = extract_client_token_info(token)

        assert info["environment"] == "production"

    def test_extract_client_token_info_with_application_id(self):
        """Test extracting applicationId field."""
        payload = {"applicationId": "app-123"}
        token = jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")

        info = extract_client_token_info(token)

        assert info["applicationId"] == "app-123"

    def test_extract_client_token_info_with_app_id_alias(self):
        """Test extracting applicationId using 'app_id' alias."""
        payload = {"app_id": "app-123"}
        token = jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")

        info = extract_client_token_info(token)

        assert info["applicationId"] == "app-123"

    def test_extract_client_token_info_with_client_id(self):
        """Test extracting clientId field."""
        payload = {"clientId": "client-123"}
        token = jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")

        info = extract_client_token_info(token)

        assert info["clientId"] == "client-123"

    def test_extract_client_token_info_with_client_id_alias(self):
        """Test extracting clientId using 'client_id' alias."""
        payload = {"client_id": "client-123"}
        token = jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")

        info = extract_client_token_info(token)

        assert info["clientId"] == "client-123"

    def test_extract_client_token_info_all_fields(self):
        """Test extracting all fields."""
        payload = {
            "application": "my-app",
            "environment": "production",
            "applicationId": "app-123",
            "clientId": "client-123",
        }
        token = jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")

        info = extract_client_token_info(token)

        assert info["application"] == "my-app"
        assert info["environment"] == "production"
        assert info["applicationId"] == "app-123"
        assert info["clientId"] == "client-123"

    def test_extract_client_token_info_case_variations(self):
        """Test extracting with case variations."""
        payload = {
            "Application": "my-app",
            "Environment": "production",
            "ApplicationId": "app-123",
            "ClientId": "client-123",
        }
        token = jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")

        info = extract_client_token_info(token)

        assert info["application"] == "my-app"
        assert info["environment"] == "production"
        assert info["applicationId"] == "app-123"
        assert info["clientId"] == "client-123"

    def test_extract_client_token_info_invalid_token(self):
        """Test extracting from invalid token."""
        info = extract_client_token_info("invalid.token.here")

        assert info["application"] is None
        assert info["environment"] is None
        assert info["applicationId"] is None
        assert info["clientId"] is None

    def test_extract_client_token_info_empty_token(self):
        """Test extracting from empty token."""
        info = extract_client_token_info("")

        assert info["application"] is None
        assert info["environment"] is None
        assert info["applicationId"] is None
        assert info["clientId"] is None

    def test_extract_client_token_info_none_token(self):
        """Test extracting from None token."""
        info = extract_client_token_info(None)

        assert info["application"] is None
        assert info["environment"] is None
        assert info["applicationId"] is None
        assert info["clientId"] is None

    def test_extract_client_token_info_no_fields(self):
        """Test extracting when no relevant fields present."""
        payload = {"sub": "user-123", "exp": 9999999999}
        token = jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")

        info = extract_client_token_info(token)

        assert info["application"] is None
        assert info["environment"] is None
        assert info["applicationId"] is None
        assert info["clientId"] is None

    def test_extract_client_token_info_priority_application(self):
        """Test that 'application' has priority over 'app'."""
        payload = {"application": "my-app", "app": "other-app"}
        token = jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")

        info = extract_client_token_info(token)

        assert info["application"] == "my-app"

    def test_extract_client_token_info_priority_environment(self):
        """Test that 'environment' has priority over 'env'."""
        payload = {"environment": "prod", "env": "dev"}
        token = jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")

        info = extract_client_token_info(token)

        assert info["environment"] == "prod"

    def test_extract_client_token_info_whitespace_trimming(self):
        """Test that whitespace is trimmed from values."""
        payload = {"application": "  my-app  ", "environment": "  prod  "}
        token = jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")

        info = extract_client_token_info(token)

        assert info["application"] == "my-app"
        assert info["environment"] == "prod"

    def test_extract_client_token_info_empty_string_values(self):
        """Test that empty string values return None."""
        payload = {"application": "", "environment": "   "}
        token = jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")

        info = extract_client_token_info(token)

        assert info["application"] is None
        assert info["environment"] is None

    def test_extract_client_token_info_non_string_values(self):
        """Test that non-string values return None."""
        payload = {"application": 123, "environment": ["prod"]}
        token = jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")

        info = extract_client_token_info(token)

        assert info["application"] is None
        assert info["environment"] is None
