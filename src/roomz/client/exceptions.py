"""
Client Exceptions

Exception hierarchy for the Roomz client library.
"""


class ClientError(Exception):
  """Base exception for all client errors."""

  pass


class ConfigurationError(ClientError):
  """Configuration error (missing or invalid configuration)."""

  pass


class ConnectionError(ClientError):
  """Failed to establish or maintain WebSocket connection."""

  pass


class AuthenticationError(ClientError):
  """Authentication failed."""

  pass


class SecurityError(ClientError):
  """Security violation detected."""

  pass
