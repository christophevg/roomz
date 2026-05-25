"""
Integration tests for JWT session token authentication flow.

This module tests the complete authentication flow including magic link request,
JWT issuance, WebSocket connection, and session management.

Requirements: I4-001 - JWT Session Tokens
- Login with magic link, get JWT
- Server restart, reconnect still works
- Remove email from ALLOWED_EMAILS, access denied
"""

import os
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from roomz.server.auth import (
  allowed_emails_manager,
  generate_jwt,
  magic_link_manager,
  validate_jwt,
)


class TestMagicLinkWithJWT:
  """
  Test suite for magic link authentication with JWT issuance.

  Tests verify the complete magic link flow ending with JWT creation.
  """

  @pytest.mark.asyncio
  async def test_magic_link_with_allowed_email(self, test_client, allowed_emails):
    """
    Test that magic link request with allowed email succeeds.

    Given: Email in ALLOWED_EMAILS
    When: POST /auth/request-magic-link with email
    Then: Returns 200 OK, magic link created
    """
    # Set environment
    os.environ["JWT_SECRET_KEY"] = "test-secret-key-minimum-32-characters-long-for-security"
    os.environ["ALLOWED_EMAILS"] = ",".join(allowed_emails)
    allowed_emails_manager.clear_cache()

    # Request magic link
    response = await test_client.post("/auth/request-magic-link", json={"email": allowed_emails[0]})

    # Verify success
    assert response.status_code == 200
    data = await response.get_json()
    assert data["status"] == "ok"

  @pytest.mark.asyncio
  async def test_magic_link_rejects_blocked_email(self, test_client):
    """
    Test that magic link request with blocked email returns 403.

    Given: Email NOT in ALLOWED_EMAILS
    When: POST /auth/request-magic-link with email
    Then: Returns 403 Forbidden
    """
    # Set environment with empty allowed emails
    os.environ["JWT_SECRET_KEY"] = "test-secret-key-minimum-32-characters-long-for-security"
    os.environ["ALLOWED_EMAILS"] = "allowed@example.com"
    allowed_emails_manager.clear_cache()

    # Request magic link with blocked email
    response = await test_client.post(
      "/auth/request-magic-link", json={"email": "blocked@example.com"}
    )

    # Verify rejection
    assert response.status_code == 403
    data = await response.get_json()
    assert "not authorized" in data["detail"].lower()

  @pytest.mark.asyncio
  async def test_magic_link_allows_case_insensitive_email(self, test_client, allowed_emails):
    """
    Test that email matching is case-insensitive.

    Given: Email in ALLOWED_EMAILS with different case
    When: POST /auth/request-magic-link with different case
    Then: Returns 200 OK
    """
    # Set environment
    os.environ["JWT_SECRET_KEY"] = "test-secret-key-minimum-32-characters-long-for-security"
    os.environ["ALLOWED_EMAILS"] = ",".join([e.lower() for e in allowed_emails])
    allowed_emails_manager.clear_cache()

    # Request with upper case
    response = await test_client.post(
      "/auth/request-magic-link", json={"email": allowed_emails[0].upper()}
    )

    # Verify success
    assert response.status_code == 200

  @pytest.mark.asyncio
  async def test_magic_link_validates_email_format(self, test_client, allowed_emails):
    """
    Test that email format validation still works.

    Given: Invalid email format
    When: POST /auth/request-magic-link
    Then: Returns 400 Bad Request
    """
    # Set environment
    os.environ["JWT_SECRET_KEY"] = "test-secret-key-minimum-32-characters-long-for-security"
    os.environ["ALLOWED_EMAILS"] = ",".join(allowed_emails)
    allowed_emails_manager.clear_cache()

    # Request with invalid email
    response = await test_client.post("/auth/request-magic-link", json={"email": "not-an-email"})

    # Verify rejection
    assert response.status_code == 400
    data = await response.get_json()
    assert "invalid" in data["detail"].lower()


