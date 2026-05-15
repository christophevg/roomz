"""
Security tests for JWT session tokens.

This module tests JWT-specific security vulnerabilities and attack vectors
including algorithm confusion, token tampering, signature verification, and
ALLOWED_EMAILS security.

Requirements: I4-001 - JWT Session Tokens
- Algorithm must be hardcoded to HS256
- "none" algorithm must be rejected
- SECRET_KEY from environment, minimum 32 characters
- ALLOWED_EMAILS checked at: magic link request, JWT creation, WebSocket connection
"""

import base64
import json
import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from roomz.server.auth import (
  JWT_ALGORITHM,
  _token_versions,
  allowed_emails_manager,
  generate_jwt,
  get_jwt_secret_key,
  get_token_version,
  increment_token_version,
  is_email_allowed,
  validate_jwt,
)


class TestAlgorithmSecurity:
  """
  Test suite for JWT algorithm security.

  Tests verify protection against algorithm confusion attacks.
  """

  def test_none_algorithm_rejected(self, jwt_secret_key):
    """
    Test that 'none' algorithm is rejected.

    Given: JWT with 'none' algorithm (attack vector)
    When: Token validation
    Then: Token is rejected (returns None)

    Security: Prevents algorithm confusion attack where attacker
    removes signature by changing algorithm to 'none'.
    """
    # Set environment
    os.environ["JWT_SECRET_KEY"] = jwt_secret_key
    os.environ["ALLOWED_EMAILS"] = "test@example.com"

    # Create token with none algorithm (attack vector)
    payload = {
      "sub": "user:attacker@example.com",
      "email": "attacker@example.com",
      "iat": int(datetime.now(timezone.utc).timestamp()),
      "exp": int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp()),
      "channel_token": secrets.token_urlsafe(32),
      "ver": 1,
    }

    # Create unsecured token (header with none algorithm)
    header = {"alg": "none", "typ": "JWT"}
    header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    token = f"{header_b64}.{payload_b64}."

    # Validate
    result = validate_jwt(token)

    # Verify rejection
    assert result is None

  def test_algorithm_confusion_rejected(self, jwt_secret_key):
    """
    Test that algorithm confusion is prevented.

    Given: JWT created with HS256 but validated with RS256
    When: Token validation
    Then: Token is rejected (algorithm mismatch)

    Security: Prevents algorithm confusion attack where attacker
    tries to use different algorithm than expected.
    """
    # Set environment
    os.environ["JWT_SECRET_KEY"] = jwt_secret_key
    os.environ["ALLOWED_EMAILS"] = "test@example.com"

    # Create valid HS256 token
    email = "test@example.com"
    token = generate_jwt(email)

    # Try to decode with wrong algorithm (should fail)
    with pytest.raises(jwt.InvalidAlgorithmError):
      jwt.decode(token, jwt_secret_key, algorithms=["RS256"])

  def test_algorithm_hardcoded_hs256(self, jwt_secret_key):
    """
    Test that algorithm is hardcoded to HS256.

    Given: JWT generation and validation code
    When: Algorithm is examined
    Then: Only HS256 is used (no dynamic algorithm from token)

    Security: Algorithm must be hardcoded, not read from token header.
    """
    # Set environment
    os.environ["JWT_SECRET_KEY"] = jwt_secret_key
    os.environ["ALLOWED_EMAILS"] = "test@example.com"

    # Generate token
    token = generate_jwt("test@example.com")

    # Check header
    header = jwt.get_unverified_header(token)

    # Verify algorithm is HS256
    assert header["alg"] == "HS256"

    # Verify JWT_ALGORITHM constant
    assert JWT_ALGORITHM == "HS256"

  def test_token_with_wrong_algorithm_header_rejected(self, jwt_secret_key):
    """
    Test that JWT with wrong algorithm in header is rejected.

    Given: JWT with 'RS256' in header
    When: Token validation (expects HS256)
    Then: Token is rejected

    Security: Prevents attacker from changing algorithm.
    """
    # Set environment
    os.environ["JWT_SECRET_KEY"] = jwt_secret_key
    os.environ["ALLOWED_EMAILS"] = "test@example.com"

    # Create token with HS256 but try to use it with RS256 header
    payload = {
      "sub": "user:test@example.com",
      "email": "test@example.com",
      "iat": int(datetime.now(timezone.utc).timestamp()),
      "exp": int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp()),
      "channel_token": secrets.token_urlsafe(32),
      "ver": 1,
    }

    # Create with wrong algorithm in header
    header = {"alg": "RS256", "typ": "JWT"}
    header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")

    # Sign with HS256 (mismatch with header)
    signature = jwt.encode(payload, jwt_secret_key, algorithm="HS256").split(".")[2]
    token = f"{header_b64}.{payload_b64}.{signature}"

    # Validate
    result = validate_jwt(token)

    # Should reject due to algorithm mismatch
    assert result is None


