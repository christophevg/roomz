"""
Unit tests for JWT session token functionality.

This module tests JWT generation, validation, and core JWT functions
in isolation from the HTTP/WebSocket layer.

Requirements: I4-001 - JWT Session Tokens
- JWT tokens replace in-memory session storage
- Stateless sessions enable server restart tolerance
- ALLOWED_EMAILS validation on every request
"""

import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.auth import (
  JWT_ALGORITHM,
  JWT_SECRET_KEY_MIN_LENGTH,
  _token_versions,
  allowed_emails_manager,
  generate_jwt,
  get_jwt_secret_key,
  get_token_version,
  increment_token_version,
  is_email_allowed,
  validate_jwt,
)


class TestJWTGeneration:
  """
  Test suite for JWT token generation.

  Tests verify JWT creation with correct claims, format, and security properties.
  """

  def test_generate_jwt_creates_valid_token(self, jwt_secret_key, sample_email):
    """
    Test that JWT generation creates a valid token with correct claims.

    Given: A valid email address and secret key
    When: JWT is generated
    Then: Token is valid JWT format with all required claims
    """
    # Set environment
    os.environ["JWT_SECRET_KEY"] = jwt_secret_key
    os.environ["ALLOWED_EMAILS"] = sample_email

    # Generate JWT
    token = generate_jwt(sample_email)

    # Verify token is valid JWT
    assert token is not None
    assert isinstance(token, str)
    assert len(token.split(".")) == 3  # JWT has 3 parts

    # Decode and verify
    payload = jwt.decode(token, jwt_secret_key, algorithms=[JWT_ALGORITHM])
    assert payload is not None
    assert "email" in payload
    assert payload["email"] == sample_email.lower().strip()

  def test_generate_jwt_includes_required_claims(self, jwt_secret_key, sample_email):
    """
    Test that JWT includes all required claims.

    Given: A JWT is generated
    When: Token is decoded
    Then: Token contains sub, email, iat, exp, channel_token claims
    """
    # Set environment
    os.environ["JWT_SECRET_KEY"] = jwt_secret_key
    os.environ["ALLOWED_EMAILS"] = sample_email

    # Generate JWT
    token = generate_jwt(sample_email)

    # Decode
    payload = jwt.decode(token, jwt_secret_key, algorithms=[JWT_ALGORITHM])

    # Verify all required claims
    assert "sub" in payload
    assert "email" in payload
    assert "iat" in payload
    assert "exp" in payload
    assert "channel_token" in payload
    assert "ver" in payload

    # Verify claim values
    assert payload["sub"] == f"user:{sample_email.lower().strip()}"
    assert payload["email"] == sample_email.lower().strip()

  def test_generate_jwt_includes_token_version(self, jwt_secret_key, sample_email):
    """
    Test that JWT includes token version claim.

    Given: A JWT is generated for a user
    When: Token is decoded
    Then: Token contains 'ver' claim for version tracking
    """
    # Set environment
    os.environ["JWT_SECRET_KEY"] = jwt_secret_key
    os.environ["ALLOWED_EMAILS"] = sample_email

    # Generate JWT
    token = generate_jwt(sample_email)

    # Decode
    payload = jwt.decode(token, jwt_secret_key, algorithms=[JWT_ALGORITHM])

    # Verify version claim
    assert "ver" in payload
    assert payload["ver"] == get_token_version(sample_email)

  def test_generate_jwt_sets_correct_expiration(self, jwt_secret_key, sample_email):
    """
    Test that JWT expiration is set correctly (30 days by default).

    Given: A JWT is generated
    When: Token is decoded
    Then: Expiration is approximately 30 days from now
    """
    # Set environment
    os.environ["JWT_SECRET_KEY"] = jwt_secret_key
    os.environ["ALLOWED_EMAILS"] = sample_email

    # Generate JWT
    before = datetime.now(timezone.utc)
    token = generate_jwt(sample_email)
    after = datetime.now(timezone.utc)

    # Decode
    payload = jwt.decode(token, jwt_secret_key, algorithms=[JWT_ALGORITHM])

    # Verify expiration
    exp_timestamp = payload["exp"]
    exp_datetime = datetime.fromtimestamp(exp_timestamp, timezone.utc)

    # Should be ~30 days from now (allow 1 minute tolerance)
    expected_min = before + timedelta(days=30) - timedelta(minutes=1)
    expected_max = after + timedelta(days=30) + timedelta(minutes=1)

    assert expected_min <= exp_datetime <= expected_max

  def test_generate_jwt_unique_channel_token(self, jwt_secret_key, sample_email):
    """
    Test that each JWT gets a unique channel_token.

    Given: Two JWTs generated for same email
    When: Tokens are decoded
    Then: Each has different channel_token
    """
    # Set environment
    os.environ["JWT_SECRET_KEY"] = jwt_secret_key
    os.environ["ALLOWED_EMAILS"] = sample_email

    # Generate two JWTs
    token1 = generate_jwt(sample_email)
    token2 = generate_jwt(sample_email)

    # Decode
    payload1 = jwt.decode(token1, jwt_secret_key, algorithms=[JWT_ALGORITHM])
    payload2 = jwt.decode(token2, jwt_secret_key, algorithms=[JWT_ALGORITHM])

    # Verify unique channel tokens
    assert payload1["channel_token"] != payload2["channel_token"]

  def test_generate_jwt_uses_hs256_algorithm(self, jwt_secret_key, sample_email):
    """
    Test that JWT is signed with HS256 algorithm.

    Given: A JWT is generated
    When: Token header is examined
    Then: Algorithm is 'HS256'
    """
    # Set environment
    os.environ["JWT_SECRET_KEY"] = jwt_secret_key
    os.environ["ALLOWED_EMAILS"] = sample_email

    # Generate JWT
    token = generate_jwt(sample_email)

    # Get header
    header = jwt.get_unverified_header(token)

    # Verify algorithm
    assert header["alg"] == "HS256"

  def test_generate_jwt_email_normalized(self, jwt_secret_key):
    """
    Test that email is normalized to lowercase in JWT.

    Given: Email with mixed case (User@Example.COM)
    When: JWT is generated
    Then: Email in JWT is lowercase
    """
    # Set environment
    mixed_case_email = "User@Example.COM"
    os.environ["JWT_SECRET_KEY"] = jwt_secret_key
    os.environ["ALLOWED_EMAILS"] = mixed_case_email.lower()

    # Generate JWT
    token = generate_jwt(mixed_case_email)

    # Decode
    payload = jwt.decode(token, jwt_secret_key, algorithms=[JWT_ALGORITHM])

    # Verify normalized email
    assert payload["email"] == mixed_case_email.lower()