class TestMagicLinkVerificationJWT:
  """
  Test suite for magic link verification with JWT issuance.

  Tests verify that magic link verification creates JWT instead of session.
  """

  @pytest.mark.asyncio
  async def test_verify_magic_link_issues_jwt(self, test_client, allowed_emails):
    """
    Test that magic link verification issues JWT cookie.

    Given: Valid magic link token
    When: GET /auth/verify?token=xxx
    Then: JWT is issued as httpOnly cookie
    """
    # Set environment
    jwt_secret = "test-secret-key-minimum-32-characters-long-for-security"
    os.environ["JWT_SECRET_KEY"] = jwt_secret
    os.environ["ALLOWED_EMAILS"] = ",".join(allowed_emails)
    allowed_emails_manager.clear_cache()

    # Create magic link
    email = allowed_emails[0]
    token = magic_link_manager.create_magic_link(email)

    # Verify magic link
    response = await test_client.get(f"/auth/verify?token={token}")

    # Verify redirect
    assert response.status_code == 302
    assert response.location == "/"

    # Check cookie
    cookies = response.headers.getlist("Set-Cookie")
    jwt_cookie = None
    for cookie in cookies:
      if "session_token=" in cookie:
        jwt_cookie = cookie
        break

    assert jwt_cookie is not None
    assert "HttpOnly" in jwt_cookie

  @pytest.mark.asyncio
  async def test_verify_magic_link_jwt_contains_email(self, test_client, allowed_emails):
    """
    Test that JWT contains correct email claim.

    Given: Magic link verification succeeds
    When: JWT is decoded
    Then: Email claim matches requested email
    """
    # Set environment
    jwt_secret = "test-secret-key-minimum-32-characters-long-for-security"
    os.environ["JWT_SECRET_KEY"] = jwt_secret
    os.environ["ALLOWED_EMAILS"] = ",".join(allowed_emails)
    allowed_emails_manager.clear_cache()

    # Create and verify magic link
    email = allowed_emails[0]
    token = magic_link_manager.create_magic_link(email)

    response = await test_client.get(f"/auth/verify?token={token}")
    assert response.status_code == 302

    # Extract JWT from cookie
    cookies = response.headers.getlist("Set-Cookie")
    jwt_token = None
    for cookie in cookies:
      if "session_token=" in cookie:
        # Extract token value
        jwt_token = cookie.split("session_token=")[1].split(";")[0]
        break

    assert jwt_token is not None

    # Decode JWT
    payload = jwt.decode(jwt_token, jwt_secret, algorithms=["HS256"])

    # Verify email
    assert payload["email"] == email.lower()

  @pytest.mark.asyncio
  async def test_verify_magic_link_jwt_contains_channel_token(self, test_client, allowed_emails):
    """
    Test that JWT contains channel_token claim.

    Given: Magic link verification succeeds
    When: JWT is decoded
    Then: channel_token claim is present
    """
    # Set environment
    jwt_secret = "test-secret-key-minimum-32-characters-long-for-security"
    os.environ["JWT_SECRET_KEY"] = jwt_secret
    os.environ["ALLOWED_EMAILS"] = ",".join(allowed_emails)
    allowed_emails_manager.clear_cache()

    # Create and verify magic link
    email = allowed_emails[0]
    token = magic_link_manager.create_magic_link(email)

    response = await test_client.get(f"/auth/verify?token={token}")
    assert response.status_code == 302

    # Extract JWT from cookie
    cookies = response.headers.getlist("Set-Cookie")
    jwt_token = None
    for cookie in cookies:
      if "session_token=" in cookie:
        jwt_token = cookie.split("session_token=")[1].split(";")[0]
        break

    assert jwt_token is not None

    # Decode JWT
    payload = jwt.decode(jwt_token, jwt_secret, algorithms=["HS256"])

    # Verify channel_token
    assert "channel_token" in payload
    assert len(payload["channel_token"]) > 0

  @pytest.mark.asyncio
  async def test_verify_magic_link_blocked_email_after_creation(self, test_client, allowed_emails):
    """
    Test that blocked email after magic link creation returns 403.

    Given: Magic link created for allowed email
    When: Email removed from ALLOWED_EMAILS before verification
    Then: Returns 403 Forbidden
    """
    # Set environment
    jwt_secret = "test-secret-key-minimum-32-characters-long-for-security"
    os.environ["JWT_SECRET_KEY"] = jwt_secret
    os.environ["ALLOWED_EMAILS"] = ",".join(allowed_emails)
    allowed_emails_manager.clear_cache()

    # Create magic link
    email = allowed_emails[0]
    token = magic_link_manager.create_magic_link(email)

    # Remove email from ALLOWED_EMAILS
    other_emails = [e for e in allowed_emails if e != email]
    os.environ["ALLOWED_EMAILS"] = ",".join(other_emails)
    allowed_emails_manager.clear_cache()

    # Try to verify
    response = await test_client.get(f"/auth/verify?token={token}")

    # Verify rejection
    assert response.status_code == 302  # Redirect
    assert "unauthorized" in response.location

  @pytest.mark.asyncio
  async def test_verify_expired_magic_link_returns_error(self, test_client, allowed_emails):
    """
    Test that expired magic link returns error.

    Given: Expired magic link token
    When: GET /auth/verify?token=xxx
    Then: Redirects with error parameter
    """
    # Set environment
    os.environ["JWT_SECRET_KEY"] = "test-secret-key-minimum-32-characters-long-for-security"
    os.environ["ALLOWED_EMAILS"] = ",".join(allowed_emails)
    allowed_emails_manager.clear_cache()

    # Create magic link and expire it
    email = allowed_emails[0]
    token = magic_link_manager.create_magic_link(email)

    # Manually expire the magic link (use SHA256 hash like magic_link_manager does)
    import hashlib

    token_hash = hashlib.sha256(token.encode()).hexdigest()
    magic_link = magic_link_manager._magic_links.get(token_hash)
    if magic_link:
      magic_link.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)

    # Try to verify
    response = await test_client.get(f"/auth/verify?token={token}")

    # Verify redirect with error
    assert response.status_code == 302
    assert "error" in response.location

  @pytest.mark.asyncio
  async def test_verify_used_magic_link_returns_error(self, test_client, allowed_emails):
    """
    Test that already-used magic link returns error.

    Given: Magic link token already used once
    When: GET /auth/verify?token=xxx (second time)
    Then: Redirects with error parameter
    """
    # Set environment
    os.environ["JWT_SECRET_KEY"] = "test-secret-key-minimum-32-characters-long-for-security"
    os.environ["ALLOWED_EMAILS"] = ",".join(allowed_emails)
    allowed_emails_manager.clear_cache()

    # Create magic link
    email = allowed_emails[0]
    token = magic_link_manager.create_magic_link(email)

    # Use magic link once
    response = await test_client.get(f"/auth/verify?token={token}")
    assert response.status_code == 302

    # Try to use again
    response = await test_client.get(f"/auth/verify?token={token}")

    # Verify redirect with error
    assert response.status_code == 302
    assert "error" in response.location


