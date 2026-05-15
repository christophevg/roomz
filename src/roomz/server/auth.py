"""
Authentication module for Roomz.

Implements magic link authentication flow with rate limiting,
JWT session tokens, and security features.
"""

import hashlib
import logging
import os
import re
import secrets
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import jwt

from .models import MagicLink

logger = logging.getLogger(__name__)

# =============================================================================
# Configuration Constants
# =============================================================================

# JWT configuration
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_DAYS = int(os.environ.get("JWT_EXPIRY_DAYS", "30"))
JWT_SECRET_KEY_MIN_LENGTH = 32

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


# =============================================================================
# JWT Secret Key Management
# =============================================================================


def get_jwt_secret_key() -> str:
  """
  Get JWT secret key from environment variable.

  The key must be at least 32 characters (256 bits) for HS256 security.

  Returns:
    JWT secret key from environment.

  Raises:
    ValueError: If JWT_SECRET_KEY is not set or too short.
  """
  secret_key = os.environ.get("JWT_SECRET_KEY")

  if not secret_key:
    raise ValueError(
      "JWT_SECRET_KEY environment variable must be set. "
      "Generate with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
    )

  if len(secret_key) < JWT_SECRET_KEY_MIN_LENGTH:
    raise ValueError(
      f"JWT_SECRET_KEY must be at least {JWT_SECRET_KEY_MIN_LENGTH} characters. "
      f"Current length: {len(secret_key)}"
    )

  return secret_key


# =============================================================================
# Allowed Emails Management
# =============================================================================


class AllowedEmailsManager:
  """
  Manages allowed emails list with caching and validation.

  Security considerations:
  - Cached for performance, but refreshed periodically
  - Case-insensitive comparison
  - Validated on every request (not cached in JWT)
  """

  def __init__(self, cache_ttl_seconds: int = 60):
    """
    Initialize allowed emails manager.

    Args:
      cache_ttl_seconds: Time-to-live for cache in seconds.
    """
    self.cache_ttl = timedelta(seconds=cache_ttl_seconds)
    self._cache_time: datetime | None = None
    self._cached_emails: set[str] = set()

  def get_allowed_emails(self) -> set[str]:
    """
    Get allowed emails with caching.

    Returns:
      Set of allowed email addresses (lowercase).
    """
    now = datetime.now(timezone.utc)

    # Check if cache is stale
    if self._cache_time is None or (now - self._cache_time) > self.cache_ttl:
      self._refresh_cache()

    return self._cached_emails

  def _refresh_cache(self):
    """Refresh cache from environment variable."""
    emails_str = os.environ.get("ALLOWED_EMAILS", "")

    # Parse and normalize
    self._cached_emails = set(
      email.strip().lower() for email in emails_str.split(",") if email.strip()
    )

    self._cache_time = datetime.now(timezone.utc)

    logger.debug(f"Refreshed ALLOWED_EMAILS cache: {len(self._cached_emails)} emails")

  def is_allowed(self, email: str) -> bool:
    """
    Check if email is allowed.

    Args:
      email: Email address to check.

    Returns:
      True if email is in allowed list.
    """
    if not email:
      return False

    # Case-insensitive comparison
    return email.strip().lower() in self.get_allowed_emails()

  def clear_cache(self):
    """Force cache refresh on next request."""
    self._cache_time = None


# Global instance
allowed_emails_manager = AllowedEmailsManager()


def is_email_allowed(email: str) -> bool:
  """
  Check if email is in ALLOWED_EMAILS.

  Args:
    email: Email address to check.

  Returns:
    True if email is in allowed list.
  """
  return allowed_emails_manager.is_allowed(email)


# =============================================================================
# Token Version Management (for Revocation)
# =============================================================================

# In-memory token version storage: {email: version}
# Note: This is ephemeral - versions reset on server restart
# For production, use persistent storage (Redis, database)
_token_versions: dict[str, int] = {}


def get_token_version(email: str) -> int:
  """
  Get current token version for user.

  The token version is used for revocation - incrementing the version
  invalidates all existing tokens for that user.

  Args:
    email: User's email address.

  Returns:
    Current token version (defaults to 1 for new users).
  """
  return _token_versions.get(email.lower().strip(), 1)