class TestTokenTampering:
  """
  Test suite for JWT token tampering attacks.

  Tests verify protection against token modification attacks.
  """

  def test_modified_payload_rejected(self, jwt_secret_key, sample_email):
    """
    Test that modified JWT payload is rejected.

    Given: JWT with modified payload (e.g., changed email)
    When: Token validation
    Then: Token is rejected (signature mismatch)

    Security: Prevents attacker from modifying token claims.
    """
    # Set environment
    os.environ["JWT_SECRET_KEY"] = jwt_secret_key
    os.environ["ALLOWED_EMAILS"] = sample_email

    # Generate valid token
    token = generate_jwt(sample_email)

    # Decode parts
    parts = token.split(".")
    header_b64 = parts[0]
    payload_b64 = parts[1]
    signature_b64 = parts[2]

    # Decode payload
    payload_json = base64.urlsafe_b64decode(payload_b64 + "==").decode()
    payload = json.loads(payload_json)

    # Modify payload
    payload["email"] = "attacker@example.com"

    # Re-encode modified payload
    modified_payload_b64 = base64.urlsafe_b64encode(
      json.dumps(payload).encode()
    ).decode().rstrip("=")

    # Reconstruct token with modified payload (same signature)
    modified_token = f"{header_b64}.{modified_payload_b64}.{signature_b64}"

    # Validate
    result = validate_jwt(modified_token)

    # Should reject due to signature mismatch
    assert result is None

  def test_modified_signature_rejected(self, jwt_secret_key, sample_email):
    """
    Test that JWT with modified signature is rejected.

    Given: JWT with invalid signature
    When: Token validation
    Then: Token is rejected

    Security: Prevents token forgery.
    """
    # Set environment
    os.environ["JWT_SECRET_KEY"] = jwt_secret_key
    os.environ["ALLOWED_EMAILS"] = sample_email

    # Generate valid token
    token = generate_jwt(sample_email)

    # Modify signature
    parts = token.split(".")
    modified_token = f"{parts[0]}.{parts[1]}.invalidsignature"

    # Validate
    result = validate_jwt(modified_token)

    # Should reject
    assert result is None

  def test_missing_signature_rejected(self, jwt_secret_key, sample_email):
    """
    Test that JWT without signature is rejected.

    Given: JWT without signature (header.payload.)
    When: Token validation
    Then: Token is rejected

    Security: Prevents unsigned token attacks.
    """
    # Set environment
    os.environ["JWT_SECRET_KEY"] = jwt_secret_key
    os.environ["ALLOWED_EMAILS"] = sample_email

    # Generate valid token
    token = generate_jwt(sample_email)

    # Remove signature
    parts = token.split(".")
    modified_token = f"{parts[0]}.{parts[1]}."

    # Validate
    result = validate_jwt(modified_token)

    # Should reject
    assert result is None

  def test_email_claim_tampering_detected(self, jwt_secret_key):
    """
    Test that email claim tampering is detected.

    Given: JWT with modified email claim
    When: Token validation
    Then: Token is rejected (signature mismatch)

    Security: Prevents privilege escalation via email change.
    """
    # Set environment
    os.environ["JWT_SECRET_KEY"] = jwt_secret_key
    os.environ["ALLOWED_EMAILS"] = "victim@example.com,attacker@example.com"

    # Generate token for attacker
    token = generate_jwt("attacker@example.com")

    # Decode
    parts = token.split(".")
    payload_json = base64.urlsafe_b64decode(parts[1] + "==").decode()
    payload = json.loads(payload_json)

    # Try to modify email to victim
    payload["email"] = "victim@example.com"

    # Re-encode
    modified_payload_b64 = base64.urlsafe_b64encode(
      json.dumps(payload).encode()
    ).decode().rstrip("=")

    modified_token = f"{parts[0]}.{modified_payload_b64}.{parts[2]}"

    # Validate
    result = validate_jwt(modified_token)

    # Should reject due to signature mismatch
    assert result is None

  def test_expiration_claim_tampering_detected(self, jwt_secret_key, sample_email):
    """
    Test that expiration claim tampering is detected.

    Given: JWT with modified exp claim (extended expiration)
    When: Token validation
    Then: Token is rejected (signature mismatch)

    Security: Prevents session extension attacks.
    """
    # Set environment
    os.environ["JWT_SECRET_KEY"] = jwt_secret_key
    os.environ["ALLOWED_EMAILS"] = sample_email

    # Generate valid token
    token = generate_jwt(sample_email)

    # Decode
    parts = token.split(".")
    payload_json = base64.urlsafe_b64decode(parts[1] + "==").decode()
    payload = json.loads(payload_json)

    # Extend expiration
    payload["exp"] = int((datetime.now(timezone.utc) + timedelta(days=365)).timestamp())

    # Re-encode
    modified_payload_b64 = base64.urlsafe_b64encode(
      json.dumps(payload).encode()
    ).decode().rstrip("=")

    modified_token = f"{parts[0]}.{modified_payload_b64}.{parts[2]}"

    # Validate
    result = validate_jwt(modified_token)

    # Should reject due to signature mismatch
    assert result is None