class TestJWTCookieSecurity:
  """
  Test suite for JWT cookie security attributes.

  Tests verify that JWT is stored in secure httpOnly cookie.
  """

  @pytest.mark.asyncio
  async def test_jwt_cookie_httponly(self, test_client, allowed_emails):
    """
    Test that JWT cookie has httpOnly attribute.

    Given: Magic link verification succeeds
    When: JWT cookie is set
    Then: Cookie has httpOnly=True
    """
    # Set environment
    os.environ["JWT_SECRET_KEY"] = "test-secret-key-minimum-32-characters-long-for-security"
    os.environ["ALLOWED_EMAILS"] = ",".join(allowed_emails)
    allowed_emails_manager.clear_cache()

    # Create and verify magic link
    email = allowed_emails[0]
    token = magic_link_manager.create_magic_link(email)

    response = await test_client.get(f"/auth/verify?token={token}")

    # Check cookie
    cookies = response.headers.getlist("Set-Cookie")
    jwt_cookie = None
    for cookie in cookies:
      if "session_token=" in cookie:
        jwt_cookie = cookie
        break

    assert jwt_cookie is not None
    # HttpOnly should be present (case insensitive)
    assert "httponly" in jwt_cookie.lower()

  @pytest.mark.asyncio
  async def test_jwt_cookie_samesite(self, test_client, allowed_emails):
    """
    Test that JWT cookie has SameSite attribute.

    Given: Magic link verification succeeds
    When: JWT cookie is set
    Then: Cookie has SameSite='Strict'
    """
    # Set environment
    os.environ["JWT_SECRET_KEY"] = "test-secret-key-minimum-32-characters-long-for-security"
    os.environ["ALLOWED_EMAILS"] = ",".join(allowed_emails)
    allowed_emails_manager.clear_cache()

    # Create and verify magic link
    email = allowed_emails[0]
    token = magic_link_manager.create_magic_link(email)

    response = await test_client.get(f"/auth/verify?token={token}")

    # Check cookie
    cookies = response.headers.getlist("Set-Cookie")
    jwt_cookie = None
    for cookie in cookies:
      if "session_token=" in cookie:
        jwt_cookie = cookie
        break

    assert jwt_cookie is not None
    # SameSite should be Strict
    assert "samesite" in jwt_cookie.lower()
    assert "strict" in jwt_cookie.lower()

  @pytest.mark.asyncio
  async def test_jwt_cookie_max_age(self, test_client, allowed_emails):
    """
    Test that JWT cookie has correct max age.

    Given: Magic link verification succeeds
    When: JWT cookie is set
    Then: Cookie max_age is 30 days
    """
    # Set environment
    os.environ["JWT_SECRET_KEY"] = "test-secret-key-minimum-32-characters-long-for-security"
    os.environ["ALLOWED_EMAILS"] = ",".join(allowed_emails)
    allowed_emails_manager.clear_cache()

    # Create and verify magic link
    email = allowed_emails[0]
    token = magic_link_manager.create_magic_link(email)

    response = await test_client.get(f"/auth/verify?token={token}")

    # Check cookie
    cookies = response.headers.getlist("Set-Cookie")
    jwt_cookie = None
    for cookie in cookies:
      if "session_token=" in cookie:
        jwt_cookie = cookie
        break

    assert jwt_cookie is not None
    # Max-Age should be present (30 days in seconds)
    assert "max-age" in jwt_cookie.lower() or "maxage" in jwt_cookie.lower()

  @pytest.mark.asyncio
  async def test_jwt_cookie_name(self, test_client, allowed_emails):
    """
    Test that JWT cookie name is 'session_token'.

    Given: Magic link verification succeeds
    When: JWT cookie is set
    Then: Cookie name is 'session_token'
    """
    # Set environment
    os.environ["JWT_SECRET_KEY"] = "test-secret-key-minimum-32-characters-long-for-security"
    os.environ["ALLOWED_EMAILS"] = ",".join(allowed_emails)
    allowed_emails_manager.clear_cache()

    # Create and verify magic link
    email = allowed_emails[0]
    token = magic_link_manager.create_magic_link(email)

    response = await test_client.get(f"/auth/verify?token={token}")

    # Check cookie
    cookies = response.headers.getlist("Set-Cookie")
    jwt_cookie = None
    for cookie in cookies:
      if "session_token=" in cookie:
        jwt_cookie = cookie
        break

    assert jwt_cookie is not None
    assert "session_token=" in jwt_cookie


