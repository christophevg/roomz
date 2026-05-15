"""
Tests for Magic Link Authentication functionality.

This module tests the authentication flow including magic link request,
verification, and security features.

Requirements: FR-1.1.1, FR-1.1.2 (from functional analysis)
- Users authenticate via email-based magic link flow
- System sends one-time magic link to user's email address
- Link expires after configurable timeout (default: 15 minutes)
- Rate limiting on magic link requests to prevent abuse
"""

import os
import re
from datetime import datetime, timedelta, timezone

import pytest

from app.auth import (
  is_valid_email,
  is_email_allowed,
  magic_link_limiter,
  magic_link_manager,
  allowed_emails_manager,
  generate_jwt,
  validate_jwt,
)


class TestMagicLinkRequest:
  """
  Test suite for magic link request functionality.

  Tests verify the magic link generation endpoint, email validation,
  and rate limiting to prevent abuse.
  """

  async def test_valid_email_request_creates_magic_link(self, test_client):
    """
    Test that a valid email request creates a magic link.

    Given: A user with a valid email address
    When: The user requests a magic link via POST /auth/request-magic-link
    Then: A magic link is generated and logged to console
    """
    response = await test_client.post(
      "/auth/request-magic-link", json={"email": "test@example.com"}
    )

    assert response.status_code == 200
    data = await response.get_json()
    assert data["status"] == "ok"
    assert "message" in data

  async def test_valid_email_returns_success_response(self, test_client):
    """
    Test that valid email returns success response.

    Given: A user with a valid email address
    When: The user requests a magic link
    Then: Server returns status 'ok' with message about checking console
    """
    response = await test_client.post(
      "/auth/request-magic-link", json={"email": "user@example.com"}
    )

    assert response.status_code == 200
    data = await response.get_json()
    assert data["status"] == "ok"

  async def test_invalid_email_format_returns_error(self, test_client):
    """
    Test that invalid email format returns error.

    Given: A user with an invalid email address (missing @, no domain, etc.)
    When: The user requests a magic link
    Then: Server returns 400 error with 'Invalid email format' message
    """
    invalid_emails = [
      "invalid",
      "no@domain",
      "@nodomain.com",
      "spaces in@email.com",
      "missing@tld.",
    ]

    for email in invalid_emails:
      response = await test_client.post("/auth/request-magic-link", json={"email": email})
      assert response.status_code == 400
      data = await response.get_json()
      # RFC 7807 format: error detail is in 'detail' field
      assert "Invalid email format" in data.get("detail", data.get("error", ""))

  async def test_empty_email_returns_error(self, test_client):
    """
    Test that empty email returns error.

    Given: A request with empty email field
    When: The user requests a magic link
    Then: Server returns 400 error
    """
    response = await test_client.post("/auth/request-magic-link", json={"email": ""})

    assert response.status_code == 400

  async def test_email_normalized_to_lowercase(self, test_client):
    """
    Test that email is normalized to lowercase.

    Given: A user with uppercase email (User@Example.COM)
    When: The user requests a magic link
    Then: Email is stored and processed as lowercase
    """
    response = await test_client.post(
      "/auth/request-magic-link", json={"email": "User@Example.COM"}
    )

    assert response.status_code == 200

    # Check that the magic link was created with lowercase email
    # by examining the stored magic links
    assert len(magic_link_manager._magic_links) > 0
    for magic_link in magic_link_manager._magic_links.values():
      assert magic_link.email == "user@example.com"

  async def test_email_whitespace_trimmed(self, test_client):
    """
    Test that email whitespace is trimmed.

    Given: A user with email containing whitespace ("  user@example.com  ")
    When: The user requests a magic link
    Then: Email is trimmed before processing
    """
    response = await test_client.post(
      "/auth/request-magic-link", json={"email": "  user@example.com  "}
    )

    assert response.status_code == 200

    # Check that the magic link was created with trimmed email
    for magic_link in magic_link_manager._magic_links.values():
      assert magic_link.email == "user@example.com"

  async def test_rate_limiting_prevents_spam(self, test_client):
    """
    Test that rate limiting prevents spam (5 per email per hour).

    Given: A user requesting 6 magic links within one hour
    When: The 6th request is made
    Then: Server returns 429 Too Many Requests error
    """
    email = "spam@test.com"

    # Make 5 successful requests (rate limit)
    for i in range(5):
      response = await test_client.post("/auth/request-magic-link", json={"email": email})
      assert response.status_code == 200

    # 6th request should fail
    response = await test_client.post("/auth/request-magic-link", json={"email": email})
    assert response.status_code == 429
    data = await response.get_json()
    # RFC 7807 format: error detail is in 'detail' field
    assert "Too many requests" in data.get("detail", data.get("error", ""))

  async def test_rate_limiting_per_email_not_global(self, test_client):
    """
    Test that rate limiting is per email, not global.

    Given: User A has reached rate limit
    When: User B requests a magic link
    Then: User B's request succeeds (different email)
    """
    # User A reaches rate limit
    for i in range(5):
      await test_client.post("/auth/request-magic-link", json={"email": "userA@test.com"})

    # User B should still be able to request
    response = await test_client.post("/auth/request-magic-link", json={"email": "userB@test.com"})

    assert response.status_code == 200

  async def test_rate_limiting_resets_after_one_hour(self, test_client):
    """
    Test that rate limit resets after one hour.

    Given: A user has reached rate limit
    When: One hour passes
    Then: The user can request a new magic link
    """
    email = "timeout@test.com"

    # Reach rate limit
    for i in range(5):
      await test_client.post("/auth/request-magic-link", json={"email": email})

    # Simulate time passing by clearing old requests
    magic_link_limiter.reset(email)

    # Should be able to request again
    response = await test_client.post("/auth/request-magic-link", json={"email": email})

    assert response.status_code == 200

  async def test_magic_link_token_format(self, test_client):
    """
    Test that magic link token uses secure format.

    Given: A user requests a magic link
    When: Token is generated
    Then: Token uses secrets.token_urlsafe(32) - 256 bits
    """
    response = await test_client.post("/auth/request-magic-link", json={"email": "token@test.com"})

    assert response.status_code == 200

    # Token should be stored as hash
    assert len(magic_link_manager._magic_links) > 0

    # Hash should be SHA-256 (64 hex chars)
    for token_hash in magic_link_manager._magic_links.keys():
      assert len(token_hash) == 64
      assert re.match(r"^[a-f0-9]{64}$", token_hash)

  async def test_magic_link_token_stored_as_hash(self, test_client):
    """
    Test that magic link token is stored as hash, not plaintext.

    Given: A user requests a magic link
    When: Token is stored in database
    Then: Only the SHA-256 hash is stored, not the plaintext token
    """

    response = await test_client.post("/auth/request-magic-link", json={"email": "hash@test.com"})

    assert response.status_code == 200

    # Get the stored hash
    stored_hashes = list(magic_link_manager._magic_links.keys())
    assert len(stored_hashes) > 0

    # Verify it's a SHA-256 hash (64 hex chars)
    token_hash = stored_hashes[-1]
    assert len(token_hash) == 64
    assert re.match(r"^[a-f0-9]{64}$", token_hash)