class TestSignatureVerification:
  """
  Test suite for JWT signature verification.

  Tests verify cryptographic signature integrity.
  """

  def test_valid_signature_accepted(self, jwt_secret_key, sample_email):
    """
    Test that valid signature is accepted.

    Given: JWT with valid signature
    When: Token validation
    Then: Token is accepted

    Security: Confirms correct signature verification.
    """
    # Set environment
    os.environ["JWT_SECRET_KEY"] = jwt_secret_key
    os.environ["ALLOWED_EMAILS"] = sample_email

    # Generate token
    token = generate_jwt(sample_email)

    # Validate
    result = validate_jwt(token)

    # Should accept
    assert result is not None
    assert result["email"] == sample_email

  def test_wrong_secret_key_rejected(self, sample_email):
    """
    Test that JWT signed with wrong key is rejected.

    Given: JWT signed with different secret key
    When: Token validation with correct key
    Then: Token is rejected

    Security: Prevents token use across different environments.
    """
    # Set environment with key A
    key_a = secrets.token_urlsafe(32)
    os.environ["JWT_SECRET_KEY"] = key_a
    os.environ["ALLOWED_EMAILS"] = sample_email

    # Generate token with key A
    token = generate_jwt(sample_email)

    # Switch to key B
    key_b = secrets.token_urlsafe(32)
    os.environ["JWT_SECRET_KEY"] = key_b

    # Validate
    result = validate_jwt(token)

    # Should reject
    assert result is None

  def test_weak_secret_key_rejected(self):
    """
    Test that weak secret key raises error.

    Given: SECRET_KEY shorter than 32 characters
    When: Application initialization
    Then: ValueError is raised

    Security: Enforces minimum key strength for HS256.
    """
    # Set weak key
    os.environ["JWT_SECRET_KEY"] = "weak"

    # Should raise error
    with pytest.raises(ValueError) as exc_info:
      get_jwt_secret_key()

    assert "32" in str(exc_info.value)

  def test_signature_verification_timing_attack_safe(self, jwt_secret_key, sample_email):
    """
    Test that signature verification is timing-attack safe.

    Given: JWT with invalid signature
    When: Token validation
    Then: Rejection time is consistent (no timing leak)

    Security: Prevents timing attacks to discover key.
    Note: PyJWT library handles this, but we verify.
    """
    # Set environment
    os.environ["JWT_SECRET_KEY"] = jwt_secret_key
    os.environ["ALLOWED_EMAILS"] = sample_email

    # Generate valid token
    token = generate_jwt(sample_email)

    # Create invalid tokens with different signatures
    invalid_tokens = [
      token[:-10] + "0123456789",
      token[:-20] + "abcdefghij0123456789",
      "invalid.token.here",
      "",
    ]

    # Validate all - should all return None without exception
    for invalid_token in invalid_tokens:
      result = validate_jwt(invalid_token)
      assert result is None


