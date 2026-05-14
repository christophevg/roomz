"""
Pytest fixtures for Roomz testing.

This module provides test fixtures for SocketIO testing, Quart test client,
and mock configurations.
"""

import secrets

import pytest

from app import connected_clients, server
from app.auth import magic_link_limiter, magic_link_manager, session_manager


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
def authenticated_session(test_client, sample_email):
  """
  Creates an authenticated session for testing.

  This fixture simulates a user who has completed the magic link
  authentication flow and has a valid session.

  Returns:
    dict: Session data including token and user info
  """
  # Create a session directly
  session_data = session_manager.create_session(
    email=sample_email, client_ip="127.0.0.1", user_agent_hash="test_ua_hash"
  )

  yield session_data

  # Cleanup
  session_manager.revoke_session(session_data["token"])


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

  Cleans up sessions, magic links, and rate limiter after each test.
  """
  # Setup: Clear all auth state
  connected_clients.clear()
  session_manager._sessions.clear()
  magic_link_manager._magic_links.clear()
  magic_link_limiter.reset()

  yield

  # Teardown: Clear all auth state
  connected_clients.clear()
  session_manager._sessions.clear()
  magic_link_manager._magic_links.clear()
  magic_link_limiter.reset()
