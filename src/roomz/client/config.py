"""
Configuration management for Roomz client using clevis package.

Provides simplified configuration with built-in security validation.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

from clevis import SecurityAction, get_config

from roomz.client.exceptions import ConfigurationError

logger = logging.getLogger(__name__)


@dataclass
class RoomzConfig:
  """
  Configuration for Roomz client.

  Attributes:
    server_url: WebSocket server URL (e.g., "http://localhost:5000")
    display_name: Optional display name for the user

  Example:
    >>> config = RoomzConfig(server_url="http://localhost:5000", display_name="Alice")
    >>> config = get_roomz_config()  # Auto-discover from env/files

  Resolution Order (highest to lowest priority):
    1. CLI arguments (if cli=True)
    2. Environment variables (ROOMZ_SERVER_URL, ROOMZ_DISPLAY_NAME)
    3. ./roomz.toml (current directory) with security validation
    4. ~/.roomz.toml (user home directory)
    5. Dataclass defaults

  Environment Variables:
    - ROOMZ_SERVER_URL: Server URL
    - ROOMZ_DISPLAY_NAME: Display name

  Config File Format (TOML):
    server_url = "http://localhost:5000"
    display_name = "Alice"

  Note:
    The old format with [client] section is no longer supported.
    Use top-level fields instead.
  """

  server_url: str | None = None
  display_name: str | None = None

  def __post_init__(self) -> None:
    """Validate configuration after initialization."""
    if self.server_url is not None:
      # Validate URL format
      if not self.server_url.startswith(("http://", "https://")):
        raise ValueError(f"server_url must be http:// or https:// URL: {self.server_url}")

      # Check for credentials in URL
      if "@" in self.server_url:
        raise ValueError(f"server_url should not contain credentials: {self.server_url}")


def get_roomz_config(cli: bool = False, args: list[str] | None = None) -> RoomzConfig:
  """
  Load configuration using clevis with built-in security validation.

  Args:
    cli: If True, parse CLI arguments; if False, ignore CLI
    args: Optional CLI arguments (defaults to sys.argv[1:])

  Returns:
    RoomzConfig instance with loaded configuration

  Raises:
    ConfigurationError: If configuration is invalid or security validation fails

  Resolution Order (highest to lowest priority):
    1. CLI arguments (if cli=True)
    2. Environment variables (ROOMZ_SERVER_URL, ROOMZ_DISPLAY_NAME)
    3. ./roomz.toml (current directory) with security validation
    4. ~/.roomz.toml (user home directory)
    5. Dataclass defaults

  Security:
    - Files with group/other read permissions are REJECTED
    - Files in world-writable directories are REJECTED
    - Home directory is trusted (no directory check)
  """
  try:
    # Get environment variables first (highest priority after CLI)
    env_server_url = os.environ.get("ROOMZ_SERVER_URL")
    env_display_name = os.environ.get("ROOMZ_DISPLAY_NAME")

    # Load from clevis (will load from TOML files with env var interpolation)
    # Only pass args to clevis if cli=True (CLI mode) - otherwise pass None to skip parsing
    clevis_args = args if cli else None
    config = get_config(
      RoomzConfig,
      name="roomz",
      user=True,
      project=True,
      cli=cli,
      args=clevis_args,
      security={
        "file_permissions": SecurityAction.REJECT,
        "directory_permissions": SecurityAction.REJECT,
      },
    )

    # Override with environment variables if set (higher priority than files)
    # This is needed because clevis only supports ${VAR} interpolation in TOML files,
    # not direct environment variable reading
    if env_server_url is not None or env_display_name is not None:
      # Create new config with env var overrides
      server_url = env_server_url if env_server_url is not None else config.server_url
      display_name = env_display_name if env_display_name is not None else config.display_name
      config = RoomzConfig(server_url=server_url, display_name=display_name)

    # Validate the final config
    if config.server_url is not None:
      # Re-validate after env var override
      RoomzConfig.__post_init__(config)

    logger.debug(
      "config_loaded",
      extra={
        "server_url": config.server_url,
        "display_name": config.display_name,
        "source": "environment" if env_server_url or env_display_name else "file",
      },
    )

    return config
  except Exception as e:
    # Convert clevis exceptions to roomz exceptions
    raise ConfigurationError(f"Failed to load configuration: {e}") from e


# Type alias for backward compatibility
Config = RoomzConfig


def resolve_config(
  config: RoomzConfig | None = None,
  config_path: str | Any | None = None,  # Deprecated: no longer used
) -> RoomzConfig:
  """
  Resolve configuration from explicit parameters or auto-discovery.

  This function maintains backward compatibility with the old API.

  Args:
    config: Explicit RoomzConfig instance (highest priority)
    config_path: DEPRECATED - Path to config file (no longer used)

  Returns:
    Resolved RoomzConfig instance

  Note:
    The config_path parameter is deprecated. Configuration is now managed
    by clevis which handles file discovery automatically.

  Example:
    >>> # Use explicit config
    >>> config = resolve_config(config=RoomzConfig(server_url="http://example.com"))

    >>> # Auto-discover
    >>> config = resolve_config()
  """
  if config is not None:
    return config

  # Note: config_path is deprecated and ignored
  # Clevis handles file discovery automatically
  return get_roomz_config(cli=False, args=[])
