"""Secret Manager integration for secure secrets management.

This module provides a simple interface to Google Cloud Secret Manager,
allowing the application to retrieve secrets securely without hardcoding
or storing them in environment variables.

Usage:
    from nvidia_blog_agent.secrets import get_secret
    
    api_key = get_secret("ingest-api-key")
"""

import os
import logging
from typing import Optional

try:
    from google.cloud import secretmanager
    SECRET_MANAGER_AVAILABLE = True
except ImportError:
    SECRET_MANAGER_AVAILABLE = False

logger = logging.getLogger(__name__)

# Cache for secrets to avoid repeated API calls
_secret_cache: dict[str, str] = {}


def get_secret(secret_id: str, project_id: Optional[str] = None, version: str = "latest") -> Optional[str]:
    """Get a secret from Google Cloud Secret Manager.
    
    Falls back to environment variable if Secret Manager is not available
    or if the secret doesn't exist.
    
    Args:
        secret_id: The secret ID (name without the full resource path)
        project_id: Optional GCP project ID. Defaults to GOOGLE_CLOUD_PROJECT env var.
        version: Secret version to retrieve. Defaults to "latest".
    
    Returns:
        The secret value as a string, or None if not found.
    
    Example:
        >>> api_key = get_secret("ingest-api-key")
        >>> if api_key:
        ...     print("Secret retrieved successfully")
    """
    # Check cache first
    cache_key = f"{secret_id}:{version}"
    if cache_key in _secret_cache:
        return _secret_cache[cache_key]
    
    # Fallback to environment variable (for local dev or if Secret Manager unavailable)
    env_var_name = secret_id.upper().replace("-", "_")
    env_value = os.environ.get(env_var_name)
    if env_value:
        logger.debug(f"Using {env_var_name} from environment variable")
        _secret_cache[cache_key] = env_value
        return env_value
    
    # Try Secret Manager if available
    if not SECRET_MANAGER_AVAILABLE:
        logger.warning(f"Secret Manager not available. Using environment variable {env_var_name} or None")
        return None
    
    try:
        # Get project ID
        if not project_id:
            project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
            if not project_id:
                logger.warning("GOOGLE_CLOUD_PROJECT not set. Cannot use Secret Manager.")
                return None
        
        # Create Secret Manager client
        client = secretmanager.SecretManagerServiceClient()
        
        # Build the resource name
        name = f"projects/{project_id}/secrets/{secret_id}/versions/{version}"
        
        # Access the secret version
        response = client.access_secret_version(request={"name": name})
        secret_value = response.payload.data.decode("UTF-8")
        
        # Cache the result
        _secret_cache[cache_key] = secret_value
        logger.info(f"Retrieved secret {secret_id} from Secret Manager")
        
        return secret_value
    
    except Exception as e:
        logger.warning(f"Failed to retrieve secret {secret_id} from Secret Manager: {e}")
        logger.warning(f"Falling back to environment variable {env_var_name}")
        return None


def clear_cache():
    """Clear the secret cache. Useful for testing or when secrets are updated."""
    global _secret_cache
    _secret_cache.clear()