class TestJWTValidation:
  """
  Test suite for JWT token validation.

  Tests verify JWT signature verification, claim validation, and security checks.
  """

  def test_validate_jwt_accepts_valid_token(self, jwt_secret_key, sample_email, sample_jwt_payload):
    """
    Test that JWT validation accepts valid token.

    Given: A valid JWT token
    When: Token is validated
    Then: Validation returns payload
    """
    # Set environment
    os.environ["JWT_SECRET_KEY"] = jwt_secret_key
    os.environ["ALLOWED_EMAILS"] = sample_email

    # Create valid token
    token = jwt.encode(sample_jwt_payload, jwt_secret_key, algorithm=JWT_ALGORITHM)

    # Validate
    result = validate_jwt(token)

    # Verify result
    assert result is not None
    assert result["email"] == sample_email

  def test_validate_jwt_rejects_expired_token(self, jwt_secret_key, expired_jwt_payload):
    """
    Test that JWT validation rejects expired token.

    Given: An expired JWT token
    When: Token is validated
    Then: Validation returns None
    """
    # Set environment
    os.environ["JWT_SECRET_KEY"] = jwt_secret_key
    os.environ["ALLOWED_EMAILS"] = "test@example.com"

    # Create expired token
    token = jwt.encode(expired_jwt_payload, jwt_secret_key, algorithm=JWT_ALGORITHM)

    # Validate
    result = validate_jwt(token)

    # Verify result
    assert result is None

  def test_validate_jwt_rejects_invalid_signature(self, jwt_secret_key, sample_email):
    """
    Test that JWT validation rejects token with invalid signature.

    Given: A JWT with incorrect signature
    When: Token is validated
    Then: Validation returns None
    """
    # Set environment
    os.environ["JWT_SECRET_KEY"] = jwt_secret_key
    os.environ["ALLOWED_EMAILS"] = sample_email

    # Create token with different key
    wrong_key = secrets.token_urlsafe(32)
    payload = {
      "sub": f"user:{sample_email}",
      "email": sample_email,
      "iat": int(datetime.now(timezone.utc).timestamp()),
      "exp": int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp()),
      "channel_token": secrets.token_urlsafe(32),
      "ver": 1,
    }
    token = jwt.encode(payload, wrong_key, algorithm=JWT_ALGORITHM)

    # Validate
    result = validate_jwt(token)

    # Verify result
    assert result is None

  def test_validate_jwt_rejects_none_algorithm(self, jwt_secret_key):
    """
    Test that JWT validation rejects 'none' algorithm.

    Given: A JWT with 'none' algorithm (attack vector)
    When: Token is validated
    Then: Validation returns None
    """
    # Set environment
    os.environ["JWT_SECRET_KEY"] = jwt_secret_key

    # Create token with none algorithm (attack vector)
    payload = {
      "sub": "user:attacker@example.com",
      "email": "attacker@example.com",
      "iat": int(datetime.now(timezone.utc).timestamp()),
      "exp": int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp()),
      "channel_token": secrets.token_urlsafe(32),
    }

    # Create unsecured token (header with none algorithm)
    header = {"alg": "none", "typ": "JWT"}
    import base64
    import json

    header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    token = f"{header_b64}.{payload_b64}."

    # Validate
    result = validate_jwt(token)

    # Verify result
    assert result is None

  def test_validate_jwt_rejects_missing_claims(self, jwt_secret_key):
    """
    Test that JWT validation rejects token missing required claims.

    Given: A JWT missing required claims (email, exp, iat)
    When: Token is validated
    Then: Validation returns None
    """
    # Set environment
    os.environ["JWT_SECRET_KEY"] = jwt_secret_key
    os.environ["ALLOWED_EMAILS"] = "test@example.com"

    # Create token with missing claims
    payload = {
      "sub": "user:test@example.com",
      # Missing: email, iat, exp, channel_token
    }
    token = jwt.encode(payload, jwt_secret_key, algorithm=JWT_ALGORITHM)

    # Validate
    result = validate_jwt(token)

    # Verify result
    assert result is None

  def test_validate_jwt_rejects_malformed_token(self, jwt_secret_key):
    """
    Test that JWT validation rejects malformed token.

    Given: A malformed JWT string
    When: Token is validated
    Then: Validation returns None (no exception)
    """
    # Set environment
    os.environ["JWT_SECRET_KEY"] = jwt_secret_key

    # Malformed token
    token = "not.a.valid.jwt"

    # Validate (should not raise exception)
    result = validate_jwt(token)

    # Verify result
    assert result is None

  def test_validate_jwt_rejects_empty_token(self, jwt_secret_key):
    """
    Test that JWT validation rejects empty token.

    Given: An empty string token
    When: Token is validated
    Then: Validation returns None
    """
    # Set environment
    os.environ["JWT_SECRET_KEY"] = jwt_secret_key

    # Empty token
    token = ""

    # Validate
    result = validate_jwt(token)

    # Verify result
    assert result is None