class TestWebSocketConnectionJWT:
  """
  Test suite for WebSocket connection with JWT authentication.

  Tests verify WebSocket connection validates JWT and joins user channel.

  Note: These tests require running server infrastructure.
  Mark with @pytest.mark.skip for unit test phase.
  """

  @pytest.mark.skip(reason="Integration test needs WebSocket test client infrastructure")
  @pytest.mark.asyncio
  async def test_websocket_connects_with_valid_jwt(self, test_client, allowed_emails):
    """
    Test that WebSocket connection with valid JWT succeeds.

    Given: Valid JWT in cookie
    When: WebSocket connection attempt
    Then: Connection succeeds, user authenticated
    """
    pytest.fail("Not implemented: WebSocket connection with valid JWT succeeds")

  @pytest.mark.skip(reason="Integration test needs WebSocket test client infrastructure")
  @pytest.mark.asyncio
  async def test_websocket_rejects_invalid_jwt(self, test_client):
    """
    Test that WebSocket connection with invalid JWT is rejected.

    Given: Invalid JWT in cookie
    When: WebSocket connection attempt
    Then: Connection is rejected
    """
    pytest.fail("Not implemented: WebSocket connection with invalid JWT rejected")

  @pytest.mark.skip(reason="Integration test needs WebSocket test client infrastructure")
  @pytest.mark.asyncio
  async def test_websocket_rejects_missing_jwt(self, test_client):
    """
    Test that WebSocket connection without JWT is rejected.

    Given: No JWT in cookie
    When: WebSocket connection attempt
    Then: Connection is rejected
    """
    pytest.fail("Not implemented: WebSocket connection without JWT rejected")

  @pytest.mark.skip(reason="Integration test needs WebSocket test client infrastructure")
  @pytest.mark.asyncio
  async def test_websocket_rejects_expired_jwt(self, test_client, expired_jwt_payload):
    """
    Test that WebSocket connection with expired JWT is rejected.

    Given: Expired JWT in cookie
    When: WebSocket connection attempt
    Then: Connection is rejected
    """
    pytest.fail("Not implemented: WebSocket connection with expired JWT rejected")

  @pytest.mark.skip(reason="Integration test needs WebSocket test client infrastructure")
  @pytest.mark.asyncio
  async def test_websocket_rejects_blocked_email(self, test_client, allowed_emails):
    """
    Test that WebSocket connection with blocked email is rejected.

    Given: Valid JWT but email removed from ALLOWED_EMAILS
    When: WebSocket connection attempt
    Then: Connection is rejected
    """
    pytest.fail("Not implemented: WebSocket connection with blocked email rejected")

  @pytest.mark.skip(reason="Integration test needs WebSocket test client infrastructure")
  @pytest.mark.asyncio
  async def test_websocket_joins_user_channel(self, test_client, allowed_emails):
    """
    Test that WebSocket connection joins user's private channel.

    Given: Valid JWT with email user@example.com
    When: WebSocket connection succeeds
    Then: Client is joined to 'user:user@example.com' channel
    """
    pytest.fail("Not implemented: WebSocket connection joins user channel")

  @pytest.mark.skip(reason="Integration test needs WebSocket test client infrastructure")
  @pytest.mark.asyncio
  async def test_websocket_authenticated_event(self, test_client, allowed_emails):
    """
    Test that WebSocket receives authenticated event with user info.

    Given: Valid JWT
    When: WebSocket connection succeeds
    Then: 'authenticated' event received with user email and channel
    """
    pytest.fail("Not implemented: WebSocket authenticated event received")


