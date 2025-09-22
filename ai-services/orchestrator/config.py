# config.py
"""
Configuration management and validation for the orchestrator service
"""
import os
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class ServiceConfig:
    """Configuration class for orchestrator service"""
    
    # Required configurations
    gemini_api_key: str
    ai_meta_db_uri: str
    jwt_public_key: str
    
    # Service URLs with defaults
    contact_sage_url: str = "http://contact-sage:8080"
    anomaly_sage_url: str = "http://anomaly-sage:8080"
    transaction_sage_url: str = "http://transaction-sage:8080"
    money_sage_url: str = "http://money-sage:8080"
    
    # Optional configurations
    log_level: str = "INFO"
    cache_ttl_seconds: int = 900  # 15 minutes
    session_cleanup_days: int = 30
    currency_cache_hours: int = 24
    http_timeout_seconds: int = 30
    max_conversation_turns: int = 50

    @classmethod
    def from_env(cls) -> 'ServiceConfig':
        """Create configuration from environment variables"""
        
        # Required environment variables
        required_vars = {
            'GEMINI_API_KEY': 'gemini_api_key',
            'AI_META_DB_URI': 'ai_meta_db_uri',
            'JWT_PUBLIC_KEY': 'jwt_public_key'
        }
        
        # Check for required variables
        missing_vars = []
        config_dict = {}
        
        for env_var, config_key in required_vars.items():
            value = os.getenv(env_var)
            if not value:
                missing_vars.append(env_var)
            else:
                config_dict[config_key] = value
        
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
        
        # Optional environment variables with defaults
        optional_vars = {
            'CONTACT_SAGE_URL': ('contact_sage_url', "http://contact-sage:8080"),
            'ANOMALY_SAGE_URL': ('anomaly_sage_url', "http://anomaly-sage:8080"),
            'TRANSACTION_SAGE_URL': ('transaction_sage_url', "http://transaction-sage:8080"),
            'MONEY_SAGE_URL': ('money_sage_url', "http://money-sage:8080"),
            'LOG_LEVEL': ('log_level', "INFO"),
            'CACHE_TTL_SECONDS': ('cache_ttl_seconds', 900),
            'SESSION_CLEANUP_DAYS': ('session_cleanup_days', 30),
            'CURRENCY_CACHE_HOURS': ('currency_cache_hours', 24),
            'HTTP_TIMEOUT_SECONDS': ('http_timeout_seconds', 30),
            'MAX_CONVERSATION_TURNS': ('max_conversation_turns', 50)
        }
        
        for env_var, (config_key, default_value) in optional_vars.items():
            value = os.getenv(env_var, str(default_value))
            
            # Convert to appropriate type
            if config_key in ['cache_ttl_seconds', 'session_cleanup_days', 'currency_cache_hours', 
                             'http_timeout_seconds', 'max_conversation_turns']:
                try:
                    value = int(value)
                except ValueError:
                    logger.warning(f"Invalid integer value for {env_var}, using default: {default_value}")
                    value = default_value
            
            config_dict[config_key] = value
        
        return cls(**config_dict)
    
    def validate(self) -> Dict[str, Any]:
        """
        Validate configuration and return validation results
        
        Returns:
            Dictionary with validation results and any issues found
        """
        issues = []
        warnings = []
        
        # Validate database URI format
        if not self.ai_meta_db_uri.startswith(('postgresql://', 'postgres://')):
            issues.append("AI_META_DB_URI must be a PostgreSQL connection string")
        
        # Validate JWT public key format
        if not self.jwt_public_key.strip().startswith('-----BEGIN'):
            issues.append("JWT_PUBLIC_KEY must be a PEM-formatted public key")
        
        # Validate service URLs
        service_urls = [
            ('CONTACT_SAGE_URL', self.contact_sage_url),
            ('ANOMALY_SAGE_URL', self.anomaly_sage_url), 
            ('TRANSACTION_SAGE_URL', self.transaction_sage_url),
            ('MONEY_SAGE_URL', self.money_sage_url)
        ]
        
        for name, url in service_urls:
            if not url.startswith(('http://', 'https://')):
                issues.append(f"{name} must be a valid HTTP/HTTPS URL")
        
        # Validate numeric ranges
        if self.cache_ttl_seconds < 60:
            warnings.append("CACHE_TTL_SECONDS is very low, may impact performance")
        
        if self.http_timeout_seconds < 5:
            warnings.append("HTTP_TIMEOUT_SECONDS is very low, may cause timeouts")
        
        if self.session_cleanup_days < 1:
            issues.append("SESSION_CLEANUP_DAYS must be at least 1")
        
        # Validate log level
        valid_log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if self.log_level.upper() not in valid_log_levels:
            issues.append(f"LOG_LEVEL must be one of: {', '.join(valid_log_levels)}")
        
        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'warnings': warnings,
            'config_summary': self.to_dict(mask_secrets=True)
        }
    
    def to_dict(self, mask_secrets: bool = True) -> Dict[str, Any]:
        """Convert configuration to dictionary, optionally masking secrets"""
        config_dict = {
            'gemini_api_key': '***masked***' if mask_secrets else self.gemini_api_key,
            'ai_meta_db_uri': self._mask_db_uri(self.ai_meta_db_uri) if mask_secrets else self.ai_meta_db_uri,
            'jwt_public_key': '***masked***' if mask_secrets else self.jwt_public_key,
            'contact_sage_url': self.contact_sage_url,
            'anomaly_sage_url': self.anomaly_sage_url,
            'transaction_sage_url': self.transaction_sage_url,
            'money_sage_url': self.money_sage_url,
            'log_level': self.log_level,
            'cache_ttl_seconds': self.cache_ttl_seconds,
            'session_cleanup_days': self.session_cleanup_days,
            'currency_cache_hours': self.currency_cache_hours,
            'http_timeout_seconds': self.http_timeout_seconds,
            'max_conversation_turns': self.max_conversation_turns
        }
        return config_dict
    
    @staticmethod
    def _mask_db_uri(uri: str) -> str:
        """Mask password in database URI for logging"""
        if '://' not in uri:
            return uri
            
        try:
            # Extract password and mask it
            parts = uri.split('://', 1)
            if '@' in parts[1]:
                creds, rest = parts[1].split('@', 1)
                if ':' in creds:
                    user, _ = creds.split(':', 1)
                    return f"{parts[0]}://{user}:***@{rest}"
        except:
            pass
        
        return uri

def load_and_validate_config() -> ServiceConfig:
    """
    Load configuration from environment and validate it
    
    Returns:
        ServiceConfig instance
        
    Raises:
        ValueError: If configuration is invalid
        RuntimeError: If validation fails
    """
    try:
        # Load configuration from environment
        config = ServiceConfig.from_env()
        
        # Validate configuration
        validation_result = config.validate()
        
        if not validation_result['valid']:
            error_msg = f"Configuration validation failed: {'; '.join(validation_result['issues'])}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
        
        # Log warnings if any
        for warning in validation_result['warnings']:
            logger.warning(f"Configuration warning: {warning}")
        
        # Log successful configuration load
        logger.info("Configuration loaded and validated successfully")
        logger.debug(f"Configuration: {validation_result['config_summary']}")
        
        return config
        
    except ValueError as e:
        logger.error(f"Configuration error: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error loading configuration: {str(e)}")
        raise RuntimeError(f"Failed to load configuration: {str(e)}")

# Global configuration instance (loaded on import)
try:
    CONFIG = load_and_validate_config()
except Exception as e:
    logger.error(f"Failed to load configuration on import: {str(e)}")
    # Re-raise to prevent service from starting with invalid config
    raise