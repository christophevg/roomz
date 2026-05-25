"""
Data models for Roomz authentication and session management.

This module defines dataclasses for sessions and magic links.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class Session:
  """
  User session data structure.

  Sessions are created after successful magic link verification
  and track authenticated users.

  Attributes:
    token_hash: SHA-256 hash of the session token
    email: User's email address (lowercase, trimmed)
    created_at: When the session was created
    expires_at: When the session expires (30 days from creation)
    last_activity: Last time the user was active
    client_ip: IP address of the client
    user_agent_hash: SHA-256 hash of user agent string
  """

  token_hash: str
  email: str
  created_at: datetime = field(default_factory=datetime.utcnow)
  expires_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
  last_activity: datetime = field(default_factory=datetime.utcnow)
  client_ip: str | None = None
  user_agent_hash: str | None = None

  def __post_init__(self) -> None:
    """Set default expires_at to 30 days from created_at."""
    if self.expires_at == datetime.now(timezone.utc):
      from datetime import timedelta

      self.expires_at = self.created_at + timedelta(days=30)

  def to_dict(self) -> dict[str, Any]:
    """Convert session to dictionary for storage/serialization."""
    return {
      "token_hash": self.token_hash,
      "email": self.email,
      "created_at": self.created_at.isoformat(),
      "expires_at": self.expires_at.isoformat(),
      "last_activity": self.last_activity.isoformat(),
      "client_ip": self.client_ip,
      "user_agent_hash": self.user_agent_hash,
    }

  @classmethod
  def from_dict(cls, data: dict[str, Any]) -> "Session":
    """Create Session from dictionary."""
    return cls(
      token_hash=data["token_hash"],
      email=data["email"],
      created_at=datetime.fromisoformat(data["created_at"]),
      expires_at=datetime.fromisoformat(data["expires_at"]),
      last_activity=datetime.fromisoformat(data["last_activity"]),
      client_ip=data.get("client_ip"),
      user_agent_hash=data.get("user_agent_hash"),
    )


@dataclass
class MagicLink:
  """
  Magic link token for passwordless authentication.

  Magic links are one-time-use tokens sent to users via email
  (or logged to console in development) for authentication.

  Attributes:
    token_hash: SHA-256 hash of the magic link token
    email: User's email address (lowercase, trimmed)
    created_at: When the magic link was created
    expires_at: When the magic link expires (15 minutes from creation)
    used: Whether the token has been used
  """

  token_hash: str
  email: str
  created_at: datetime = field(default_factory=datetime.utcnow)
  expires_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
  used: bool = False

  def __post_init__(self) -> None:
    """Set default expires_at to 15 minutes from created_at."""
    if self.expires_at == datetime.now(timezone.utc):
      from datetime import timedelta

      self.expires_at = self.created_at + timedelta(minutes=15)

  def to_dict(self) -> dict[str, Any]:
    """Convert magic link to dictionary for storage/serialization."""
    return {
      "token_hash": self.token_hash,
      "email": self.email,
      "created_at": self.created_at.isoformat(),
      "expires_at": self.expires_at.isoformat(),
      "used": self.used,
    }

  @classmethod
  def from_dict(cls, data: dict[str, Any]) -> "MagicLink":
    """Create MagicLink from dictionary."""
    return cls(
      token_hash=data["token_hash"],
      email=data["email"],
      created_at=datetime.fromisoformat(data["created_at"]),
      expires_at=datetime.fromisoformat(data["expires_at"]),
      used=data.get("used", False),
    )