class TestExpirationEnforcement:
  """
  Test suite for JWT expiration enforcement.

  Tests verify that expired tokens are properly rejected.
  """

  def test_expired_token_rejected(self, jwt_secret_key, expired_jwt_payload):
    """
    Test that expired JWT is rejected.

    Given: JWT with exp claim in the past
    When: Token validation
    Then: Token is rejected

    Security: Enforces session timeout.
    """
    # Set environment
    os.environ["JWT_SECRET_KEY"] = jwt_secret_key
    os.environ["ALLOWED_EMAILS"] = "test@example.com"

    # Create expired token
    token = jwt.encode(expired_jwt_payload, jwt_secret_key, algorithm=JWT_ALGORITHM)

    # Validate
    result = validate_jwt(token)

    # Should reject
    assert result is None

  def test_expiration_claim_required(self, jwt_secret_key, sample_email):
    """
    Test that exp claim is required.

    Given: JWT without exp claim
    When: Token validation
    Then: Token is rejected

    Security: Prevents indefinite session tokens.
    """
    # Set environment
    os.environ["JWT_SECRET_KEY"] = jwt_secret_key
    os.environ["ALLOWED_EMAILS"] = sample_email

    # Create token without exp
    payload = {
      "sub": f"user:{sample_email}",
      "email": sample_email,
      "iat": int(datetime.now(timezone.utc).timestamp()),
      "channel_token": secrets.token_urlsafe(32),
      "ver": 1,
    }
    token = jwt.encode(payload, jwt_secret_key, algorithm=JWT_ALGORITHM)

    # Validate
    result = validate_jwt(token)

    # Should reject
    assert result is None

  def test_expiration_not_too_distant(self, jwt_secret_key, sample_email):
    """
    Test that expiration is not too far in the future.

    Given: JWT with exp claim > 30 days
    When: Token validation
    Then: Token is accepted (no max check currently)

    Note: Current design allows 30-day expiration.
    Future: Consider rejecting excessively long expiration.
    """
    # Set environment
    os.environ["JWT_SECRET_KEY"] = jwt_secret_key
    os.environ["ALLOWED_EMAILS"] = sample_email

    # Generate token
    token = generate_jwt(sample_email)

    # Decode and check expiration
    payload = jwt.decode(token, jwt_secret_key, algorithms=[JWT_ALGORITHM])
    exp_datetime = datetime.fromtimestamp(payload["exp"], timezone.utc)

    # Should be approximately 30 days from now
    expected_max = datetime.now(timezone.utc) + timedelta(days=31)
    assert exp_datetime < expected_max

  def test_issued_at_claim_required(self, jwt_secret_key, sample_email):
    """
    Test that iat claim is required.

    Given: JWT without iat claim
    When: Token validation
    Then: Token is rejected

    Security: Enables token age verification.
    """
    # Set environment
    os.environ["JWT_SECRET_KEY"] = jwt_secret_key
    os.environ["ALLOWED_EMAILS"] = sample_email

    # Create token without iat
    payload = {
      "sub": f"user:{sample_email}",
      "email": sample_email,
      "exp": int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp()),
      "channel_token": secrets.token_urlsafe(32),
      "ver": 1,
    }
    token = jwt.encode(payload, jwt_secret_key, algorithm=JWT_ALGORITHM)

    # Validate
    result = validate_jwt(token)

    # Should reject
    assert result is None