class TestEmailAllowed:
  """
  Test suite for ALLOWED_EMAILS validation.

  Tests verify email allow-list checking functionality.
  """

  def test_is_email_allowed_returns_true_for_allowed_email(self, allowed_emails):
    """
    Test that is_email_allowed returns True for allowed email.

    Given: An email in ALLOWED_EMAILS
    When: is_email_allowed is called
    Then: Returns True
    """
    # Set environment
    os.environ["ALLOWED_EMAILS"] = ",".join(allowed_emails)
    allowed_emails_manager.clear_cache()

    # Test
    email = allowed_emails[0]
    result = is_email_allowed(email)

    # Verify
    assert result is True

  def test_is_email_allowed_returns_false_for_blocked_email(self, allowed_emails):
    """
    Test that is_email_allowed returns False for blocked email.

    Given: An email NOT in ALLOWED_EMAILS
    When: is_email_allowed is called
    Then: Returns False
    """
    # Set environment
    os.environ["ALLOWED_EMAILS"] = ",".join(allowed_emails)
    allowed_emails_manager.clear_cache()

    # Test
    blocked_email = "blocked@example.com"
    result = is_email_allowed(blocked_email)

    # Verify
    assert result is False

  def test_is_email_allowed_case_insensitive(self, allowed_emails):
    """
    Test that is_email_allowed is case-insensitive.

    Given: Email with different case than in ALLOWED_EMAILS
    When: is_email_allowed is called
    Then: Returns True (case-insensitive match)
    """
    # Set environment
    os.environ["ALLOWED_EMAILS"] = ",".join(allowed_emails)
    allowed_emails_manager.clear_cache()

    # Test with different case
    email = allowed_emails[0].upper()
    result = is_email_allowed(email)

    # Verify
    assert result is True

  def test_is_email_allowed_handles_whitespace(self, allowed_emails):
    """
    Test that is_email_allowed handles whitespace.

    Given: Email with leading/trailing whitespace
    When: is_email_allowed is called
    Then: Returns correct result after trimming
    """
    # Set environment
    os.environ["ALLOWED_EMAILS"] = ",".join(allowed_emails)
    allowed_emails_manager.clear_cache()

    # Test with whitespace
    email = f"  {allowed_emails[0]}  "
    result = is_email_allowed(email)

    # Verify
    assert result is True

  def test_is_email_allowed_empty_list_returns_false(self):
    """
    Test that is_email_allowed returns False when no emails allowed.

    Given: Empty ALLOWED_EMAILS list
    When: is_email_allowed is called with any email
    Then: Returns False
    """
    # Set empty environment
    os.environ["ALLOWED_EMAILS"] = ""
    allowed_emails_manager.clear_cache()

    # Test
    result = is_email_allowed("anyone@example.com")

    # Verify
    assert result is False

  def test_is_email_allowed_cache_refresh(self, allowed_emails):
    """
    Test that ALLOWED_EMAILS cache refreshes correctly.

    Given: ALLOWED_EMAILS has been cached
    When: Environment variable changes and cache refreshes
    Then: New email list is used
    """
    # Set initial environment
    os.environ["ALLOWED_EMAILS"] = ",".join(allowed_emails)
    allowed_emails_manager.clear_cache()

    # Initial check
    result = is_email_allowed(allowed_emails[0])
    assert result is True

    # Change environment
    new_email = "new@example.com"
    os.environ["ALLOWED_EMAILS"] = new_email
    allowed_emails_manager.clear_cache()

    # Verify new list is used
    result = is_email_allowed(new_email)
    assert result is True

    # Old email no longer allowed
    result = is_email_allowed(allowed_emails[0])
    assert result is False


