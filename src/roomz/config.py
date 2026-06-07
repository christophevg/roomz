"""Configuration module for roomz application.

This module provides configuration support using dataclasses and Clevis.
Configuration can be loaded from TOML files, environment variables, or CLI args.
"""

from dataclasses import dataclass, field
from typing import List  # noqa: UP035 - Required for Clevis compatibility


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
  """Roomz application configuration.

  This dataclass defines all configuration options for a roomz application.
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
    server: Server configuration
    email: Email configuration
    jwt: JWT configuration

  Example:
      >>> config = RoomzConfig(name="roomz", title="Roomz Chat")
      >>> config.name
      'roomz'
      >>> config.server.workers
      1
  """

  # Application entry point (required)
  app_uri: str = "roomz.server:asgi_app"

  # Application metadata
  name: str = "roomz"
  title: str = "Roomz Chat"
  description: str = "A real-time chat application"
  version: str | None = None

  # Nested configuration sections
  server: ServerConfig = field(default_factory=ServerConfig)
  email: EmailConfig = field(default_factory=EmailConfig)
  jwt: JWTConfig = field(default_factory=JWTConfig)