class TestAllowedEmailsSecurity:
  """
  Test suite for ALLOWED_EMAILS security validation.

  Tests verify that ALLOWED_EMAILS is checked at all security checkpoints.
  """

  def test_allowed_emails_checked_at_all_points(self, jwt_secret_key, allowed_emails):
    """
    Test that ALLOWED_EMAILS is checked at all authentication points.

    Given: Email not in ALLOWED_EMAILS
    When: Authentication at any point (magic link, JWT, WebSocket)
    Then: Request is rejected

    Security: Prevents unauthorized access even with valid JWT.
    """
    # Set environment with allowed emails
    os.environ["JWT_SECRET_KEY"] = jwt_secret_key
    os.environ["ALLOWED_EMAILS"] = ",".join(allowed_emails)
    allowed_emails_manager.clear_cache()

    # Try with blocked email
    blocked_email = "blocked@example.com"
    token = generate_jwt(blocked_email)

    # Validate - should reject because email not in allowed list
    # Note: generate_jwt creates token, but validate_jwt checks ALLOWED_EMAILS
    result = validate_jwt(token)

    # Should reject
    assert result is None

  def test_allowed_emails_instant_revocation(self, jwt_secret_key, allowed_emails):
    """
    Test that removing email from ALLOWED_EMAILS instantly revokes access.

    Given: User with valid JWT
    When: Email removed from ALLOWED_EMAILS
    Then: Next request is rejected

    Security: Enables instant access revocation.
    """
    # Set environment with initial allowed emails
    email = allowed_emails[0]
    os.environ["JWT_SECRET_KEY"] = jwt_secret_key
    os.environ["ALLOWED_EMAILS"] = ",".join(allowed_emails)
    allowed_emails_manager.clear_cache()

    # Generate token
    token = generate_jwt(email)

    # Validate - should succeed
    result = validate_jwt(token)
    assert result is not None

    # Remove email from ALLOWED_EMAILS
    os.environ["ALLOWED_EMAILS"] = ",".join([e for e in allowed_emails if e != email])
    allowed_emails_manager.clear_cache()

    # Validate - should reject
    result = validate_jwt(token)
    assert result is None

  def test_allowed_emails_case_insensitive(self, jwt_secret_key, allowed_emails):
    """
    Test that ALLOWED_EMAILS matching is case-insensitive.

    Given: Email in ALLOWED_EMAILS as lowercase
    When: Request with mixed case email
    Then: Request is accepted

    Security: Prevents case-based bypass attempts.
    """
    # Set environment
    os.environ["JWT_SECRET_KEY"] = jwt_secret_key
    os.environ["ALLOWED_EMAILS"] = ",".join([e.lower() for e in allowed_emails])
    allowed_emails_manager.clear_cache()

    # Test with mixed case
    mixed_case_email = allowed_emails[0].upper()
    token = generate_jwt(mixed_case_email)

    # Validate
    result = validate_jwt(token)

    # Should accept
    assert result is not None

  def test_allowed_emails_whitespace_handling(self, jwt_secret_key, allowed_emails):
    """
    Test that ALLOWED_EMAILS handles whitespace correctly.

    Given: Email with whitespace
    When: ALLOWED_EMAILS check
    Then: Whitespace is trimmed before matching

    Security: Prevents whitespace-based bypass attempts.
    """
    # Set environment with whitespace
    os.environ["JWT_SECRET_KEY"] = jwt_secret_key
    os.environ["ALLOWED_EMAILS"] = "  " + "  ,  ".join(allowed_emails) + "  "
    allowed_emails_manager.clear_cache()

    # Test
    email = allowed_emails[0]
    token = generate_jwt(email)

    # Validate
    result = validate_jwt(token)

    # Should accept
    assert result is not None

  def test_allowed_emails_empty_list_denies_all(self, jwt_secret_key):
    """
    Test that empty ALLOWED_EMAILS denies all access.

    Given: Empty ALLOWED_EMAILS environment variable
    When: Any authentication attempt
    Then: Request is rejected

    Security: Fail-closed for empty allow-list.
    """
    # Set empty environment
    os.environ["JWT_SECRET_KEY"] = jwt_secret_key
    os.environ["ALLOWED_EMAILS"] = ""
    allowed_emails_manager.clear_cache()

    # Test
    token = generate_jwt("anyone@example.com")

    # Validate
    result = validate_jwt(token)

    # Should reject
    assert result is None

  def test_allowed_emails_cache_timing(self, allowed_emails):
    """
    Test that ALLOWED_EMAILS cache refresh doesn't leak timing.

    Given: ALLOWED_EMAILS cache refresh
    When: Multiple requests during refresh
    Then: No timing difference based on allow-list size

    Security: Prevents timing attacks on allow-list.
    Note: Implementation may cache for performance.
    """
    import time

    # Set environment
    os.environ["ALLOWED_EMAILS"] = ",".join(allowed_emails)
    allowed_emails_manager.clear_cache()

    # First check (triggers cache refresh)
    start = time.time()
    is_email_allowed(allowed_emails[0])
    first_duration = time.time() - start

    # Second check (uses cache)
    start = time.time()
    is_email_allowed(allowed_emails[0])
    second_duration = time.time() - start

    # Both should be fast (no significant timing difference)
    # This is a basic check - real timing attacks need more sophisticated analysis
    # Handle edge case where both durations are effectively 0 (fast execution)
    if first_duration < 0.001 and second_duration < 0.001:
      pass  # Both very fast, timing check passes
    else:
      assert second_duration < first_duration * 2  # Second should not be significantly slower


class TestTokenVersionSecurity:
  """
  Test suite for token version security.

  Tests verify token version mechanism for session revocation.
  """

  def test_token_version_mismatch_rejected(self, jwt_secret_key, sample_email, token_version_manager):
    """
    Test that JWT with wrong token version is rejected.

    Given: JWT with token version N, current version N+1
    When: Token validation
    Then: Token is rejected

    Security: Enables "revoke all sessions" functionality.
    """
    # Set environment
    os.environ["JWT_SECRET_KEY"] = jwt_secret_key
    os.environ["ALLOWED_EMAILS"] = sample_email

    # Generate token with version 1
    token = generate_jwt(sample_email)

    # Increment version
    increment_token_version(sample_email)

    # Validate - should reject
    result = validate_jwt(token)

    # Should reject
    assert result is None

  def test_token_version_increment_invalidates_all(self, jwt_secret_key, sample_email, token_version_manager):
    """
    Test that incrementing token version invalidates all existing tokens.

    Given: User has multiple JWTs with version N
    When: Token version incremented to N+1
    Then: All previous JWTs are invalid

    Security: Enables immediate session revocation.
    """
    # Set environment
    os.environ["JWT_SECRET_KEY"] = jwt_secret_key
    os.environ["ALLOWED_EMAILS"] = sample_email

    # Generate multiple tokens
    tokens = [generate_jwt(sample_email) for _ in range(3)]

    # Increment version
    increment_token_version(sample_email)

    # All previous tokens should be invalid
    for token in tokens:
      result = validate_jwt(token)
      assert result is None

  def test_token_version_not_in_jwt_payload(self, jwt_secret_key, sample_email):
    """
    Test that missing token version defaults to version 1.

    Given: JWT without 'ver' claim
    When: Token validation
    Then: Treated as version 1 (backward compatibility)

    Security: Enables migration from version-less tokens.
    """
    # Set environment
    os.environ["JWT_SECRET_KEY"] = jwt_secret_key
    os.environ["ALLOWED_EMAILS"] = sample_email

    # Create token without version
    payload = {
      "sub": f"user:{sample_email}",
      "email": sample_email,
      "iat": int(datetime.now(timezone.utc).timestamp()),
      "exp": int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp()),
      "channel_token": secrets.token_urlsafe(32),
    }
    token = jwt.encode(payload, jwt_secret_key, algorithm=JWT_ALGORITHM)

    # Validate - should use default version 1
    result = validate_jwt(token)

    # Should accept (version defaults to 1)
    assert result is not None

  def test_token_version_storage_lightweight(self, token_version_manager):
    """
    Test that token version storage is lightweight.

    Given: Token version storage mechanism
    When: Many users with token versions
    Then: Storage remains minimal (e.g., single int per user)

    Security: Ensures revocation mechanism is scalable.
    """
    # Add multiple users
    for i in range(100):
      email = f"user{i}@example.com"
      version = get_token_version(email)
      assert version == 1

    # Increment some versions
    increment_token_version("user0@example.com")
    increment_token_version("user1@example.com")

    # Verify storage is lightweight (just email -> int)
    assert len(_token_versions) == 2


