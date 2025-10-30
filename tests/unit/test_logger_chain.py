"""
Unit tests for LoggerChain fluent API.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from miso_client.services.logger import LoggerService, LoggerChain
from miso_client.models.config import ClientLoggingOptions


class TestLoggerChain:
    """Test cases for LoggerChain."""
    
    @pytest.fixture
    def logger_service(self, mock_http_client, mock_redis):
        """Test LoggerService instance."""
        return LoggerService(mock_http_client, mock_redis)
    
    @pytest.fixture
    def logger_chain(self, logger_service):
        """Test LoggerChain instance."""
        return LoggerChain(logger_service, {"initial": "context"}, ClientLoggingOptions())
    
    def test_chain_initialization(self, logger_service):
        """Test LoggerChain initialization."""
        chain = LoggerChain(logger_service, {"key": "value"}, ClientLoggingOptions())
        
        assert chain.logger is logger_service
        assert chain.context == {"key": "value"}
        assert isinstance(chain.options, ClientLoggingOptions)
    
    def test_add_context(self, logger_chain):
        """Test add_context method."""
        result = logger_chain.add_context("new_key", "new_value")
        
        assert result is logger_chain  # Should return self for chaining
        assert logger_chain.context["new_key"] == "new_value"
        assert logger_chain.context["initial"] == "context"  # Preserve existing
    
    def test_add_user(self, logger_chain):
        """Test add_user method."""
        result = logger_chain.add_user("user-123")
        
        assert result is logger_chain
        assert logger_chain.options.userId == "user-123"
    
    def test_add_application(self, logger_chain):
        """Test add_application method."""
        result = logger_chain.add_application("app-456")
        
        assert result is logger_chain
        assert logger_chain.options.applicationId == "app-456"
    
    def test_add_correlation(self, logger_chain):
        """Test add_correlation method."""
        result = logger_chain.add_correlation("corr-789")
        
        assert result is logger_chain
        assert logger_chain.options.correlationId == "corr-789"
    
    def test_with_token(self, logger_chain):
        """Test with_token method."""
        result = logger_chain.with_token("jwt-token-123")
        
        assert result is logger_chain
        assert logger_chain.options.token == "jwt-token-123"
    
    def test_with_performance(self, logger_chain):
        """Test with_performance method."""
        result = logger_chain.with_performance()
        
        assert result is logger_chain
        assert logger_chain.options.performanceMetrics is True
    
    def test_without_masking(self, logger_chain):
        """Test without_masking method."""
        result = logger_chain.without_masking()
        
        assert result is logger_chain
        assert logger_chain.options.maskSensitiveData is False
    
    def test_chain_methods_composable(self, logger_chain):
        """Test that chain methods can be composed."""
        result = (logger_chain
                  .add_context("key1", "value1")
                  .add_user("user-1")
                  .add_application("app-1")
                  .with_performance())
        
        assert result is logger_chain
        assert logger_chain.context["key1"] == "value1"
        assert logger_chain.options.userId == "user-1"
        assert logger_chain.options.applicationId == "app-1"
        assert logger_chain.options.performanceMetrics is True
    
    @pytest.mark.asyncio
    async def test_error_method(self, logger_service):
        """Test chain error method."""
        logger_service.redis.is_connected.return_value = False
        
        with patch.object(logger_service, 'error', new_callable=AsyncMock) as mock_error:
            chain = LoggerChain(logger_service, {"key": "value"}, ClientLoggingOptions())
            await chain.error("Error message", "Stack trace")
            
            mock_error.assert_called_once_with("Error message", {"key": "value"}, "Stack trace", chain.options)
    
    @pytest.mark.asyncio
    async def test_info_method(self, logger_service):
        """Test chain info method."""
        logger_service.redis.is_connected.return_value = False
        
        with patch.object(logger_service, 'info', new_callable=AsyncMock) as mock_info:
            chain = LoggerChain(logger_service, {"key": "value"}, ClientLoggingOptions())
            await chain.info("Info message")
            
            mock_info.assert_called_once_with("Info message", {"key": "value"}, chain.options)
    
    @pytest.mark.asyncio
    async def test_audit_method(self, logger_service):
        """Test chain audit method."""
        logger_service.redis.is_connected.return_value = False
        
        with patch.object(logger_service, 'audit', new_callable=AsyncMock) as mock_audit:
            chain = LoggerChain(logger_service, {"key": "value"}, ClientLoggingOptions())
            await chain.audit("action", "resource")
            
            mock_audit.assert_called_once_with("action", "resource", {"key": "value"}, chain.options)
    
    @pytest.mark.asyncio
    async def test_chain_with_all_options(self, logger_service):
        """Test chain with all options set."""
        logger_service.redis.is_connected.return_value = False
        
        with patch.object(logger_service, 'info', new_callable=AsyncMock) as mock_info:
            chain = (LoggerChain(logger_service, {}, ClientLoggingOptions())
                     .add_user("user-123")
                     .add_application("app-456")
                     .add_correlation("corr-789")
                     .with_token("token-abc")
                     .with_performance()
                     .without_masking())
            
            await chain.info("Test message")
            
            mock_info.assert_called_once()
            call_args = mock_info.call_args
            options = call_args[0][2]  # Third argument is options
            assert options.userId == "user-123"
            assert options.applicationId == "app-456"
            assert options.correlationId == "corr-789"
            assert options.token == "token-abc"
            assert options.performanceMetrics is True
            assert options.maskSensitiveData is False

