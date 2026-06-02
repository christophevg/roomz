"""
Configuration management for Roomz client.

Provides a Config class with automatic discovery from multiple sources:
explicit parameters, environment variables, and TOML config files.

Resolution order (highest to lowest priority):
  1. Explicit `config` parameter
  2. Explicit `config_path` parameter (load from file)
  3. Prefixed environment variable (e.g., HELLO_ROOMZ_SERVER_URL)
  4. Unprefixed environment variable (e.g., ROOMZ_SERVER_URL)
  5. ./roomz.toml (current directory)
  6. ~/.roomz.toml (user home directory)
  7. Default Config() (empty, raises on connect)
"""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Use tomllib for Python 3.11+, tomli for earlier versions
if sys.version_info >= (3, 11):
  import tomllib
else:
  import tomli as tomllib


@dataclass
class Config:
  """
  Configuration for Roomz client.

  Attributes:
    server_url: WebSocket server URL (e.g., "http://localhost:5000")
    display_name: Optional display name for the user

  Example:
    >>> config = Config(server_url="http://localhost:5000", display_name="Alice")
    >>> config = Config.load("~/.roomz.toml")
    >>> config, path = Config.auto_discover()

  Resolution Order:
    Each config value is resolved in this order:
      1. Explicit `config` parameter (if provided)
      2. Explicit `config_path` parameter (load from file)
      3. Prefixed env var (e.g., HELLO_ROOMZ_SERVER_URL)
      4. Unprefixed env var (e.g., ROOMZ_SERVER_URL)
      5. ./roomz.toml (current directory)
      6. ~/.roomz.toml (user home directory)
      7. Default Config() (empty values)

  Environment Variables:
    - ROOMZ_SERVER_URL: Server URL (or {PREFIX}_ROOMZ_SERVER_URL)
    - ROOMZ_DISPLAY_NAME: Display name (or {PREFIX}_ROOMZ_DISPLAY_NAME)
    - ROOMZ_PREFIX: Prefix for environment variables (e.g., "HELLO" -> "HELLO_ROOMZ_*")

  Config File Format (TOML):
    [client]
    server_url = "http://localhost:5000"
    display_name = "Alice"

  Note:
    The prefix system allows multiple environments (dev, staging, prod) to use
    different configuration sets. For example:
      ROOMZ_PREFIX=DEV -> DEV_ROOMZ_SERVER_URL
      ROOMZ_PREFIX=PROD -> PROD_ROOMZ_SERVER_URL
  """

  server_url: str | None = None
  display_name: str | None = None

  @staticmethod
  def _get_env_var(prefix: str, base_var: str) -> str | None:
    """
    Get environment variable with optional prefix.

    Resolution order:
      1. {PREFIX}_{BASE_VAR} if prefix is set
      2. {BASE_VAR} (without prefix)

    Args:
      prefix: Environment variable prefix (from ROOMZ_PREFIX)
      base_var: Base variable name (e.g., "ROOMZ_SERVER_URL")

    Returns:
      Environment variable value or None

    Example:
      >>> os.environ["ROOMZ_PREFIX"] = "HELLO"
      >>> os.environ["HELLO_ROOMZ_SERVER_URL"] = "http://example.com"
      >>> Config._get_env_var("HELLO", "ROOMZ_SERVER_URL")
      'http://example.com'
    """
    # Try prefixed variable first
    if prefix:
      prefixed_var = f"{prefix}_{base_var}"
      value = os.environ.get(prefixed_var)
      if value is not None:
        return value

    # Fall back to unprefixed variable
    return os.environ.get(base_var)

  @classmethod
  def load(cls, config_path: str | Path) -> Config:
    """
    Load configuration from a TOML file.

    Args:
      config_path: Path to TOML config file

    Returns:
      Config instance with values from file

    Raises:
      FileNotFoundError: If config file doesn't exist
      ConfigurationError: If config file is invalid TOML

    Example:
      >>> config = Config.load("~/.roomz.toml")
      >>> config.server_url
      'http://localhost:5000'

    Config File Format:
      [client]
      server_url = "http://localhost:5000"
      display_name = "Alice"
    """
    # Import here to avoid circular import at module level
    from roomz.client.exceptions import ConfigurationError

    config_path = Path(config_path).expanduser()

    if not config_path.exists():
      raise FileNotFoundError(f"Config file not found: {config_path}")

    try:
      with open(config_path, "rb") as f:
        data = tomllib.load(f)

      # Extract [client] section
      client_config = data.get("client", {})

      return cls(
        server_url=client_config.get("server_url"),
        display_name=client_config.get("display_name"),
      )
    except (OSError, ValueError) as e:
      raise ConfigurationError(f"Failed to parse config file {config_path}: {e}") from e

  @classmethod
  def auto_discover(cls) -> tuple[Config, Path | None]:
    """
    Auto-discover configuration from environment and files.

    Searches for configuration in this order:
      1. Environment variables (prefixed and unprefixed)
      2. ./roomz.toml (current directory)
      3. ~/.roomz.toml (user home directory)

    Returns:
      Tuple of (Config instance, discovered config file path or None)
      The config file path is useful for debugging/logging which file was used.

    Raises:
      ConfigurationError: If a config file exists but is invalid

    Example:
      >>> # With ROOMZ_SERVER_URL env var set
      >>> config, path = Config.auto_discover()
      >>> config.server_url
      'http://example.com'
      >>> path is None  # No file was used
      True

      >>> # With ./roomz.toml file
      >>> config, path = Config.auto_discover()
      >>> config.server_url
      'http://localhost:5000'
      >>> path.name
      'roomz.toml'
    """
    # Import here to avoid circular import at module level
    from roomz.client.exceptions import ConfigurationError

    # Get prefix from environment
    prefix = os.environ.get("ROOMZ_PREFIX", "")

    # Try environment variables first
    server_url = cls._get_env_var(prefix, "ROOMZ_SERVER_URL")
    display_name = cls._get_env_var(prefix, "ROOMZ_DISPLAY_NAME")

    # Track discovered path for logging
    discovered_path: Path | None = None
    discovered_location: str | None = None

    # If both values are set from env, return early
    if server_url is not None and display_name is not None:
      logger.info(
        "config_discovered",
        extra={"path": None, "location": "environment", "server_url": server_url},
      )
      return cls(server_url=server_url, display_name=display_name), None

    # Try config files
    config_files = [
      (Path.cwd() / "roomz.toml", "cwd"),  # ./roomz.toml
      (Path.home() / ".roomz.toml", "home"),  # ~/.roomz.toml
    ]

    for config_file, location in config_files:
      if config_file.exists():
        try:
          file_config = cls.load(config_file)
          # Merge: env vars take precedence over file values
          if server_url is None:
            server_url = file_config.server_url
          if display_name is None:
            display_name = file_config.display_name
          # Found a valid config file, stop searching
          discovered_path = config_file
          discovered_location = location
          break
        except (OSError, ValueError) as e:
          # OSError: file reading issues
          # ValueError: TOML parsing errors (from cls.load)
          # Raise ConfigurationError instead of just logging
          raise ConfigurationError(f"Failed to load config file {config_file}: {e}") from e

    config = cls(server_url=server_url, display_name=display_name)

    # Log discovered config
    logger.info(
      "config_discovered",
      extra={
        "path": str(discovered_path) if discovered_path else None,
        "location": discovered_location or "environment",
        "server_url": server_url,
      },
    )

    # Validate discovered config and log warnings for issues
    errors = config.validate()
    for error in errors:
      logger.warning(f"Configuration validation: {error}")

    return config, discovered_path

  def merge(self, other: Config) -> Config:
    """
    Merge this config with another, preferring non-None values from this config.

    Args:
      other: Another Config instance to merge with

    Returns:
      New Config instance with merged values

    Example:
      >>> config1 = Config(server_url="http://example.com")
      >>> config2 = Config(display_name="Alice")
      >>> merged = config1.merge(config2)
      >>> merged.server_url
      'http://example.com'
      >>> merged.display_name
      'Alice'
    """
    return Config(
      server_url=self.server_url if self.server_url is not None else other.server_url,
      display_name=(self.display_name if self.display_name is not None else other.display_name),
    )

  def validate(self) -> list[str]:
    """
    Validate configuration values.

    Returns:
      List of validation error messages (empty if valid)

    Example:
      >>> config = Config(server_url="invalid")
      >>> config.validate()
      ['server_url must be http:// or https:// URL']
    """
    errors: list[str] = []

    if self.server_url is not None:
      # Validate server_url format
      if not self.server_url.startswith(("http://", "https://")):
        errors.append("server_url must be http:// or https:// URL")

      # Check for credentials in URL
      if "@" in self.server_url:
        errors.append("server_url should not contain credentials")

    return errors