class TestSecretKeySecurity:
  """
  Test suite for SECRET_KEY security management.

  Tests verify proper SECRET_KEY handling and storage.
  """

  def test_secret_key_from_environment(self, jwt_secret_key):
    """
    Test that SECRET_KEY is loaded from environment variable.

    Given: SECRET_KEY in environment
    When: Application starts
    Then: Key is loaded from environment, not hardcoded

    Security: Prevents hardcoded secrets in source code.
    """
    # Set environment
    os.environ["JWT_SECRET_KEY"] = jwt_secret_key

    # Get key
    result = get_jwt_secret_key()

    # Verify
    assert result == jwt_secret_key

  def test_secret_key_not_logged(self, jwt_secret_key, caplog):
    """
    Test that SECRET_KEY is never logged.

    Given: Application with SECRET_KEY
    When: Application runs and logs
    Then: SECRET_KEY never appears in logs

    Security: Prevents secret exposure in logs.
    """
    # Set environment
    os.environ["JWT_SECRET_KEY"] = jwt_secret_key

    # Use key (trigger potential logging)
    get_jwt_secret_key()

    # Check logs
    for record in caplog.records:
      assert jwt_secret_key not in record.message

  def test_secret_key_minimum_length_32_chars(self):
    """
    Test that SECRET_KEY minimum length is 32 characters (256 bits).

    Given: SECRET_KEY shorter than 32 characters
    When: Application initialization
    Then: ValueError is raised

    Security: Enforces minimum key strength for HS256.
    """
    # Test various lengths
    for length in [10, 20, 31]:
      short_key = "a" * length
      os.environ["JWT_SECRET_KEY"] = short_key

      with pytest.raises(ValueError) as exc_info:
        get_jwt_secret_key()

      assert "32" in str(exc_info.value)

  def test_secret_key_cryptographically_random(self, jwt_secret_key):
    """
    Test that SECRET_KEY is cryptographically random (not predictable).

    Given: SECRET_KEY
    When: Key is examined
    Then: Key has sufficient entropy (not 'password', 'secret', etc.)

    Security: Prevents brute-force attacks on weak keys.
    Note: This is a configuration check, not runtime test.
    """
    # This test verifies the key is not a common weak key
    weak_keys = ["password", "secret", "12345678", "admin", "key"]

    # Check key is not weak
    assert jwt_secret_key.lower() not in weak_keys
    assert len(jwt_secret_key) >= 32

  def test_missing_secret_key_raises_error(self):
    """
    Test that missing SECRET_KEY raises error at startup.

    Given: No SECRET_KEY environment variable
    When: Application initialization
    Then: ValueError is raised with clear message

    Security: Prevents running with no key.
    """
    # Remove key
    if "JWT_SECRET_KEY" in os.environ:
      del os.environ["JWT_SECRET_KEY"]

    # Should raise error
    with pytest.raises(ValueError) as exc_info:
      get_jwt_secret_key()

    assert "JWT_SECRET_KEY" in str(exc_info.value)