def increment_token_version(email: str) -> int:
  """
  Increment token version for user (revokes all existing tokens).

  Args:
    email: User's email address.

  Returns:
    New token version.
  """
  email_lower = email.lower().strip()
  current_version = _token_versions.get(email_lower, 1)
  new_version = current_version + 1
  _token_versions[email_lower] = new_version

  logger.info(f"Token version incremented for {email}: {current_version} -> {new_version}")

  return new_version


# =============================================================================
# JWT Generation and Validation
# =============================================================================


def generate_jwt(email: str) -> str:
  """
  Generate JWT for authenticated user.

  JWT includes:
  - sub: Subject identifier (user:{email})
  - email: User's email address
  - iat: Issued at timestamp
  - exp: Expiration timestamp (30 days)
  - channel_token: UUID for private channel access
  - ver: Token version for revocation

  Args:
    email: User's email address.

  Returns:
    JWT token string.

  Raises:
    ValueError: If JWT_SECRET_KEY is not set or too short.
  """
  secret_key = get_jwt_secret_key()
  now = datetime.now(timezone.utc)

  # Normalize email
  email_lower = email.lower().strip()

  # Generate unique channel token
  channel_token = secrets.token_urlsafe(32)

  payload = {
    "sub": f"user:{email_lower}",
    "email": email_lower,
    "iat": int(now.timestamp()),
    "exp": int((now + timedelta(days=JWT_EXPIRY_DAYS)).timestamp()),
    "channel_token": channel_token,
    "ver": get_token_version(email_lower),
  }

  # SECURITY: Algorithm is hardcoded, never from token header
  token = jwt.encode(payload, secret_key, algorithm=JWT_ALGORITHM)

  logger.info(f"Generated JWT for {email_lower}")

  return token


def validate_jwt(token: str) -> dict | None:
  """
  Validate JWT session token.

  Security checks:
  - Algorithm is hardcoded to HS256 (never from token header)
  - "none" algorithm is explicitly rejected
  - Signature verification
  - Expiration check
  - ALLOWED_EMAILS validation
  - Token version check

  Args:
    token: JWT token string to validate.

  Returns:
    JWT payload dict if valid, None otherwise.
  """
  if not token:
    return None

  try:
    # Check for "none" algorithm explicitly (defense in depth)
    # Note: PyJWT already rejects "none" when algorithms=["HS256"]
    # This is an additional security check
    try:
      header = jwt.get_unverified_header(token)
      if header.get("alg", "").lower() == "none":
        logger.warning("Rejected JWT with 'none' algorithm")
        return None
    except Exception:
      # If we can't decode the header, proceed to regular validation
      pass

    # SECURITY: algorithms parameter forces algorithm verification
    # Library will reject token if alg header differs from allowed list
    secret_key = get_jwt_secret_key()
    payload = jwt.decode(
      token,
      secret_key,
      algorithms=[JWT_ALGORITHM],  # ONLY allow HS256
      options={
        "verify_exp": True,
        "verify_iat": True,
        "require": ["exp", "iat", "email", "channel_token"],
      },
    )

    # Extract email
    email = payload.get("email")
    if not email:
      logger.warning("JWT missing email claim")
      return None

    # SECURITY: Check ALLOWED_EMAILS on every request
    if not is_email_allowed(email):
      logger.warning(f"Email not in ALLOWED_EMAILS: {email}")
      return None

    # Check token version for revocation
    current_version = get_token_version(email)
    token_version = payload.get("ver", 1)

    if token_version != current_version:
      logger.info(f"Token version mismatch for {email}: {token_version} != {current_version}")
      return None

    return payload

  except jwt.ExpiredSignatureError:
    logger.debug("JWT expired")
    return None
  except jwt.InvalidTokenError as e:
    logger.warning(f"Invalid JWT: {e}")
    return None
  except ValueError as e:
    # JWT_SECRET_KEY validation error
    logger.error(f"JWT secret key error: {e}")
    return None
  except Exception as e:
    logger.error(f"Unexpected error validating JWT: {e}")
    return None


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
magic_link_manager = MagicLinkManager()
