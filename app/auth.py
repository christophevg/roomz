"""
Authentication module for Roomz.

Implements magic link authentication flow with rate limiting,
session management, and security features.
"""

import hashlib
import logging
import re
import secrets
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from .models import MagicLink, Session

logger = logging.getLogger(__name__)

# =============================================================================
# Configuration Constants
# =============================================================================

# Session configuration
SESSION_TIMEOUT_DAYS = 30
INACTIVITY_TIMEOUT_DAYS = 7

# Magic link configuration
MAGIC_LINK_EXPIRY_MINUTES = 15
MAGIC_LINK_RATE_LIMIT = 5  # requests per email per hour

# Rate limiting configuration
RATE_LIMIT_WINDOW_HOURS = 1


def is_valid_email(email: str) -> bool:
  """
  Validate email format following RFC 5322 basic rules.

  Args:
    email: Email address to validate

  Returns:
    True if email is valid, False otherwise
  """
  if not email or len(email) > 255:
    return False

  # Basic RFC 5322 pattern
  pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
  if not re.match(pattern, email):
    return False

  # Local part max length check
  parts = email.split("@")
  if len(parts[0]) > 64:
    return False

  return True


class RateLimiter:
  """
  Rate limiter for magic link requests.

  Prevents magic link spam by limiting requests per email per hour.
  """

  def __init__(self, max_requests: int = 5, window_hours: int = 1):
    """
    Initialize rate limiter.

    Args:
      max_requests: Maximum requests allowed per window
      window_hours: Time window in hours
    """
    self.max_requests = max_requests
    self.window = timedelta(hours=window_hours)
    # Track requests per email: {email: [(timestamp, ip), ...]}
    self._requests: dict[str, list] = defaultdict(list)

  def is_allowed(self, email: str, client_ip: str | None = None) -> bool:
    """
    Check if request is allowed for given email.

    Args:
      email: Email address making request
      client_ip: Optional client IP (for future IP-based limiting)

    Returns:
      True if request is allowed, False if rate limit exceeded
    """
    now = datetime.now(timezone.utc)
    email_lower = email.lower()

    # Clean up old requests
    self._requests[email_lower] = [
      (ts, ip) for ts, ip in self._requests[email_lower] if now - ts < self.window
    ]

    # Check if limit exceeded
    if len(self._requests[email_lower]) >= self.max_requests:
      return False

    # Record new request
    self._requests[email_lower].append((now, client_ip))
    return True

  def get_remaining_requests(self, email: str) -> int:
    """
    Get number of remaining requests for email.

    Args:
      email: Email address to check

    Returns:
      Number of remaining requests in current window
    """
    now = datetime.now(timezone.utc)
    email_lower = email.lower()

    # Clean up old requests
    self._requests[email_lower] = [
      (ts, ip) for ts, ip in self._requests[email_lower] if now - ts < self.window
    ]

    return max(0, self.max_requests - len(self._requests[email_lower]))

  def reset(self, email: str | None = None):
    """
    Reset rate limiter state (for testing).

    Args:
      email: Optional specific email to reset, or all if None
    """
    if email:
      self._requests.pop(email.lower(), None)
    else:
      self._requests.clear()