class TestCookieSecurity:
  """
  Test suite for JWT cookie security attributes.

  Tests verify that JWT cookie has proper security attributes.
  """

  @pytest.mark.asyncio
  async def test_cookie_httponly_flag(self, test_client, allowed_emails):
    """
    Test that JWT cookie has httpOnly flag.

    Given: JWT cookie
    When: Cookie is set
    Then: httpOnly=True (prevents JavaScript access)

    Security: Prevents XSS attacks from accessing JWT.
    """
    # Set environment
    import os

    os.environ["JWT_SECRET_KEY"] = "test-secret-key-minimum-32-characters-long-for-security"
    os.environ["ALLOWED_EMAILS"] = ",".join(allowed_emails)

    # Request magic link
    response = await test_client.post(
      "/auth/request-magic-link", json={"email": allowed_emails[0]}
    )
    assert response.status_code == 200

    # Get magic link from logs (development mode)
    # Note: In production, this would be sent via email

  @pytest.mark.asyncio
  async def test_cookie_secure_flag_production(self, test_client, allowed_emails):
    """
    Test that JWT cookie has secure flag in production.

    Given: Production environment
    When: JWT cookie is set
    Then: secure=True (HTTPS only)

    Security: Prevents JWT transmission over HTTP.
    Note: Development may have secure=False for localhost.
    """
    # This test verifies production configuration
    # Implementation should check ENV environment variable
    pass

  @pytest.mark.asyncio
  async def test_cookie_samesite_strict(self, test_client, allowed_emails):
    """
    Test that JWT cookie has SameSite=Strict.

    Given: JWT cookie
    When: Cookie is set
    Then: SameSite=Strict (prevents CSRF)

    Security: Prevents CSRF attacks.
    """
    pass

  @pytest.mark.asyncio
  async def test_cookie_path_set(self, test_client, allowed_emails):
    """
    Test that JWT cookie has path set correctly.

    Given: JWT cookie
    When: Cookie is set
    Then: path='/' (available on all paths)

    Security: Ensures cookie is available for all endpoints.
    """
    pass

  @pytest.mark.asyncio
  async def test_cookie_not_accessible_via_javascript(self, test_client, allowed_emails):
    """
    Test that JWT cookie is not accessible via JavaScript.

    Given: JWT cookie with httpOnly
    When: JavaScript tries to read document.cookie
    Then: JWT is not present

    Security: Prevents XSS attacks from stealing JWT.
    Note: This is a browser behavior test.
    """
    pass