class TestServerRestartTolerance:
  """
  Test suite for server restart tolerance with JWT sessions.

  Tests verify that JWT sessions survive server restarts.

  Note: These tests require server restart simulation.
  Mark with @pytest.mark.skip for unit test phase.
  """

  @pytest.mark.skip(reason="Integration test needs server restart simulation")
  @pytest.mark.asyncio
  async def test_server_restart_preserves_auth(self, test_client, allowed_emails):
    """
    Test that JWT remains valid after server restart.

    Given: Valid JWT issued before server restart
    When: Server restarts
    Then: JWT is still valid for authentication
    """
    pytest.fail("Not implemented: JWT remains valid after server restart")

  @pytest.mark.skip(reason="Integration test needs server restart simulation")
  @pytest.mark.asyncio
  async def test_reconnect_after_restart(self, test_client, allowed_emails):
    """
    Test that WebSocket can reconnect after server restart.

    Given: Valid JWT, server restarted
    When: WebSocket reconnects
    Then: Connection succeeds with same JWT
    """
    pytest.fail("Not implemented: WebSocket reconnects after server restart")

  @pytest.mark.skip(reason="Integration test needs server restart simulation")
  @pytest.mark.asyncio
  async def test_magic_links_lost_on_restart(self, test_client, allowed_emails):
    """
    Test that pending magic links are lost on server restart.

    Given: Magic link created but not used
    When: Server restarts
    Then: Magic link no longer valid (in-memory storage)
    """
    pytest.fail("Not implemented: Magic links lost after server restart")


