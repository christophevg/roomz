"""
Tests for Session Management functionality.

This module tests session lifecycle, persistence, expiration,
and security features.

NOTE: The SessionManager class has been removed and replaced with JWT sessions.
The tests in this file are skipped until they are updated for JWT.

See tests/test_jwt_*.py for JWT session tests.

Requirements: FR-1.4.1, FR-1.4.2 (from functional analysis)
- JWT tokens replace in-memory session storage
- Sessions persist across server restarts (stateless JWT)
- ALLOWED_EMAILS validation on every request
"""

import hashlib
from datetime import datetime, timedelta, timezone

import pytest

from app.auth import (
  magic_link_manager,
)

# All session tests are skipped - SessionManager has been replaced with JWT
# See tests/test_jwt_unit.py, tests/test_jwt_security.py, tests/test_jwt_integration.py


@pytest.mark.skip(reason="SessionManager removed - use JWT instead")
class TestSessionCreation:
  """Test suite for session creation functionality."""

  async def test_session_created_on_successful_auth(self, test_client):
    pytest.skip("SessionManager removed - use JWT instead")

  def test_session_token_generated_securely(self):
    pytest.skip("SessionManager removed - use JWT instead")


@pytest.mark.skip(reason="SessionManager removed - use JWT instead")
class TestSessionPersistence:
  """Test suite for session persistence functionality."""

  async def test_session_persists_in_httponly_cookie(self, test_client):
    pytest.skip("SessionManager removed - use JWT instead")

  async def test_session_resume_with_valid_cookie(self, test_client):
    pytest.skip("SessionManager removed - use JWT instead")


@pytest.mark.skip(reason="SessionManager removed - use JWT instead")
class TestSessionExpiration:
  """Test suite for session expiration functionality."""

  def test_expired_session_rejected(self):
    pytest.skip("SessionManager removed - use JWT instead")

  def test_session_expiration_check_on_websocket_connect(self):
    pytest.skip("SessionManager removed - use JWT instead")


@pytest.mark.skip(reason="SessionManager removed - use JWT instead")
class TestSessionSecurity:
  """Test suite for session security features."""

  def test_session_token_unpredictable(self):
    pytest.skip("SessionManager removed - use JWT instead")

  async def test_session_cookie_not_accessible_via_javascript(self, test_client):
    pytest.skip("SessionManager removed - use JWT instead")


@pytest.mark.skip(reason="SessionManager removed - use JWT instead")
class TestSessionCleanup:
  """Test suite for session cleanup functionality."""

  def test_expired_sessions_cleaned_up(self):
    pytest.skip("SessionManager removed - use JWT instead")


class TestMagicLinkCleanup:
  """Test suite for magic link cleanup (still in use)."""

  def test_used_magic_links_cleaned_up(self):
    """Test that used magic links are cleaned up."""
    # Create magic link
    token = magic_link_manager.create_magic_link("used@test.com")

    # Use it
    magic_link = magic_link_manager.validate_token(token)

    # It should be marked as used
    assert magic_link.used

    # Verify it directly
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    magic_link_direct = magic_link_manager._magic_links.get(token_hash)
    assert magic_link_direct.used

  def test_expired_magic_links_cleaned_up(self):
    """Test that expired magic links are cleaned up."""
    # Create magic link
    token = magic_link_manager.create_magic_link("expired@test.com")

    # Manually expire it
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    magic_link = magic_link_manager._magic_links.get(token_hash)
    magic_link.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)

    # Run cleanup
    magic_link_manager.cleanup_expired()

    # Magic link should be removed
    assert magic_link_manager._magic_links.get(token_hash) is None


# Note: For JWT session tests, see:
# - tests/test_jwt_unit.py - Unit tests for JWT functions
# - tests/test_jwt_security.py - Security tests for JWT
# - tests/test_jwt_integration.py - Integration tests for JWT authentication flow