def resolve_config(
  config: Config | None = None,
  config_path: str | Path | None = None,
) -> Config:
  """
  Resolve configuration from explicit parameters or auto-discovery.

  This function implements the full resolution order:
    1. Explicit `config` parameter (if provided, returned as-is)
    2. Explicit `config_path` parameter (load from file, merge with auto-discovered)
    3. Auto-discover from environment and files

  Args:
    config: Explicit Config instance (highest priority)
    config_path: Path to config file (medium priority)

  Returns:
    Resolved Config instance

  Example:
      >>> # Use explicit config
      >>> config = resolve_config(config=Config(server_url="http://example.com"))

      >>> # Load from file
      >>> config = resolve_config(config_path="~/.roomz.toml")

      >>> # Auto-discover
      >>> config = resolve_config()
  """
  # Priority 1: Explicit config parameter
  if config is not None:
    return config

  # Priority 2 & 3: Load from file or auto-discover
  if config_path is not None:
    # Load from explicit path
    explicit_config = Config.load(config_path)
    # Merge with auto-discovered (auto-discovered values fill in None)
    auto_config, _ = Config.auto_discover()
    return explicit_config.merge(auto_config)

  # Priority 4-6: Auto-discover from environment and files
  config, _ = Config.auto_discover()
  return config