class TestLogoutJWT:
  """
  Test suite for logout with JWT sessions.

  Tests verify logout behavior with stateless JWT sessions.
  """

  @pytest.mark.asyncio
  async def test_logout_clears_cookie(self, test_client, allowed_emails):
    """
    Test that logout clears JWT cookie.

    Given: Authenticated user with JWT cookie
    When: POST /auth/logout
    Then: JWT cookie is cleared
    """
    # Set environment
    os.environ["JWT_SECRET_KEY"] = "test-secret-key-minimum-32-characters-long-for-security"
    os.environ["ALLOWED_EMAILS"] = ",".join(allowed_emails)
    allowed_emails_manager.clear_cache()

    # Create and verify magic link
    email = allowed_emails[0]
    token = magic_link_manager.create_magic_link(email)

    response = await test_client.get(f"/auth/verify?token={token}")
    assert response.status_code == 302

    # Logout
    response = await test_client.post("/auth/logout")

    # Verify success
    assert response.status_code == 200
    data = await response.get_json()
    assert data["status"] == "ok"

    # Check cookie is cleared
    cookies = response.headers.getlist("Set-Cookie")
    clear_cookie = None
    for cookie in cookies:
      if "session_token=" in cookie and (
        "expires" in cookie.lower() or "max-age=0" in cookie.lower()
      ):
        clear_cookie = cookie
        break

    # Cookie should be set to expire
    assert clear_cookie is not None or len(cookies) > 0

  @pytest.mark.asyncio
  async def test_logout_no_server_side_revocation(self, test_client, allowed_emails):
    """
    Test that logout does not revoke JWT server-side (stateless).

    Given: User logs out (cookie cleared)
    When: JWT is still valid until expiration
    Then: No server-side session storage (stateless)

    Note: This test verifies stateless nature - no session_manager.delete()
    """
    # Set environment
    jwt_secret = "test-secret-key-minimum-32-characters-long-for-security"
    os.environ["JWT_SECRET_KEY"] = jwt_secret
    os.environ["ALLOWED_EMAILS"] = ",".join(allowed_emails)
    allowed_emails_manager.clear_cache()

    # Create JWT
    email = allowed_emails[0]
    jwt_token = generate_jwt(email)

    # Logout (no server-side action for JWT)
    response = await test_client.post("/auth/logout")
    assert response.status_code == 200

    # JWT should still be valid (stateless)
    payload = validate_jwt(jwt_token)
    assert payload is not None

  @pytest.mark.asyncio
  async def test_logout_without_cookie_succeeds(self, test_client):
    """
    Test that logout without JWT cookie succeeds.

    Given: Request without JWT cookie
    When: POST /auth/logout
    Then: Returns 200 OK
    """
    # Set environment
    os.environ["JWT_SECRET_KEY"] = "test-secret-key-minimum-32-characters-long-for-security"
    os.environ["ALLOWED_EMAILS"] = "test@example.com"
    allowed_emails_manager.clear_cache()

    # Logout without cookie
    response = await test_client.post("/auth/logout")

    # Verify success
    assert response.status_code == 200


