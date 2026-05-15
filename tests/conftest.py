"""
Pytest fixtures for Roomz testing.

This module provides test fixtures for SocketIO testing, Quart test client,
and mock configurations.
"""

import os
import secrets

import jwt
import pytest

from app import connected_clients, server
from app.auth import (
  JWT_EXPIRY_DAYS,
  _token_versions,
  allowed_emails_manager,
  magic_link_limiter,
  magic_link_manager,
)


@pytest.fixture
def test_client():
  """
  Quart test client fixture for HTTP endpoint testing.

  Provides a test client that can make HTTP requests to the application
  without starting a real server.

  Returns:
    Quart test client instance
  """
  return server.test_client()


@pytest.fixture
def socketio_client():
  """
  SocketIO test client fixture for WebSocket testing.

  Note: AsyncServer doesn't have test_client() like sync Server.
  WebSocket tests are marked as integration tests and require
  a running server. See test_websocket.py for details.

  This fixture is kept for future use when integration test infrastructure
  is set up.
  """
  pytest.skip("WebSocket tests require running server (integration tests)")


@pytest.fixture
def authenticated_socketio_client(sample_email):
  """
  SocketIO test client with valid authentication.

  Note: AsyncServer doesn't have test_client() like sync Server.
  WebSocket tests are marked as integration tests and require
  a running server. See test_websocket.py for details.

  This fixture is kept for future use when integration test infrastructure
  is set up.
  """
  pytest.skip("WebSocket tests require running server (integration tests)")


@pytest.fixture
def connected_clients_tracker():
  """
  In-memory tracker for connected clients.

  Provides access to the connected_clients set used by the server
  to track active connections.

  Returns:
    Set of connected client session IDs
  """
  # Clear before test
  connected_clients.clear()

  yield connected_clients

  # Clear after test
  connected_clients.clear()


# =============================================================================
# Authentication Fixtures (I2-001 Magic Link Authentication)
# =============================================================================


@pytest.fixture
def sample_email():
  """
  Sample email address for testing.

  Returns:
    str: A valid email address for testing
  """
  return "test@example.com"


@pytest.fixture
def sample_magic_link_token():
  """
  Sample magic link token for testing.

  Returns:
    str: A sample token for testing (not cryptographically secure)
  """
  return secrets.token_urlsafe(32)


@pytest.fixture
def authenticated_session(test_client, sample_email, jwt_secret_key, allowed_emails):
  """
  Creates an authenticated session for testing.

  This fixture simulates a user who has completed the magic link
  authentication flow and has a valid JWT token.

  Returns:
    dict: Session data including JWT token and user info
  """
  from app.auth import generate_jwt

  # Set ALLOWED_EMAILS for this test
  os.environ["ALLOWED_EMAILS"] = ",".join(allowed_emails)
  allowed_emails_manager.clear_cache()

  # Generate JWT
  jwt_token = generate_jwt(sample_email)

  yield {"token": jwt_token, "email": sample_email}

  # Cleanup
  _token_versions.clear()
  allowed_emails_manager.clear_cache()


@pytest.fixture
def rate_limiter_state():
  """
  In-memory tracker for rate limiting state.

  Provides access to rate limiter state for testing magic link
  request limits.

  Returns:
    dict: Rate limiter state (email -> request count/timestamps)
  """
  # Reset rate limiter before test
  magic_link_limiter.reset()

  yield magic_link_limiter._requests

  # Clear after test
  magic_link_limiter.reset()


@pytest.fixture(autouse=True)
def cleanup_auth_state():
  """
  Auto-cleanup fixture for authentication state.

  Cleans up magic links, rate limiter, and token versions after each test.
  """
  # Setup: Clear all auth state
  connected_clients.clear()
  magic_link_manager._magic_links.clear()
  magic_link_limiter.reset()
  _token_versions.clear()
  allowed_emails_manager.clear_cache()

  yield

  # Teardown: Clear all auth state
  connected_clients.clear()
  magic_link_manager._magic_links.clear()
  magic_link_limiter.reset()
  _token_versions.clear()
  allowed_emails_manager.clear_cache()


# =============================================================================
# JWT Session Fixtures (I4-001 JWT Session Tokens)
# =============================================================================


@pytest.fixture
def jwt_secret_key():
  """
  JWT secret key for testing.

  Returns:
    str: A test secret key (256 bits, minimum for HS256)
  """
  return "test-secret-key-minimum-32-characters-long-for-security"


@pytest.fixture
def allowed_emails():
  """
  List of allowed emails for testing.

  Returns:
    list: List of allowed email addresses
  """
  return ["alice@example.com", "bob@example.com", "charlie@example.com"]


@pytest.fixture
def sample_jwt_payload(sample_email):
  """
  Sample JWT payload for testing.

  Returns:
    dict: A sample JWT payload with standard claims
  """
  from datetime import datetime, timedelta, timezone

  return {
    "sub": f"user:{sample_email}",
    "email": sample_email,
    "iat": int(datetime.now(timezone.utc).timestamp()),
    "exp": int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp()),
    "channel_token": secrets.token_urlsafe(32),
  }


@pytest.fixture
def expired_jwt_payload(sample_email):
  """
  Expired JWT payload for testing.

  Returns:
    dict: An expired JWT payload (expired 1 hour ago)
  """
  from datetime import datetime, timedelta, timezone

  return {
    "sub": f"user:{sample_email}",
    "email": sample_email,
    "iat": int((datetime.now(timezone.utc) - timedelta(days=31)).timestamp()),
    "exp": int((datetime.now(timezone.utc) - timedelta(hours=1)).timestamp()),
    "channel_token": secrets.token_urlsafe(32),
  }


@pytest.fixture
def token_version_manager():
  """
  Token version manager for testing JWT revocation.

  Returns:
    dict: A simple in-memory token version tracker
  """
  # Token version strategy: {email: int}
  versions = {}

  def get_version(email: str) -> int:
    """Get current token version for email."""
    return versions.get(email.lower().strip(), 1)

  def increment_version(email: str) -> int:
    """Increment token version for email (revoke all tokens)."""
    email = email.lower().strip()
    versions[email] = versions.get(email, 1) + 1
    return versions[email]

  return {
    "get_version": get_version,
    "increment_version": increment_version,
    "versions": versions,
  }