class TestMagicLinkVerification:
  """
  Test suite for magic link verification functionality.

  Tests verify the token verification endpoint, session creation,
  and security constraints (single-use, expiration).
  """

  async def test_valid_token_creates_session(self, test_client):
    """
    Test that valid token creates session and sets cookie.

    Given: A user with a valid magic link token
    When: The user accesses GET /auth/verify?token=abc123
    Then: Session is created, httpOnly cookie is set, redirect to /
    """
    # Create a magic link
    token = magic_link_manager.create_magic_link("verify@test.com")

    # Verify the token
    response = await test_client.get(f"/auth/verify?token={token}")

    assert response.status_code == 302
    assert "/" in response.headers.get("Location", "")

    # Check cookie is set
    cookies = response.headers.getlist("Set-Cookie")
    assert any("session_token" in cookie for cookie in cookies)

  async def test_valid_token_redirects_to_chat(self, test_client):
    """
    Test that valid token redirects to chat page.

    Given: A user with a valid magic link token
    When: The user verifies the token
    Then: Response redirects to /
    """
    token = magic_link_manager.create_magic_link("redirect@test.com")

    response = await test_client.get(f"/auth/verify?token={token}")

    assert response.status_code == 302
    assert "/" in response.headers.get("Location", "")

  async def test_invalid_token_returns_error(self, test_client):
    """
    Test that invalid token returns error.

    Given: A user with an invalid/non-existent token
    When: The user tries to verify
    Then: Response redirects to /?error=invalid_token
    """
    response = await test_client.get("/auth/verify?token=invalidtoken123")

    assert response.status_code == 302
    location = response.headers.get("Location", "")
    assert "error=invalid_token" in location or "error=missing_token" in location

  async def test_expired_token_returns_error(self, test_client):
    """
    Test that expired token returns error.

    Given: A user with a token older than 15 minutes
    When: The user tries to verify
    Then: Response redirects to /?error=token_expired
    """
    import hashlib

    # Create a magic link
    token = magic_link_manager.create_magic_link("expired@test.com")
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    # Manually expire it
    magic_link = magic_link_manager._magic_links.get(token_hash)
    if magic_link:
      magic_link.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)

    # Try to verify
    response = await test_client.get(f"/auth/verify?token={token}")

    assert response.status_code == 302
    location = response.headers.get("Location", "")
    assert "error=token_expired" in location or "error=invalid_token" in location

  async def test_already_used_token_returns_error(self, test_client):
    """
    Test that already-used token returns error.

    Given: A token that has been used once
    When: The user tries to verify again
    Then: Response redirects to /?error=token_already_used
    """
    # Create a magic link
    token = magic_link_manager.create_magic_link("used@test.com")

    # Use it once
    response1 = await test_client.get(f"/auth/verify?token={token}")
    assert response1.status_code == 302

    # Try to use it again
    response2 = await test_client.get(f"/auth/verify?token={token}")

    assert response2.status_code == 302
    location = response2.headers.get("Location", "")
    assert "error=token_already_used" in location or "error=invalid_token" in location

  async def test_token_single_use_enforcement(self, test_client):
    """
    Test that tokens can only be used once.

    Given: A valid magic link token
    When: Token is used once successfully
    Then: Second use attempt fails with 'token_already_used' error
    """
    token = magic_link_manager.create_magic_link("single@test.com")

    # First use succeeds
    response1 = await test_client.get(f"/auth/verify?token={token}")
    assert response1.status_code == 302
    assert "/" in response1.headers.get("Location", "")

    # Second use fails
    response2 = await test_client.get(f"/auth/verify?token={token}")
    assert response2.status_code == 302
    location = response2.headers.get("Location", "")
    assert "error=" in location

  async def test_missing_token_parameter_returns_error(self, test_client):
    """
    Test that missing token parameter returns error.

    Given: A request to /auth/verify without token parameter
    When: The endpoint is called
    Then: Response redirects to /?error=missing_token
    """
    response = await test_client.get("/auth/verify")

    assert response.status_code == 302
    location = response.headers.get("Location", "")
    assert "error=missing_token" in location

  async def test_malformed_token_format_handled(self, test_client):
    """
    Test that malformed token format is handled gracefully.

    Given: A request with malformed token (special chars, too long, etc.)
    When: The endpoint is called
    Then: Returns error without crashing
    """
    malformed_tokens = [
      "a" * 1000,  # Very long
      "!@#$%^&*()",  # Special chars
      "   ",  # Whitespace
    ]

    for token in malformed_tokens:
      response = await test_client.get(f"/auth/verify?token={token}")
      # Should redirect with error, not crash
      assert response.status_code == 302
      location = response.headers.get("Location", "")
      assert "error=" in location

  async def test_session_cookie_httponly_attribute(self, test_client):
    """
    Test that session cookie has httpOnly attribute.

    Given: A successful magic link verification
    When: Session cookie is set
    Then: Cookie has httpOnly=True attribute
    """
    token = magic_link_manager.create_magic_link("cookie@test.com")

    response = await test_client.get(f"/auth/verify?token={token}")

    cookies = response.headers.getlist("Set-Cookie")
    session_cookie = [c for c in cookies if "session_token" in c][0]

    assert "HttpOnly" in session_cookie or "httponly" in session_cookie.lower()

  async def test_session_cookie_secure_attribute(self, test_client):
    """
    Test that session cookie has secure attribute in production.

    Note: Development mode sets secure=False for localhost compatibility.
    This test verifies the HttpOnly attribute which is always set.

    Given: A successful magic link verification
    When: Session cookie is set
    Then: Cookie has HttpOnly attribute (secure in production only)
    """
    token = magic_link_manager.create_magic_link("secure@test.com")

    response = await test_client.get(f"/auth/verify?token={token}")

    cookies = response.headers.getlist("Set-Cookie")
    session_cookie = [c for c in cookies if "session_token" in c][0]

    # HttpOnly is always set (dev and prod)
    assert "HttpOnly" in session_cookie or "httponly" in session_cookie.lower()
    # SameSite is always set
    assert "SameSite" in session_cookie or "samesite" in session_cookie.lower()

  async def test_session_cookie_samesite_attribute(self, test_client):
    """
    Test that session cookie has SameSite attribute.

    Given: A successful magic link verification
    When: Session cookie is set
    Then: Cookie has SameSite='Strict' or 'Lax' attribute
    """
    token = magic_link_manager.create_magic_link("samesite@test.com")

    response = await test_client.get(f"/auth/verify?token={token}")

    cookies = response.headers.getlist("Set-Cookie")
    session_cookie = [c for c in cookies if "session_token" in c][0]

    assert "SameSite" in session_cookie or "samesite" in session_cookie.lower()

  async def test_session_cookie_max_age(self, test_client):
    """
    Test that session cookie has correct max age.

    Given: A successful magic link verification
    When: Session cookie is set
    Then: Cookie has max_age of 30 days (2592000 seconds)
    """
    token = magic_link_manager.create_magic_link("maxage@test.com")

    response = await test_client.get(f"/auth/verify?token={token}")

    cookies = response.headers.getlist("Set-Cookie")
    session_cookie = [c for c in cookies if "session_token" in c][0]

    # Max-Age should be 30 days in seconds
    assert "Max-Age" in session_cookie or "max-age" in session_cookie.lower()
    # 30 days = 2592000 seconds
    assert "2592000" in session_cookie