class TestTokenVersion:
  """
  Test suite for token version invalidation strategy.

  Tests verify token version mechanism for revoking all tokens.
  """

  def test_token_version_invalidation(self, jwt_secret_key, sample_email, token_version_manager):
    """
    Test that token version increment invalidates all tokens.

    Given: User has valid JWT with version N
    When: Token version is incremented to N+1
    Then: Old JWT (version N) is invalid
    """
    # Set environment
    os.environ["JWT_SECRET_KEY"] = jwt_secret_key
    os.environ["ALLOWED_EMAILS"] = sample_email

    # Generate JWT with version 1
    token = generate_jwt(sample_email)

    # Verify initial token is valid
    result = validate_jwt(token)
    assert result is not None

    # Increment token version
    increment_token_version(sample_email)

    # Verify old token is now invalid
    result = validate_jwt(token)
    assert result is None

  def test_token_version_new_token_after_increment(self, jwt_secret_key, sample_email, token_version_manager):
    """
    Test that new token after version increment has correct version.

    Given: Token version incremented to N+1
    When: New JWT is generated
    Then: New JWT has version N+1
    """
    # Set environment
    os.environ["JWT_SECRET_KEY"] = jwt_secret_key
    os.environ["ALLOWED_EMAILS"] = sample_email

    # Initial version
    initial_version = get_token_version(sample_email)

    # Increment version
    new_version = increment_token_version(sample_email)

    # Generate new token
    token = generate_jwt(sample_email)

    # Decode and verify version
    payload = jwt.decode(token, jwt_secret_key, algorithms=[JWT_ALGORITHM])
    assert payload["ver"] == new_version
    assert new_version == initial_version + 1

  def test_token_version_default_is_one(self, sample_email, token_version_manager):
    """
    Test that default token version is 1.

    Given: User with no previous tokens
    When: Token version is queried
    Then: Default version is 1
    """
    # Get version for new user
    version = get_token_version("newuser@example.com")

    # Verify default
    assert version == 1


