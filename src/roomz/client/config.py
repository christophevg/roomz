"""
Configuration management for Roomz client using clevis package.

Provides simplified configuration with built-in security validation.
"""

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ClientConfig:
  """
  Client-specific configuration.

  Attributes:
    server_url: WebSocket server URL (e.g., "http://localhost:5000")
    display_name: Optional display name for the user

  Example:
    >>> client_config = ClientConfig(server_url="http://localhost:5000", display_name="Alice")
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


@dataclass
class RoomzConfig:
  """
  Root configuration for Roomz client.

  Attributes:
    client: Client-specific configuration (server_url, display_name)

  Example:
    >>> config = RoomzConfig()
    >>> config = get_config(RoomzConfig, name="roomz")  # Use clevis directly

  Resolution Order (highest to lowest priority):
    1. CLI arguments (when cli=True)
    2. Project TOML (./roomz.toml) with ${VAR} interpolation
    3. User TOML (~/.roomz.toml) with ${VAR} interpolation
    4. Dataclass defaults

  Environment Variables (for TOML interpolation):
    Use ${ROOMZ_SERVER_URL} and ${ROOMZ_DISPLAY_NAME} in TOML files.

  Config File Format (TOML):
    [client]
    server_url = "http://localhost:5000"
    display_name = "Alice"

    # Or with environment variable interpolation:
    [client]
    server_url = "${ROOMZ_SERVER_URL}"
    display_name = "${ROOMZ_DISPLAY_NAME}"
  """

  client: ClientConfig = field(default_factory=ClientConfig)
