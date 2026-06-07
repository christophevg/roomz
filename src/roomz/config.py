"""Configuration module for roomz application.

This module provides configuration support using dataclasses and Clevis.
Configuration can be loaded from TOML files, environment variables, or CLI args.
"""

from dataclasses import dataclass, field
from typing import List  # noqa: UP035 - Required for Clevis compatibility


@dataclass
class ClientConfig:
  """Client configuration for TUI.

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
class ServerConfig:
  """Server configuration.

  Attributes:
    bind: The socket to bind (e.g., '0.0.0.0:8000' or 'unix:/tmp/socket')
    workers: Number of worker processes
    worker_class: The type of workers to use (e.g., uvicorn.workers.UvicornWorker)
    timeout: Worker timeout in seconds
    keepalive: Time to wait for requests on a Keep-Alive connection
  """

  bind: str = "127.0.0.1:8081"
  workers: int = 1
  worker_class: str = "uvicorn.workers.UvicornWorker"
  timeout: int = 120
  keepalive: int = 5


@dataclass
class EmailConfig:
  """Email configuration for magic link authentication.

  Attributes:
    sender_email: Email address to send magic links from
    resend_api_key: Resend API key for email delivery
    allowed_emails: List of allowed email addresses/patterns
    magic_link_expiry: Magic link expiration time in minutes
    rate_limit_per_hour: Max magic link requests per email per hour
  """

  sender_email: str | None = None
  resend_api_key: str | None = None
  allowed_emails: List[str] | None = field(default_factory=list)  # noqa: UP006 - Required for Clevis compatibility
  magic_link_expiry: int = 15
  rate_limit_per_hour: int = 5


@dataclass
class JWTConfig:
  """JWT configuration for session tokens.

  Attributes:
    secret_key: Secret key for signing JWTs
    expiry_days: Number of days before JWT expires
  """

  secret_key: str | None = None
  expiry_days: int = 7


@dataclass
class RoomzConfig:
  """Unified Roomz configuration.

  This dataclass defines all configuration options for roomz applications.
  Configuration can be loaded from TOML files, environment variables, or
  created programmatically.

  Configuration Priority (via Clevis):
    1. CLI arguments (highest priority)
    2. Environment variables (ROOMZ_*, GUNICORN_*)
    3. Project-level TOML (./roomz.toml)
    4. User-level TOML (~/.roomz.toml)
    5. Dataclass defaults (lowest priority)

  Attributes:
    app_uri: Application entry point (module:attribute format)
    name: Application name
    title: Application title
    description: Application description
    version: Application version
    client: Client configuration
    server: Server configuration
    email: Email configuration
    jwt: JWT configuration

  Example:
      >>> config = RoomzConfig(name="roomz", title="Roomz Chat")
      >>> config.name
      'roomz'
      >>> config.server.workers
      1
      >>> config.client.server_url = "http://localhost:5000"
  """

  # Application entry point (required)
  app_uri: str = "roomz.server:asgi_app"

  # Application metadata
  name: str = "roomz"
  title: str = "Roomz Chat"
  description: str = "A real-time chat application"
  version: str | None = None

  # Nested configuration sections
  client: ClientConfig = field(default_factory=ClientConfig)
  server: ServerConfig = field(default_factory=ServerConfig)
  email: EmailConfig = field(default_factory=EmailConfig)
  jwt: JWTConfig = field(default_factory=JWTConfig)