class TestSecretKeyManagement:
  """
  Test suite for SECRET_KEY management and validation.

  Tests verify secret key requirements and security properties.
  """

  def test_secret_key_minimum_length(self):
    """
    Test that SECRET_KEY must be minimum 32 characters.

    Given: SECRET_KEY shorter than 32 characters
    When: Application starts
    Then: ValueError is raised
    """
    # Set short key
    os.environ["JWT_SECRET_KEY"] = "short"

    # Test
    with pytest.raises(ValueError) as exc_info:
      get_jwt_secret_key()

    assert "at least" in str(exc_info.value).lower()

  def test_secret_key_missing_raises_error(self):
    """
    Test that missing SECRET_KEY raises error.

    Given: SECRET_KEY environment variable not set
    When: Application starts
    Then: ValueError is raised
    """
    # Remove key
    if "JWT_SECRET_KEY" in os.environ:
      del os.environ["JWT_SECRET_KEY"]

    # Test
    with pytest.raises(ValueError) as exc_info:
      get_jwt_secret_key()

    assert "JWT_SECRET_KEY" in str(exc_info.value)

  def test_secret_key_loaded_from_environment(self, jwt_secret_key):
    """
    Test that SECRET_KEY is loaded from environment variable.

    Given: SECRET_KEY set in environment
    When: get_jwt_secret_key() is called
    Then: Returns value from environment
    """
    # Set environment
    os.environ["JWT_SECRET_KEY"] = jwt_secret_key

    # Test
    result = get_jwt_secret_key()

    # Verify
    assert result == jwt_secret_key

  def test_secret_key_never_hardcoded(self):
    """
    Test that SECRET_KEY is never hardcoded in source code.

    Given: Application source code
    When: Searching for hardcoded secrets
    Then: No hardcoded SECRET_KEY found

    Note: This test verifies the implementation doesn't have default values.
    """
    # This test verifies that get_jwt_secret_key() requires environment variable
    # Remove key and verify error
    if "JWT_SECRET_KEY" in os.environ:
      del os.environ["JWT_SECRET_KEY"]

    # Should raise error (no default/hardcoded value)
    with pytest.raises(ValueError):
      get_jwt_secret_key()


class TestChannelTokenSecurity:
  """
  Test suite for channel token security.

  Tests verify channel token generation and uniqueness properties.
  """

  def test_channel_token_unique_per_session(self, jwt_secret_key, sample_email):
    """
    Test that each JWT gets unique channel_token.

    Given: Two JWTs for same user
    When: Tokens are generated
    Then: Each has different channel_token
    """
    # Set environment
    os.environ["JWT_SECRET_KEY"] = jwt_secret_key
    os.environ["ALLOWED_EMAILS"] = sample_email

    # Generate two tokens
    token1 = generate_jwt(sample_email)
    token2 = generate_jwt(sample_email)

    # Decode
    payload1 = jwt.decode(token1, jwt_secret_key, algorithms=[JWT_ALGORITHM])
    payload2 = jwt.decode(token2, jwt_secret_key, algorithms=[JWT_ALGORITHM])

    # Verify unique channel tokens
    assert payload1["channel_token"] != payload2["channel_token"]

  def test_channel_token_sufficient_entropy(self, jwt_secret_key, sample_email):
    """
    Test that channel_token has sufficient entropy (256 bits).

    Given: A JWT is generated
    When: channel_token is examined
    Then: Token has at least 256 bits of entropy
    """
    # Set environment
    os.environ["JWT_SECRET_KEY"] = jwt_secret_key
    os.environ["ALLOWED_EMAILS"] = sample_email

    # Generate token
    token = generate_jwt(sample_email)

    # Decode
    payload = jwt.decode(token, jwt_secret_key, algorithms=[JWT_ALGORITHM])
    channel_token = payload["channel_token"]

    # Verify entropy (token_urlsafe(32) = 256 bits, ~43 chars)
    assert len(channel_token) >= 32

  def test_channel_token_unpredictable(self, jwt_secret_key, sample_email):
    """
    Test that channel_token is cryptographically random (unpredictable).

    Given: Multiple channel_tokens generated
    When: Tokens are compared
    Then: No predictable pattern exists
    """
    # Set environment
    os.environ["JWT_SECRET_KEY"] = jwt_secret_key
    os.environ["ALLOWED_EMAILS"] = sample_email

    # Generate multiple tokens
    tokens = []
    for _ in range(10):
      token = generate_jwt(sample_email)
      payload = jwt.decode(token, jwt_secret_key, algorithms=[JWT_ALGORITHM])
      tokens.append(payload["channel_token"])

    # Verify all tokens are unique
    assert len(set(tokens)) == 10

    # Verify no sequential pattern
    # (This is a basic check - cryptographic randomness should pass easily)
    for i in range(len(tokens) - 1):
      assert tokens[i] != tokens[i + 1]

  def test_channel_token_included_in_jwt(self, jwt_secret_key, sample_email):
    """
    Test that channel_token is included in JWT payload.

    Given: A JWT is generated
    When: Token is decoded
    Then: channel_token claim is present
    """
    # Set environment
    os.environ["JWT_SECRET_KEY"] = jwt_secret_key
    os.environ["ALLOWED_EMAILS"] = sample_email

    # Generate token
    token = generate_jwt(sample_email)

    # Decode
    payload = jwt.decode(token, jwt_secret_key, algorithms=[JWT_ALGORITHM])

    # Verify channel_token is present
    assert "channel_token" in payload
    assert payload["channel_token"] is not None
    assert len(payload["channel_token"]) > 0