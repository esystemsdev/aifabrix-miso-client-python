"""
Unit tests for error types.
"""

from miso_client.errors import (
    MisoClientError,
    AuthenticationError,
    AuthorizationError,
    ConnectionError,
    ConfigurationError,
)


class TestErrors:
    """Test cases for error types."""
    
    def test_miso_client_error(self):
        """Test base MisoClientError."""
        error = MisoClientError("Test error", status_code=400, error_body={"code": "ERR001"})
        
        assert str(error) == "Test error"
        assert error.message == "Test error"
        assert error.status_code == 400
        assert error.error_body == {"code": "ERR001"}
    
    def test_miso_client_error_minimal(self):
        """Test MisoClientError with minimal args."""
        error = MisoClientError("Simple error")
        
        assert str(error) == "Simple error"
        assert error.status_code is None
        assert error.error_body is None
    
    def test_authentication_error(self):
        """Test AuthenticationError."""
        error = AuthenticationError("Auth failed", status_code=401)
        
        assert isinstance(error, MisoClientError)
        assert str(error) == "Auth failed"
        assert error.status_code == 401
    
    def test_authorization_error(self):
        """Test AuthorizationError."""
        error = AuthorizationError("Not authorized", status_code=403)
        
        assert isinstance(error, MisoClientError)
        assert str(error) == "Not authorized"
        assert error.status_code == 403
    
    def test_connection_error(self):
        """Test ConnectionError."""
        error = ConnectionError("Connection failed")
        
        assert isinstance(error, MisoClientError)
        assert str(error) == "Connection failed"
    
    def test_configuration_error(self):
        """Test ConfigurationError."""
        error = ConfigurationError("Config invalid")
        
        assert isinstance(error, MisoClientError)
        assert str(error) == "Config invalid"
    
    def test_error_inheritance(self):
        """Test error inheritance hierarchy."""
        auth_error = AuthenticationError("test")
        authz_error = AuthorizationError("test")
        conn_error = ConnectionError("test")
        config_error = ConfigurationError("test")
        
        assert isinstance(auth_error, MisoClientError)
        assert isinstance(authz_error, MisoClientError)
        assert isinstance(conn_error, MisoClientError)
        assert isinstance(config_error, MisoClientError)