class SessionManager:
  """
  Manages user sessions.

  Handles session creation, validation, revocation, and cleanup.
  """

  def __init__(
    self,
    session_timeout_days: int = SESSION_TIMEOUT_DAYS,
    inactivity_timeout_days: int = INACTIVITY_TIMEOUT_DAYS,
  ):
    """
    Initialize session manager.

    Args:
      session_timeout_days: Maximum session lifetime in days
      inactivity_timeout_days: Days of inactivity before expiration
    """
    self.session_timeout = timedelta(days=session_timeout_days)
    self.inactivity_timeout = timedelta(days=inactivity_timeout_days)
    # In-memory storage: {token_hash: Session}
    self._sessions: dict[str, Session] = {}

  def create_session(
    self, email: str, client_ip: str | None = None, user_agent_hash: str | None = None
  ) -> dict:
    """
    Create a new session for authenticated user.

    Args:
      email: User's email address
      client_ip: Optional client IP address
      user_agent_hash: Optional hash of user agent string

    Returns:
      Session data including token (only returned on creation)
    """
    # Generate secure token
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    # Create session
    now = datetime.now(timezone.utc)
    session = Session(
      token_hash=token_hash,
      email=email.lower().strip(),
      created_at=now,
      expires_at=now + self.session_timeout,
      last_activity=now,
      client_ip=client_ip,
      user_agent_hash=user_agent_hash,
    )

    # Store session
    self._sessions[token_hash] = session

    logger.info(f"Created session for {email}")

    # Return session with token (only time token is available)
    return {
      "token": token,
      "token_hash": token_hash,
      "email": session.email,
      "created_at": session.created_at.isoformat(),
      "expires_at": session.expires_at.isoformat(),
    }

  def validate_token(self, token: str) -> Session | None:
    """
    Validate session token and return session if valid.

    Also checks expiration and inactivity timeout.

    Args:
      token: Session token to validate

    Returns:
      Session if valid, None otherwise
    """
    if not token:
      return None

    # Hash token
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    # Look up session
    session = self._sessions.get(token_hash)
    if not session:
      return None

    # Check expiration
    now = datetime.now(timezone.utc)
    if now > session.expires_at:
      logger.info(f"Session expired for {session.email}")
      self._sessions.pop(token_hash, None)
      return None

    # Check inactivity timeout
    if now - session.last_activity > self.inactivity_timeout:
      logger.info(f"Session inactive for {session.email}")
      self._sessions.pop(token_hash, None)
      return None

    # Update last activity
    session.last_activity = now

    return session

  def revoke_session(self, token: str) -> bool:
    """
    Revoke (delete) a session.

    Args:
      token: Session token to revoke

    Returns:
      True if session was revoked, False if not found
    """
    if not token:
      return False

    token_hash = hashlib.sha256(token.encode()).hexdigest()

    if token_hash in self._sessions:
      session = self._sessions.pop(token_hash)
      logger.info(f"Revoked session for {session.email}")
      return True

    return False

  def get_session_by_hash(self, token_hash: str) -> Session | None:
    """
    Get session by token hash (for WebSocket authentication).

    Args:
      token_hash: SHA-256 hash of session token

    Returns:
      Session if found, None otherwise
    """
    return self._sessions.get(token_hash)

  def cleanup_expired(self):
    """
    Remove expired sessions from storage.

    Should be called periodically to prevent memory leaks.
    """
    now = datetime.now(timezone.utc)
    expired_hashes = [
      token_hash
      for token_hash, session in self._sessions.items()
      if now > session.expires_at or now - session.last_activity > self.inactivity_timeout
    ]

    for token_hash in expired_hashes:
      self._sessions.pop(token_hash, None)

    if expired_hashes:
      logger.info(f"Cleaned up {len(expired_hashes)} expired sessions")


class MagicLinkManager:
  """
  Manages magic link tokens for authentication.

  Handles token generation, validation, and cleanup.
  """

  def __init__(self, token_expiry_minutes: int = MAGIC_LINK_EXPIRY_MINUTES):
    """
    Initialize magic link manager.

    Args:
      token_expiry_minutes: Magic link lifetime in minutes
    """
    self.token_expiry = timedelta(minutes=token_expiry_minutes)
    # In-memory storage: {token_hash: MagicLink}
    self._magic_links: dict[str, MagicLink] = {}

  def create_magic_link(self, email: str) -> str:
    """
    Generate a new magic link token.

    Args:
      email: User's email address

    Returns:
      Magic link token (only returned on creation)
    """
    # Generate secure token
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    # Create magic link
    now = datetime.now(timezone.utc)
    magic_link = MagicLink(
      token_hash=token_hash,
      email=email.lower().strip(),
      created_at=now,
      expires_at=now + self.token_expiry,
      used=False,
    )

    # Store magic link
    self._magic_links[token_hash] = magic_link

    logger.info(f"Created magic link for {email}")

    return token

  def validate_token(self, token: str) -> MagicLink | None:
    """
    Validate magic link token and return magic link if valid.

    Checks expiration and marks token as used (single-use).

    Args:
      token: Magic link token to validate

    Returns:
      MagicLink if valid, None otherwise
    """
    if not token:
      return None

    # Hash token
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    # Look up magic link
    magic_link = self._magic_links.get(token_hash)
    if not magic_link:
      return None

    # Check if already used
    if magic_link.used:
      logger.warning(f"Magic link already used for {magic_link.email}")
      return None

    # Check expiration
    now = datetime.now(timezone.utc)
    if now > magic_link.expires_at:
      logger.warning(f"Magic link expired for {magic_link.email}")
      return None

    # Mark as used (single-use)
    magic_link.used = True

    return magic_link

  def cleanup_expired(self):
    """
    Remove expired and used magic links from storage.

    Should be called periodically to prevent memory leaks.
    """
    now = datetime.now(timezone.utc)
    expired_hashes = [
      token_hash
      for token_hash, magic_link in self._magic_links.items()
      if now > magic_link.expires_at or magic_link.used
    ]

    for token_hash in expired_hashes:
      self._magic_links.pop(token_hash, None)

    if expired_hashes:
      logger.info(f"Cleaned up {len(expired_hashes)} expired/used magic links")

  def remove_token(self, token_hash: str):
    """
    Remove a magic link by token hash.

    Args:
      token_hash: SHA-256 hash of magic link token
    """
    self._magic_links.pop(token_hash, None)


# Global instances (shared across requests)
magic_link_limiter = RateLimiter(
  max_requests=MAGIC_LINK_RATE_LIMIT, window_hours=RATE_LIMIT_WINDOW_HOURS
)
session_manager = SessionManager()
magic_link_manager = MagicLinkManager()