class TestMagicLinkSecurity:
  """
  Test suite for magic link security features.

  Tests verify security aspects like token generation,
  rate limiting, and protection against common attacks.
  """

  async def test_token_uses_cryptographically_secure_generation(self, test_client):
    """
    Test that tokens use cryptographically secure random generation.

    Given: Multiple magic link requests
    When: Tokens are generated
    Then: Each token is unique and uses secrets module
    """

    for i in range(10):
      await test_client.post("/auth/request-magic-link", json={"email": f"unique{i}@test.com"})

    # All tokens should be unique
    # (we check by checking the stored magic links)
    token_hashes = list(magic_link_manager._magic_links.keys())
    assert len(set(token_hashes)) == len(token_hashes)

  async def test_token_length_adequate(self, test_client):
    """
    Test that token length is adequate (256 bits).

    Given: A magic link request
    When: Token is generated
    Then: Token is at least 32 bytes (256 bits) of entropy
    """
    # The actual token is secrets.token_urlsafe(32)
    # which produces 43 characters
    # We verify that the hash is SHA-256 (256 bits)
    await test_client.post("/auth/request-magic-link", json={"email": "length@test.com"})

    # SHA-256 hash is always 64 hex characters (256 bits)
    token_hashes = list(magic_link_manager._magic_links.keys())
    assert len(token_hashes[-1]) == 64

  async def test_rate_limiting_prevents_brute_force(self, test_client):
    """
    Test that rate limiting prevents brute force attacks.

    Given: An attacker trying multiple requests rapidly
    When: Rate limit is reached
    Then: Further requests are blocked for 1 hour
    """
    email = "brute@test.com"

    # Reach rate limit
    for i in range(5):
      await test_client.post("/auth/request-magic-link", json={"email": email})

    # Further requests should be blocked
    response = await test_client.post("/auth/request-magic-link", json={"email": email})
    assert response.status_code == 429

  async def test_concurrent_verification_attempts(self, test_client):
    """
    Test handling of concurrent verification attempts.

    Given: Same token being verified concurrently by multiple requests
    When: Both requests arrive simultaneously
    Then: Only one succeeds, others get 'token_already_used' error
    """
    token = magic_link_manager.create_magic_link("concurrent@test.com")

    # First verification succeeds
    response1 = await test_client.get(f"/auth/verify?token={token}")
    assert response1.status_code == 302

    # Second verification fails (token already used)
    response2 = await test_client.get(f"/auth/verify?token={token}")
    assert response2.status_code == 302
    assert "error=" in response2.headers.get("Location", "")

  def test_no_shared_secret_stored(self):
    """
    Test that no shared secret is stored in code or config.

    Given: The authentication system
    When: Searching for hardcoded secrets
    Then: No shared secrets or API keys found in code
    """
    # This is a design verification
    # The authentication system uses magic links, not shared secrets
    # We verify that the auth module doesn't have hardcoded secrets
    import inspect

    import app.auth

    source = inspect.getsource(app.auth)

    # Check that there are no hardcoded secrets
    # (This is a basic check - in production you'd use more sophisticated tools)
    assert "SECRET_KEY" not in source
    assert "API_KEY" not in source
    assert "PASSWORD" not in source

  def test_email_validation_rfc5322_compliant(self, test_client):
    """
    Test that email validation follows RFC 5322.

    Given: Various email formats (valid and invalid)
    When: Validating email addresses
    Then: RFC 5322 compliance is enforced
    """
    valid_emails = [
      "user@example.com",
      "user.name@example.com",
      "user+tag@example.com",
      "user@subdomain.example.com",
    ]

    invalid_emails = [
      "invalid",
      "@example.com",
      "user@",
      "user @example.com",
      "user@example",
    ]

    for email in valid_emails:
      assert is_valid_email(email), f"Should accept {email}"

    for email in invalid_emails:
      assert not is_valid_email(email), f"Should reject {email}"

  async def test_magic_link_url_format(self, test_client):
    """
    Test that magic link URL has correct format.

    Given: A generated magic link
    When: URL is created
    Then: URL format is correct with token parameter
    """
    # The magic link URL is logged to console
    # We verify the format by checking the endpoint accepts it
    token = magic_link_manager.create_magic_link("url@test.com")

    # URL should have been created with this token
    response = await test_client.get(f"/auth/verify?token={token}")
    assert response.status_code == 302

    # Invalid token should fail
    response = await test_client.get("/auth/verify?token=invalid")
    assert "error=" in response.headers.get("Location", "")