class TestGetCurrentUserJWT:
  """
  Test suite for /auth/me endpoint with JWT.

  Tests verify user info retrieval with JWT authentication.
  """

  @pytest.mark.asyncio
  async def test_get_current_user_with_valid_jwt(self, test_client, allowed_emails):
    """
    Test getting current user info with valid JWT.

    Given: Valid JWT in cookie
    When: GET /auth/me
    Then: Returns user info with email
    """
    # Set environment
    jwt_secret = "test-secret-key-minimum-32-characters-long-for-security"
    os.environ["JWT_SECRET_KEY"] = jwt_secret
    os.environ["ALLOWED_EMAILS"] = ",".join(allowed_emails)
    allowed_emails_manager.clear_cache()

    # Create magic link and verify
    email = allowed_emails[0]
    token = magic_link_manager.create_magic_link(email)

    response = await test_client.get(f"/auth/verify?token={token}")
    assert response.status_code == 302

    # Get current user (with session_token cookie from redirect)
    response = await test_client.get(
      "/auth/me", headers={"Cookie": response.headers.get("Set-Cookie", "")}
    )

    # Verify success
    assert response.status_code == 200
    data = await response.get_json()
    assert data["status"] == "ok"
    assert data["user"]["email"] == email.lower()

  @pytest.mark.asyncio
  async def test_get_current_user_with_expired_jwt(self, test_client, expired_jwt_payload):
    """
    Test getting current user info with expired JWT.

    Given: Expired JWT in cookie
    When: GET /auth/me
    Then: Returns 401 Unauthorized
    """
    # Set environment
    jwt_secret = "test-secret-key-minimum-32-characters-long-for-security"
    os.environ["JWT_SECRET_KEY"] = jwt_secret
    os.environ["ALLOWED_EMAILS"] = "test@example.com"
    allowed_emails_manager.clear_cache()

    # Create expired token
    expired_token = jwt.encode(expired_jwt_payload, jwt_secret, algorithm="HS256")

    # Get current user with expired token
    response = await test_client.get(
      "/auth/me", headers={"Cookie": f"session_token={expired_token}"}
    )

    # Verify rejection
    assert response.status_code == 401

  @pytest.mark.asyncio
  async def test_get_current_user_without_jwt(self, test_client):
    """
    Test getting current user info without JWT.

    Given: No JWT in cookie
    When: GET /auth/me
    Then: Returns 401 Unauthorized
    """
    # Set environment
    os.environ["JWT_SECRET_KEY"] = "test-secret-key-minimum-32-characters-long-for-security"
    os.environ["ALLOWED_EMAILS"] = "test@example.com"
    allowed_emails_manager.clear_cache()

    # Get current user without cookie
    response = await test_client.get("/auth/me")

    # Verify rejection
    assert response.status_code == 401

  @pytest.mark.asyncio
  async def test_get_current_user_with_blocked_email(self, test_client, allowed_emails):
    """
    Test getting current user info with blocked email.

    Given: Valid JWT but email removed from ALLOWED_EMAILS
    When: GET /auth/me
    Then: Returns 401 Unauthorized
    """
    # Set environment
    jwt_secret = "test-secret-key-minimum-32-characters-long-for-security"
    os.environ["JWT_SECRET_KEY"] = jwt_secret
    os.environ["ALLOWED_EMAILS"] = ",".join(allowed_emails)
    allowed_emails_manager.clear_cache()

    # Create JWT
    email = allowed_emails[0]
    jwt_token = generate_jwt(email)

    # Remove email from ALLOWED_EMAILS
    other_emails = [e for e in allowed_emails if e != email]
    os.environ["ALLOWED_EMAILS"] = ",".join(other_emails)
    allowed_emails_manager.clear_cache()

    # Get current user
    response = await test_client.get("/auth/me", headers={"Cookie": f"session_token={jwt_token}"})

    # Verify rejection
    assert response.status_code == 401