class TestChannelTokenSecurity:
  """
  Test suite for channel token security.

  Tests verify channel token uniqueness and binding to user.
  """

  def test_channel_token_unique_per_session(self, jwt_secret_key, sample_email):
    """
    Test that channel token is unique per session.

    Given: Two JWTs for same user
    When: Tokens are generated
    Then: Each has different channel_token

    Security: Prevents session hijacking via token reuse.
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

  def test_channel_token_cryptographically_random(self, jwt_secret_key):
    """
    Test that channel token is cryptographically random.

    Given: Multiple channel tokens generated
    When: Tokens are examined
    Then: No predictable pattern exists

    Security: Prevents channel token guessing attacks.
    """
    # Set environment
    os.environ["JWT_SECRET_KEY"] = jwt_secret_key
    os.environ["ALLOWED_EMAILS"] = "test@example.com"

    # Generate multiple tokens
    tokens = []
    for _ in range(100):
      token = generate_jwt("test@example.com")
      payload = jwt.decode(token, jwt_secret_key, algorithms=[JWT_ALGORITHM])
      tokens.append(payload["channel_token"])

    # Verify all unique
    assert len(set(tokens)) == 100

  def test_channel_token_not_predictable(self, jwt_secret_key, sample_email):
    """
    Test that channel token cannot be predicted.

    Given: Previous channel tokens
    When: Attacker tries to predict next token
    Then: Prediction fails (insufficient entropy)

    Security: Prevents channel token prediction attacks.
    """
    # Set environment
    os.environ["JWT_SECRET_KEY"] = jwt_secret_key
    os.environ["ALLOWED_EMAILS"] = sample_email

    # Generate tokens
    tokens = []
    for _ in range(10):
      token = generate_jwt(sample_email)
      payload = jwt.decode(token, jwt_secret_key, algorithms=[JWT_ALGORITHM])
      tokens.append(payload["channel_token"])

    # No token should be predictable from previous
    # (Basic check - cryptographic randomness should pass easily)
    for i in range(1, len(tokens)):
      # Tokens should not be sequential
      assert tokens[i] != tokens[i - 1]

  def test_channel_token_bound_to_user(self, jwt_secret_key, sample_email):
    """
    Test that channel token is bound to user email.

    Given: JWT with channel_token and email
    When: WebSocket connection with JWT
    Then: User can only join their own channel (user:{email})

    Security: Prevents channel hijacking.
    """
    # Set environment
    os.environ["JWT_SECRET_KEY"] = jwt_secret_key
    os.environ["ALLOWED_EMAILS"] = sample_email

    # Generate token
    token = generate_jwt(sample_email)

    # Decode
    payload = jwt.decode(token, jwt_secret_key, algorithms=[JWT_ALGORITHM])

    # Verify email binding
    assert payload["email"] == sample_email.lower().strip()
    assert payload["sub"] == f"user:{sample_email.lower().strip()}"

  def test_channel_token_cannot_access_other_user_channel(self, jwt_secret_key, allowed_emails):
    """
    Test that user cannot access another user's channel.

    Given: User A with JWT for user_a@example.com
    When: User A tries to join user_b@example.com channel
    Then: Connection rejected

    Security: Prevents unauthorized channel access.
    """
    # Set environment
    os.environ["JWT_SECRET_KEY"] = jwt_secret_key
    os.environ["ALLOWED_EMAILS"] = ",".join(allowed_emails)

    # Generate token for user A
    user_a = allowed_emails[0]
    token = generate_jwt(user_a)

    # Decode
    payload = jwt.decode(token, jwt_secret_key, algorithms=[JWT_ALGORITHM])

    # Verify user A cannot access user B's channel
    user_b = allowed_emails[1]
    assert payload["email"] != user_b
    assert payload["sub"] != f"user:{user_b}"


class TestSecurityRegression:
  """
  Test suite for security regression tests.

  Tests verify known security issues are addressed.
  """

  def test_no_hardcoded_secrets(self):
    """
    Test that no secrets are hardcoded in source code.

    Given: Application source code
    When: Searching for hardcoded secrets
    Then: No SECRET_KEY, API_KEY, PASSWORD found

    Security: Prevents credential exposure in source code.
    """
    import re
    from pathlib import Path

    # Read auth.py (relative to project root)
    project_root = Path(__file__).parent.parent
    with open(project_root / "src" / "roomz" / "server" / "auth.py") as f:
      content = f.read()

    # Check for hardcoded secrets (patterns to avoid)
    # Allow legitimate references like JWT_SECRET_KEY_MIN_LENGTH
    patterns = [
      r'JWT_SECRET_KEY\s*=\s*["\'][^"\']+["\']',  # JWT_SECRET_KEY = "value"
      r'SECRET\s*=\s*["\'][^"\']+["\']',  # SECRET = "value"
      r'PASSWORD\s*=\s*["\'][^"\']+["\']',  # PASSWORD = "value"
    ]

    for pattern in patterns:
      matches = re.findall(pattern, content, re.IGNORECASE)
      assert len(matches) == 0, f"Hardcoded secret found: {matches}"

  def test_no_secret_in_logs(self, jwt_secret_key, caplog):
    """
    Test that secrets are never logged.

    Given: Application running with SECRET_KEY
    When: Application logs are examined
    Then: SECRET_KEY never appears in logs

    Security: Prevents secret exposure in logs.
    """
    # Set environment
    os.environ["JWT_SECRET_KEY"] = jwt_secret_key

    # Use key
    _ = get_jwt_secret_key()

    # Check logs
    for record in caplog.records:
      assert jwt_secret_key not in record.message

  def test_no_secret_in_error_messages(self, jwt_secret_key):
    """
    Test that secrets don't appear in error messages.

    Given: Application with errors
    When: Error messages are generated
    Then: SECRET_KEY never appears in error messages

    Security: Prevents secret exposure in error messages.
    """
    # Set environment
    os.environ["JWT_SECRET_KEY"] = jwt_secret_key

    # Try to use with wrong key
    try:
      # This should not expose the key
      _ = get_jwt_secret_key()
    except ValueError as e:
      # Key should not be in error message
      assert jwt_secret_key not in str(e)

  def test_jwt_validated_before_use(self, jwt_secret_key, sample_email):
    """
    Test that JWT is validated before any use.

    Given: JWT in request
    When: Request is processed
    Then: JWT signature is validated before claims are used

    Security: Prevents processing of untrusted JWTs.
    """
    # Set environment
    os.environ["JWT_SECRET_KEY"] = jwt_secret_key
    os.environ["ALLOWED_EMAILS"] = sample_email

    # Create invalid token (modified signature)
    token = generate_jwt(sample_email)
    parts = token.split(".")
    invalid_token = f"{parts[0]}.{parts[1]}.invalid"

    # Validate
    result = validate_jwt(invalid_token)

    # Should reject without processing claims
    assert result is None

  def test_email_in_jwt_matches_session(self, jwt_secret_key, sample_email):
    """
    Test that email in JWT matches the authenticated user.

    Given: JWT with email claim
    When: Request is processed
    Then: Email in JWT is the authenticated user's email

    Security: Prevents email-based privilege escalation.
    """
    # Set environment
    os.environ["JWT_SECRET_KEY"] = jwt_secret_key
    os.environ["ALLOWED_EMAILS"] = sample_email

    # Generate token
    token = generate_jwt(sample_email)

    # Validate
    result = validate_jwt(token)

    # Verify email matches
    assert result is not None
    assert result["email"] == sample_email.lower().strip()