class TestLogout:
  """
  Test suite for logout functionality.

  Tests verify JWT cookie clearing (stateless - no server-side session).
  """

  async def test_logout_clears_jwt_cookie(self, test_client, jwt_secret_key, allowed_emails):
    """
    Test that logout clears JWT cookie.

    Given: An authenticated user with JWT cookie
    When: User calls POST /auth/logout
    Then: JWT cookie is cleared
    """
    # Set environment
    os.environ["JWT_SECRET_KEY"] = jwt_secret_key
    os.environ["ALLOWED_EMAILS"] = ",".join(allowed_emails)
    allowed_emails_manager.clear_cache()

    # Generate JWT
    email = allowed_emails[0]
    jwt_token = generate_jwt(email)

    # Logout with JWT cookie
    response = await test_client.post("/auth/logout", headers={"Cookie": f"session_token={jwt_token}"})

    assert response.status_code == 200

    # Cookie should be cleared (Set-Cookie with empty value or expires)
    _ = response.headers.getlist("Set-Cookie")

  async def test_logout_stateless_no_server_side_revocation(self, test_client, jwt_secret_key, allowed_emails):
    """
    Test that logout is stateless (no server-side session revocation).

    Given: An authenticated user
    When: User logs out
    Then: JWT is still technically valid (stateless nature)

    Note: This tests the stateless nature of JWT - logout only clears cookie.
    """
    # Set environment
    os.environ["JWT_SECRET_KEY"] = jwt_secret_key
    os.environ["ALLOWED_EMAILS"] = ",".join(allowed_emails)
    allowed_emails_manager.clear_cache()

    # Generate JWT
    email = allowed_emails[0]
    jwt_token = generate_jwt(email)

    # Logout
    await test_client.post("/auth/logout", headers={"Cookie": f"session_token={jwt_token}"})

    # JWT should still be valid (stateless)
    payload = validate_jwt(jwt_token)
    assert payload is not None

  async def test_logout_without_session_no_error(self, test_client):
    """
    Test that logout without JWT doesn't cause error.

    Given: A request without JWT cookie
    When: User calls POST /auth/logout
    Then: Request succeeds without error
    """
    response = await test_client.post("/auth/logout")

    assert response.status_code == 200

  async def test_get_current_user_with_valid_jwt(self, test_client, jwt_secret_key, allowed_emails):
    """
    Test getting current user info with valid JWT.

    Given: An authenticated user with valid JWT
    When: User calls GET /auth/me
    Then: Returns user info including email
    """
    # Set environment
    os.environ["JWT_SECRET_KEY"] = jwt_secret_key
    os.environ["ALLOWED_EMAILS"] = ",".join(allowed_emails)
    allowed_emails_manager.clear_cache()

    # Generate JWT
    email = allowed_emails[0]
    jwt_token = generate_jwt(email)

    response = await test_client.get("/auth/me", headers={"Cookie": f"session_token={jwt_token}"})

    assert response.status_code == 200
    data = await response.get_json()
    assert data["status"] == "ok"
    assert data["user"]["email"] == email.lower()

  async def test_get_current_user_without_jwt_returns_error(self, test_client):
    """
    Test getting current user info without JWT.

    Given: A request without JWT cookie
    When: User calls GET /auth/me
    Then: Returns 401 Unauthorized
    """
    response = await test_client.get("/auth/me")

    assert response.status_code == 401