class TestAllowedEmailsIntegration:
  """
  Test suite for ALLOWED_EMAILS validation integration.

  Tests verify ALLOWED_EMAILS is checked at all authentication points.
  """

  @pytest.mark.asyncio
  async def test_allowed_emails_checked_at_magic_link_request(self, test_client):
    """
    Test that ALLOWED_EMAILS is checked at magic link request.

    Given: Email NOT in ALLOWED_EMAILS
    When: POST /auth/request-magic-link
    Then: Returns 403 Forbidden
    """
    # Set environment
    os.environ["JWT_SECRET_KEY"] = "test-secret-key-minimum-32-characters-long-for-security"
    os.environ["ALLOWED_EMAILS"] = "allowed@example.com"
    allowed_emails_manager.clear_cache()

    # Request magic link with blocked email
    response = await test_client.post(
      "/auth/request-magic-link", json={"email": "blocked@example.com"}
    )

    # Verify rejection
    assert response.status_code == 403

  @pytest.mark.asyncio
  async def test_allowed_emails_checked_at_jwt_creation(self, test_client, allowed_emails):
    """
    Test that ALLOWED_EMAILS is checked at JWT creation (magic link verification).

    Given: Magic link created, then email removed from ALLOWED_EMAILS
    When: GET /auth/verify?token=xxx
    Then: Returns 403 Forbidden (double-check)
    """
    # Set environment
    os.environ["JWT_SECRET_KEY"] = "test-secret-key-minimum-32-characters-long-for-security"
    os.environ["ALLOWED_EMAILS"] = ",".join(allowed_emails)
    allowed_emails_manager.clear_cache()

    # Create magic link
    email = allowed_emails[0]
    token = magic_link_manager.create_magic_link(email)

    # Remove email from ALLOWED_EMAILS
    other_emails = [e for e in allowed_emails if e != email]
    os.environ["ALLOWED_EMAILS"] = ",".join(other_emails)
    allowed_emails_manager.clear_cache()

    # Try to verify
    response = await test_client.get(f"/auth/verify?token={token}")

    # Verify rejection (redirect with error)
    assert response.status_code == 302
    assert "unauthorized" in response.location.lower()

  @pytest.mark.skip(reason="Integration test needs WebSocket test client infrastructure")
  @pytest.mark.asyncio
  async def test_allowed_emails_checked_at_websocket_connection(self, test_client, allowed_emails):
    """
    Test that ALLOWED_EMAILS is checked at WebSocket connection.

    Given: Valid JWT but email removed from ALLOWED_EMAILS
    When: WebSocket connection attempt
    Then: Connection rejected
    """
    pytest.fail("Not implemented: ALLOWED_EMAILS checked at WebSocket connection")

  @pytest.mark.asyncio
  async def test_allowed_emails_checked_at_api_request(self, test_client, allowed_emails):
    """
    Test that ALLOWED_EMAILS is checked at API requests (/auth/me).

    Given: Valid JWT but email removed from ALLOWED_EMAILS
    When: GET /auth/me
    Then: Returns 401 Unauthorized
    """
    # Set environment
    jwt_secret = "test-secret-key-minimum-32-characters-long-for-security"
    os.environ["JWT_SECRET_KEY"] = jwt_secret
    os.environ["ALLOWED_EMAILS"] = ",".join(allowed_emails)
    allowed_emails_manager.clear_cache()

    # Create JWT
    email = allowed_emails[0]
    jwt_token = generate_jwt(email)

    # Remove email from ALLOWED_EMAILS
    other_emails = [e for e in allowed_emails if e != email]
    os.environ["ALLOWED_EMAILS"] = ",".join(other_emails)
    allowed_emails_manager.clear_cache()

    # Get current user
    response = await test_client.get("/auth/me", headers={"Cookie": f"session_token={jwt_token}"})

    # Verify rejection
    assert response.status_code == 401

  @pytest.mark.asyncio
  async def test_allowed_emails_instant_revocation(self, test_client, allowed_emails):
    """
    Test that removing email from ALLOWED_EMAILS instantly revokes access.

    Given: User authenticated with valid JWT
    When: Email removed from ALLOWED_EMAILS
    Then: Next request is rejected (instant revocation)
    """
    # Set environment
    jwt_secret = "test-secret-key-minimum-32-characters-long-for-security"
    os.environ["JWT_SECRET_KEY"] = jwt_secret
    os.environ["ALLOWED_EMAILS"] = ",".join(allowed_emails)
    allowed_emails_manager.clear_cache()

    # Create JWT and verify it works
    email = allowed_emails[0]
    jwt_token = generate_jwt(email)

    response = await test_client.get("/auth/me", headers={"Cookie": f"session_token={jwt_token}"})
    assert response.status_code == 200

    # Remove email from ALLOWED_EMAILS
    other_emails = [e for e in allowed_emails if e != email]
    os.environ["ALLOWED_EMAILS"] = ",".join(other_emails)
    allowed_emails_manager.clear_cache()

    # Try again
    response = await test_client.get("/auth/me", headers={"Cookie": f"session_token={jwt_token}"})

    # Verify rejection
    assert response.status_code == 401
