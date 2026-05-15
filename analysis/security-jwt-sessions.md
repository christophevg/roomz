# Security Review Report: I4-001 JWT Session Tokens

**Task**: I4-001 - Replace in-memory session storage with JWT tokens
**Date**: 2026-05-15
**Analyst**: Security Engineer Agent
**Status**: Pre-Implementation Security Review

## Executive Summary

This security review analyzes the planned migration from in-memory sessions to stateless JWT tokens for authentication. The implementation introduces significant architectural changes that require careful security consideration.

**Key Security Trade-offs**:
- **Gains**: Stateless sessions, horizontal scalability, server restart tolerance
- **Losses**: Immediate token revocation capability, server-side session invalidation
- **Risk Level**: **MEDIUM-HIGH** - Proper mitigation strategies required

The most critical security consideration is the inability to immediately revoke individual JWT tokens. The ALLOWED_EMAILS mechanism provides a workaround for user-level revocation but introduces its own complexity.

## Security Findings Classification

| Finding | Classification | Action |
|---------|---------------|--------|
| JWT token revocation limitation | Blocking | Must implement mitigation strategy |
| SECRET_KEY management | Blocking | Must use environment variable with strong key |
| Algorithm confusion vulnerability | Blocking | Must hardcode algorithm in verification |
| ALLOWED_EMAILS validation timing | Blocking | Must validate on every request |
| Cookie security flags | Related | Verify production configuration |
| Token expiration strategy | Related | Implement appropriate expiration |
| Channel token security | Related | Validate token binding |
| Stateless session risks | Related | Document trade-offs clearly |

---

## Critical Findings (CVSS 9.0-10.0)

### CRITICAL-1: JWT Token Revocation Limitation

**OWASP Category**: A07:2025 - Authentication Failures
**STRIDE**: Spoofing, Elevation of Privilege
**CVSS Score**: 9.1 (Critical)

**Description**: JWTs are inherently stateless and cannot be individually revoked before expiration. Once issued, a JWT remains valid until its expiration time. This creates significant security risks for session management.

**Impact**:
- Stolen JWT provides access for entire expiration period
- Cannot immediately revoke compromised sessions
- Cannot implement "logout all devices" functionality
- User removal from ALLOWED_EMAILS does not invalidate existing tokens until expiration
- Insider threat: employee with valid token retains access after termination

**Current State (In-Memory Sessions)**:
```python
# Current: Can immediately revoke
def revoke_session(self, token: str) -> bool:
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    if token_hash in self._sessions:
        del self._sessions[token_hash]  # Immediate revocation
        return True
```

**Proposed State (JWT)**:
```python
# JWT: No server-side storage, no revocation
jwt_payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
# Token valid until exp claim - no way to revoke!
```

**Remediation Options**:

**Option A: Token Version Strategy (Recommended for I4-001)**

Store a `token_version` per user and include in JWT:

```python
# app/models.py - Add to User model
@dataclass
class User:
    email: str
    token_version: int = 1

# app/auth.py - JWT creation
def create_jwt_session(email: str, user_repo: UserRepository) -> str:
    user = user_repo.get_by_email(email)

    payload = {
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(days=30),
        "iat": datetime.now(timezone.utc),
        "ver": user.token_version,  # Version claim
        "channel_token": secrets.token_urlsafe(32)
    }

    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

# app/auth.py - JWT validation
def validate_jwt(token: str, user_repo: UserRepository) -> dict | None:
    payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])

    # Check token version
    user = user_repo.get_by_email(payload["email"])
    if payload["ver"] != user.token_version:
        # Token version mismatch - revoked
        return None

    # Check email still allowed
    if payload["email"] not in ALLOWED_EMAILS:
        return None

    return payload

# Revoke all tokens for user
def revoke_all_sessions(email: str, user_repo: UserRepository):
    user = user_repo.get_by_email(email)
    user.token_version += 1
    user_repo.save(user)
    # All existing JWTs now invalid
```

**Pros**:
- Immediate "revoke all" capability
- Single database field update
- Small storage footprint (one int per user)

**Cons**:
- Requires user storage
- Cannot revoke single device/session

**Option B: Token Denylist (Blocklist)**

```python
import redis
from datetime import datetime, timezone, timedelta

class JWTDenylist:
    """Redis-based token denylist for immediate revocation."""

    def __init__(self, redis_url: str):
        self.redis = redis.from_url(redis_url)

    def revoke_token(self, token: str):
        """Add token to denylist."""
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"], options={"verify_exp": False})

        # Calculate remaining TTL
        exp = datetime.fromtimestamp(payload["exp"], timezone.utc)
        now = datetime.now(timezone.utc)
        ttl = int((exp - now).total_seconds())

        if ttl > 0:
            jti = payload.get("jti") or payload.get("channel_token")
            self.redis.setex(f"revoked:{jti}", ttl, "1")

    def is_revoked(self, token: str) -> bool:
        """Check if token is revoked."""
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"], options={"verify_exp": False})
        jti = payload.get("jti") or payload.get("channel_token")
        return bool(self.redis.get(f"revoked:{jti}"))

# Usage in validation
def validate_jwt_with_denylist(token: str, denylist: JWTDenylist) -> dict | None:
    payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])

    # Check denylist
    if denylist.is_revoked(token):
        return None

    # Check ALLOWED_EMAILS
    if payload["email"] not in ALLOWED_EMAILS:
        return None

    return payload
```

**Pros**:
- Per-token revocation capability
- Supports logout functionality

**Cons**:
- Redis dependency
- Lookup on every request
- Denylist grows with revocations

**Option C: Short Expiration + Refresh Tokens**

```python
# Access token: 15 minutes
# Refresh token: 30 days (stored server-side)

def create_session_tokens(email: str) -> dict:
    # Short-lived access token
    access_token = jwt.encode({
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
        "type": "access",
        "channel_token": secrets.token_urlsafe(32)
    }, SECRET_KEY, algorithm="HS256")

    # Long-lived refresh token (opaque, stored server-side)
    refresh_token = secrets.token_urlsafe(32)
    refresh_tokens[hashlib.sha256(refresh_token.encode()).hexdigest()] = {
        "email": email,
        "expires_at": datetime.now(timezone.utc) + timedelta(days=30)
    }

    return {"access_token": access_token, "refresh_token": refresh_token}

def revoke_session(refresh_token: str):
    """Revoke refresh token - access token expires in 15 min max."""
    token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
    refresh_tokens.pop(token_hash, None)
    # Access token still valid for up to 15 minutes
```

**Pros**:
- Maximum exposure window: 15 minutes
- Logout functionality via refresh token revocation

**Cons**:
- More complex implementation
- Still has vulnerability window
- Requires server-side refresh token storage

**Recommendation for I4-001**:

Use **Option A (Token Version)** combined with **ALLOWED_EMAILS validation**:

```python
# Minimal implementation for I4-001
# Token version stored in lightweight storage (file-based or in-memory dict)

token_versions = {}  # {email: int}

def get_token_version(email: str) -> int:
    return token_versions.get(email, 1)

def revoke_all_tokens(email: str):
    token_versions[email] = token_versions.get(email, 0) + 1

def validate_jwt(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])

        # Check expiration (automatic)
        # Check token version
        current_version = get_token_version(payload["email"])
        if payload.get("ver", 1) != current_version:
            return None

        # Check ALLOWED_EMAILS (immediate revocation)
        if payload["email"] not in get_allowed_emails():
            return None

        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
```

**Reference**:
- [OWASP A07:2025 - Authentication Failures](https://owasp.org/Top10/A07_2025-Identification_and_Authentication_Failures/)
- [OWASP JSON Web Token Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/JSON_Web_Token_for_Java_Cheat_Sheet.html)
- [JWT Revocation Strategies](https://www.michal-drozd.com/en/blog/jwt-revocation-strategies/)
- [RFC 8725: JWT Best Current Practices](https://rfc-editor.org/rfc/rfc8725)

---

### CRITICAL-2: SECRET_KEY Management

**OWASP Category**: A04:2025 - Cryptographic Failures
**STRIDE**: Spoofing, Tampering
**CVSS Score**: 9.8 (Critical)

**Description**: JWT signing requires a secret key. Improper key management allows token forgery and complete authentication bypass.

**Impact**:
- Exposed secret key allows arbitrary token creation
- Weak keys can be brute-forced
- Hardcoded keys in source code are critical vulnerabilities
- Key rotation requires coordination

**Remediation**:

```python
# app/config.py - Key management
import os
import secrets

def get_jwt_secret_key() -> str:
    """
    Get JWT secret key from environment.

    Requirements:
    - Minimum 256 bits (32 bytes) of entropy for HS256
    - Loaded from environment variable (never hardcoded)
    - Must be set before application starts
    """
    secret_key = os.environ.get("JWT_SECRET_KEY")

    if not secret_key:
        raise ValueError(
            "JWT_SECRET_KEY environment variable must be set. "
            "Generate with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
        )

    # Verify minimum length (256 bits = 32 bytes = ~43 chars in base64)
    if len(secret_key) < 32:
        raise ValueError(
            "JWT_SECRET_KEY must be at least 32 characters. "
            f"Current length: {len(secret_key)}"
        )

    return secret_key

# Key rotation support
def get_jwt_keys() -> dict:
    """
    Support key rotation with multiple keys.

    Returns:
        {
            "current": "primary-key",
            "previous": "old-key"  # For validating tokens during rotation
        }
    """
    current_key = os.environ.get("JWT_SECRET_KEY")
    previous_key = os.environ.get("JWT_SECRET_KEY_PREVIOUS")

    keys = {"current": current_key}
    if previous_key:
        keys["previous"] = previous_key

    return keys

# Usage
def create_jwt(payload: dict) -> str:
    return jwt.encode(payload, get_jwt_secret_key(), algorithm="HS256")

def validate_jwt(token: str) -> dict | None:
    keys = get_jwt_keys()

    # Try current key first
    try:
        return jwt.decode(token, keys["current"], algorithms=["HS256"])
    except jwt.InvalidSignatureError:
        # Try previous key (during rotation)
        if "previous" in keys:
            try:
                return jwt.decode(token, keys["previous"], algorithms=["HS256"])
            except jwt.InvalidSignatureError:
                return None
        return None
```

**Environment Configuration**:

```bash
# .env (development)
JWT_SECRET_KEY=your-secret-key-minimum-32-characters-long

# .env.example (committed to repo)
JWT_SECRET_KEY=generate-with-python-secrets-token-urlsafe-32

# .gitignore
.env
.env.local
.env.production
*.pem
*.key
```

**Key Generation**:

```bash
# Generate secure key
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Output example: K7gNU3sdo-OL0wNhqoVWhr3g6s1xYv72ol_pe_Unols
```

**Key Rotation Procedure**:

1. Generate new key
2. Set `JWT_SECRET_KEY_PREVIOUS` = current `JWT_SECRET_KEY`
3. Set `JWT_SECRET_KEY` = new key
4. Restart application
5. Both keys valid during transition
6. After token expiration period, remove `JWT_SECRET_KEY_PREVIOUS`

**Reference**:
- [OWASP A04:2025 - Cryptographic Failures](https://owasp.org/Top10/A04_2025-Cryptographic_Failures/)
- [CWE-798: Use of Hard-coded Credentials](https://cwe.mitre.org/data/definitions/798.html)
- [RFC 8725: Strong Keys](https://rfc-editor.org/rfc/rfc8725)

---

### CRITICAL-3: Algorithm Confusion Vulnerability

**OWASP Category**: A05:2025 - Security Misconfiguration
**STRIDE**: Tampering
**CVSS Score**: 9.8 (Critical)

**Description**: JWT libraries that trust the `alg` header from the token are vulnerable to algorithm confusion attacks. An attacker can forge tokens by changing the algorithm header.

**Attack Vectors**:

1. **"none" Algorithm Attack**:
```python
# Attacker creates:
header = {"alg": "none", "typ": "JWT"}
payload = {"email": "admin@example.com", "exp": 9999999999}
# No signature - library may accept this!
forged_token = base64url(header) + "." + base64url(payload) + "."
```

2. **RS256 → HS256 Confusion**:
```python
# If server uses RS256 (asymmetric) but accepts HS256:
# Attacker can use public key as HMAC secret
# Since public key is known, they can forge signatures
```

**Remediation**:

```python
# app/auth.py - Secure JWT handling
import jwt
from typing import Optional
from datetime import datetime, timezone

# HARDCODED algorithm - never trust token header
JWT_ALGORITHM = "HS256"

def create_jwt_session(email: str, channel_token: str) -> str:
    """
    Create JWT session token.

    Security:
    - Algorithm hardcoded (not from token)
    - All claims validated
    - Strong secret key required
    """
    payload = {
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(days=30),
        "iat": datetime.now(timezone.utc),
        "channel_token": channel_token,
        "ver": get_token_version(email)
    }

    # Explicitly specify algorithm
    return jwt.encode(payload, get_jwt_secret_key(), algorithm=JWT_ALGORITHM)

def validate_jwt(token: str) -> Optional[dict]:
    """
    Validate JWT session token.

    Security:
    - Algorithm hardcoded (never from token)
    - Explicit rejection of "none" algorithm
    - All claims validated
    - Exception handling prevents bypass
    """
    if not token:
        return None

    try:
        # SECURITY: algorithms parameter forces algorithm verification
        # Library will reject token if alg header differs from allowed list
        payload = jwt.decode(
            token,
            get_jwt_secret_key(),
            algorithms=[JWT_ALGORITHM],  # ONLY allow our algorithm
            options={
                "verify_exp": True,
                "verify_iat": True,
                "require": ["exp", "iat", "email", "channel_token"]
            }
        )

        # Additional validation
        if not payload.get("email"):
            return None

        if not payload.get("channel_token"):
            return None

        # Check ALLOWED_EMAILS
        if payload["email"] not in get_allowed_emails():
            return None

        # Check token version
        current_version = get_token_version(payload["email"])
        if payload.get("ver", 1) != current_version:
            return None

        return payload

    except jwt.ExpiredSignatureError:
        logger.info("JWT expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid JWT: {e}")
        return None

def get_allowed_emails() -> set[str]:
    """Get allowed emails from environment."""
    emails = os.environ.get("ALLOWED_EMAILS", "")
    return set(email.strip().lower() for email in emails.split(",") if email.strip())

# Explicit "none" algorithm rejection (defense in depth)
def validate_jwt_with_none_check(token: str) -> Optional[dict]:
    """Validate with explicit none algorithm rejection."""
    try:
        # Check for "none" algorithm before decoding
        header = jwt.get_unverified_header(token)
        if header.get("alg", "").lower() == "none":
            logger.warning("Rejected JWT with 'none' algorithm")
            return None

        return validate_jwt(token)
    except Exception as e:
        logger.warning(f"JWT validation error: {e}")
        return None
```

**Testing for Vulnerability**:

```python
# tests/test_jwt_security.py
import jwt
import pytest

def test_none_algorithm_rejected():
    """Test that 'none' algorithm is rejected."""
    # Forge token with none algorithm
    header = {"alg": "none", "typ": "JWT"}
    payload = {"email": "test@example.com", "exp": 9999999999}
    forged = f"{base64url(header)}.{base64url(payload)}."

    result = validate_jwt(forged)
    assert result is None

def test_algorithm_confusion_rejected():
    """Test that algorithm confusion is prevented."""
    # Create token with HS256 but try RS256 verification
    token = create_jwt_session("test@example.com", "token123")

    # Attempt to decode with wrong algorithm
    with pytest.raises(jwt.InvalidAlgorithmError):
        jwt.decode(token, get_jwt_secret_key(), algorithms=["RS256"])
```

**Reference**:
- [OWASP A05:2025 - Security Misconfiguration](https://owasp.org/Top10/A05_2025-Security_Misconfiguration/)
- [JWT Algorithm None Attack](https://ofriperetz.dev/articles/the-jwt-algorithm-none-attack-the-vulnerability-in-1-line-of-code-d9g)
- [RFC 8725: Algorithm Verification](https://rfc-editor.org/rfc/rfc8725)

---

## High Findings (CVSS 7.0-8.9)

### HIGH-1: ALLOWED_EMAILS Implementation Risks

**OWASP Category**: A01:2025 - Broken Access Control
**STRIDE**: Elevation of Privilege
**CVSS Score**: 8.6 (High)

**Description**: The ALLOWED_EMAILS environment variable provides user-level revocation but introduces several security considerations that must be properly implemented.

**Impact**:
- Improper implementation may cache stale email lists
- Environment variable changes require server restart to take effect
- Timing attacks if validation is inconsistent across code paths
- Case sensitivity issues in email comparison

**Remediation**:

```python
# app/auth.py - Secure ALLOWED_EMAILS implementation
import os
from functools import lru_cache
from datetime import datetime, timezone, timedelta

class AllowedEmailsManager:
    """
    Manages allowed emails list with caching and validation.

    Security considerations:
    - Cached for performance, but refreshed periodically
    - Case-insensitive comparison
    - Validated on every request (no caching in JWT)
    """

    def __init__(self, cache_ttl_seconds: int = 60):
        self.cache_ttl = timedelta(seconds=cache_ttl_seconds)
        self._cache_time: datetime | None = None
        self._cached_emails: set[str] = set()

    def get_allowed_emails(self) -> set[str]:
        """
        Get allowed emails with caching.

        Returns:
            Set of allowed email addresses (lowercase)
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
            email.strip().lower()
            for email in emails_str.split(",")
            if email.strip()
        )

        self._cache_time = datetime.now(timezone.utc)

        logger.info(f"Refreshed ALLOWED_EMAILS cache: {len(self._cached_emails)} emails")

    def is_allowed(self, email: str) -> bool:
        """
        Check if email is allowed.

        Args:
            email: Email address to check

        Returns:
            True if email is in allowed list
        """
        if not email:
            return False

        # Case-insensitive comparison
        return email.strip().lower() in self.get_allowed_emails()

    def clear_cache(self):
        """Force cache refresh on next request."""
        self._cache_time = None

# Global instance
allowed_emails_manager = AllowedEmailsManager(cache_ttl_seconds=60)

# Usage in JWT validation
def validate_jwt(token: str) -> dict | None:
    """Validate JWT with ALLOWED_EMAILS check."""
    try:
        payload = jwt.decode(token, get_jwt_secret_key(), algorithms=["HS256"])

        # SECURITY: Check email on EVERY request (not cached in JWT)
        if not allowed_emails_manager.is_allowed(payload["email"]):
            logger.warning(f"Email not in ALLOWED_EMAILS: {payload['email']}")
            return None

        # Check token version
        current_version = get_token_version(payload["email"])
        if payload.get("ver", 1) != current_version:
            return None

        return payload

    except jwt.InvalidTokenError:
        return None

# Immediate revocation support
def revoke_user(email: str):
    """
    Immediately revoke user access.

    Two mechanisms:
    1. Remove from ALLOWED_EMAILS (immediate after cache refresh)
    2. Increment token version (immediate for all sessions)
    """
    # Increment token version (immediate)
    revoke_all_tokens(email)

    # Clear cache so next request picks up ALLOWED_EMAILS change
    allowed_emails_manager.clear_cache()
```

**Environment Configuration**:

```bash
# .env
ALLOWED_EMAILS=alice@example.com,bob@example.com,charlie@example.com

# .env.example
ALLOWED_EMAILS=user1@example.com,user2@example.com
```

**Validation Points**:

The ALLOWED_EMAILS must be checked at these points:

1. **Magic Link Request**: Reject if email not in list
2. **JWT Creation**: Double-check before issuing JWT
3. **JWT Validation**: Check on EVERY WebSocket connection and API request
4. **Channel Access**: Verify before joining user's private channel

```python
# All validation points

# 1. Magic Link Request
@app.route("/auth/request-magic-link", methods=["POST"])
async def request_magic_link():
    email = (await request.get_json()).get("email", "").strip().lower()

    if not allowed_emails_manager.is_allowed(email):
        return jsonify({"error": "Email not authorized"}), 403

    # Continue with magic link creation...

# 2. JWT Creation (magic link verification)
@app.route("/auth/verify")
async def verify_magic_link():
    token = request.args.get("token")
    magic_link = magic_link_manager.validate_token(token)

    if not magic_link:
        return redirect("/?error=invalid_token")

    # Double-check email before JWT creation
    if not allowed_emails_manager.is_allowed(magic_link.email):
        return redirect("/?error=unauthorized")

    jwt_token = create_jwt_session(magic_link.email, secrets.token_urlsafe(32))
    # ...

# 3. WebSocket Connection
@socketio.on("connect")
async def on_connect(sid, environ, auth):
    token = extract_jwt_from_cookie(environ)
    payload = validate_jwt(token)  # Includes ALLOWED_EMAILS check

    if not payload:
        return False

    # Continue with connection...

# 4. API Endpoints
@app.route("/api/messages", methods=["POST"])
async def send_message():
    token = extract_jwt_from_cookie(request.cookies)
    payload = validate_jwt(token)  # Includes ALLOWED_EMAILS check

    if not payload:
        return jsonify({"error": "Unauthorized"}), 401

    # Continue with message...
```

**Reference**:
- [OWASP A01:2025 - Broken Access Control](https://owasp.org/Top10/A01_2025-Broken_Access_Control/)
- [OWASP Access Control Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Access_Control_Cheat_Sheet.html)

---

### HIGH-2: Token Expiration Strategy

**OWASP Category**: A07:2025 - Authentication Failures
**STRIDE**: Spoofing
**CVSS Score**: 7.8 (High)

**Description**: Long-lived JWT tokens (30 days proposed) provide an extended window of vulnerability if tokens are stolen. Expiration strategy must balance security with user experience.

**Impact**:
- 30-day expiration = 30 days of vulnerability window
- Stolen token provides long-term access
- No automatic session cleanup
- User experience impact if expiration too short

**Current State**:
```python
# Current: 30-day expiration
payload = {
    "email": email,
    "exp": datetime.now(timezone.utc) + timedelta(days=30),
    ...
}
```

**Remediation Options**:

**Option A: Short Expiration + Refresh Tokens (Most Secure)**

```python
# app/auth.py
from datetime import datetime, timezone, timedelta

JWT_ACCESS_EXPIRATION = timedelta(minutes=15)
JWT_REFRESH_EXPIRATION = timedelta(days=30)

def create_token_pair(email: str) -> dict:
    """
    Create access token + refresh token pair.

    Access token: Short-lived (15 min), used for API calls
    Refresh token: Long-lived (30 days), stored server-side
    """
    channel_token = secrets.token_urlsafe(32)

    # Short-lived access token
    access_token = jwt.encode({
        "email": email,
        "exp": datetime.now(timezone.utc) + JWT_ACCESS_EXPIRATION,
        "iat": datetime.now(timezone.utc),
        "type": "access",
        "channel_token": channel_token,
        "ver": get_token_version(email)
    }, get_jwt_secret_key(), algorithm="HS256")

    # Long-lived refresh token (opaque, stored server-side)
    refresh_token = secrets.token_urlsafe(32)
    refresh_hash = hashlib.sha256(refresh_token.encode()).hexdigest()

    refresh_tokens[refresh_hash] = {
        "email": email,
        "created_at": datetime.now(timezone.utc),
        "expires_at": datetime.now(timezone.utc) + JWT_REFRESH_EXPIRATION,
        "channel_token": channel_token
    }

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_in": int(JWT_ACCESS_EXPIRATION.total_seconds())
    }

def refresh_access_token(refresh_token: str) -> dict | None:
    """Exchange refresh token for new access token."""
    refresh_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
    stored = refresh_tokens.get(refresh_hash)

    if not stored:
        return None

    if datetime.now(timezone.utc) > stored["expires_at"]:
        del refresh_tokens[refresh_hash]
        return None

    # Check ALLOWED_EMAILS
    if not allowed_emails_manager.is_allowed(stored["email"]):
        del refresh_tokens[refresh_hash]
        return None

    # Issue new access token
    return create_token_pair(stored["email"])

def revoke_refresh_token(refresh_token: str):
    """Revoke refresh token (logout)."""
    refresh_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
    refresh_tokens.pop(refresh_hash, None)
```

**Option B: Sliding Expiration (User Experience Balance)**

```python
# Keep 30-day max, but refresh on activity
JWT_MAX_LIFETIME = timedelta(days=30)
JWT_IDLE_TIMEOUT = timedelta(days=7)

def create_jwt_with_lifetime(email: str) -> str:
    """Create JWT with absolute and idle expiration."""
    return jwt.encode({
        "email": email,
        "exp": datetime.now(timezone.utc) + JWT_MAX_LIFETIME,
        "iat": datetime.now(timezone.utc),
        "last_activity": datetime.now(timezone.utc).isoformat(),
        ...
    }, get_jwt_secret_key(), algorithm="HS256")

# Note: Sliding expiration requires server-side tracking,
# which defeats stateless nature of JWT
# Better to use Option A for true statelessness
```

**Recommendation for I4-001**:

Use **Option A (Access + Refresh Tokens)** if state management is acceptable.
If strict statelessness required, use **30-day expiration with token version revocation**.

**Expiration Recommendations by Use Case**:

| Use Case | Access Token | Refresh Token | Notes |
|----------|-------------|---------------|-------|
| High-security app | 5-15 minutes | 24 hours | Bank, healthcare |
| Standard web app | 15-60 minutes | 7-30 days | Most applications |
| Development/internal | 1-4 hours | 30 days | Low risk |
| Service-to-service | 1 hour | N/A | Use API keys instead |

**Reference**:
- [OWASP A07:2025 - Authentication Failures](https://owasp.org/Top10/A07_2025-Identification_and_Authentication_Failures/)
- [OWASP Session Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)
- [JWT Best Practices - WorkOS](https://workos.com/blog/jwt-best-practices)

---

### HIGH-3: Channel Token Security

**OWASP Category**: A01:2025 - Broken Access Control
**STRIDE**: Elevation of Privilege
**CVSS Score**: 7.5 (High)

**Description**: The `channel_token` claim in the JWT allows clients to join user-specific channels. If channel tokens are predictable or can be forged, users could access other users' private channels.

**Impact**:
- Predictable channel tokens allow channel hijacking
- Token reuse across sessions enables session hijacking
- Insufficient token validation allows unauthorized channel access
- Token exposure in logs leaks access capability

**Remediation**:

```python
# app/auth.py - Secure channel token implementation
import secrets

def create_jwt_session(email: str) -> str:
    """
    Create JWT with secure channel token.

    Channel token security requirements:
    - Minimum 256 bits of entropy
    - Unique per session (not per user)
    - Cannot be predicted
    - Not exposed in logs
    """
    # Generate cryptographically secure channel token
    channel_token = secrets.token_urlsafe(32)  # 256 bits of entropy

    payload = {
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(days=30),
        "iat": datetime.now(timezone.utc),
        "channel_token": channel_token,  # Unique per session
        "ver": get_token_version(email)
    }

    return jwt.encode(payload, get_jwt_secret_key(), algorithm="HS256")

# app/__init__.py - WebSocket channel validation
@socketio.on("connect")
async def on_connect(sid: str, environ: dict, auth_data: dict | None) -> bool:
    """Handle WebSocket connection with channel token validation."""

    # Extract JWT from cookie
    cookies = environ.get("HTTP_COOKIE", "")
    token = extract_jwt_from_cookie(cookies)

    if not token:
        logger.warning(f"Rejecting connection {sid}: no JWT token")
        return False

    # Validate JWT
    payload = validate_jwt(token)
    if not payload:
        logger.warning(f"Rejecting connection {sid}: invalid JWT")
        return False

    email = payload["email"]
    channel_token = payload["channel_token"]

    # Check ALLOWED_EMAILS
    if not allowed_emails_manager.is_allowed(email):
        logger.warning(f"Rejecting connection {sid}: email not allowed: {email}")
        return False

    # Store connection info
    connected_clients[sid] = {
        "email": email,
        "channel_token": channel_token,  # Store for channel validation
        "ip": environ.get("REMOTE_ADDR"),
        "connected_at": datetime.now(timezone.utc)
    }

    # Join user's channel
    user_channel = f"user:{email}"
    await socketio_server.enter_room(sid, user_channel)

    logger.info(f"Client connected: {email} (total: {len(connected_clients)})")

    return True

# Channel access validation on message send
@socketio.on("message")
async def on_message(sid: str, data: dict) -> dict:
    """Handle message with channel validation."""

    client_info = connected_clients.get(sid)
    if not client_info:
        return {"error": "Not authenticated"}

    email = client_info["email"]
    channel_token = client_info["channel_token"]

    # Security: Validate that the message is being sent to the correct channel
    # (Prevents message injection into other users' channels)
    message = {
        "id": str(uuid.uuid4()),
        "user": email,
        "content": html.escape(data.get("content", "")),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    # Broadcast only to user's channel
    user_channel = f"user:{email}"
    await socketio_server.emit("message", message, room=user_channel)

    return {"status": "ok", "message_id": message["id"]}
```

**Channel Token Validation Matrix**:

| Action | Validations Required |
|--------|---------------------|
| WebSocket Connect | JWT valid + email in ALLOWED_EMAILS |
| Join Channel | JWT channel_token matches stored token |
| Send Message | Connection email matches channel |
| Receive Message | Only from joined channels |

**Security Properties**:

```python
# Security test cases
def test_channel_token_unpredictable():
    """Channel tokens must be cryptographically random."""
    token1 = create_jwt_session("user@example.com")
    token2 = create_jwt_session("user@example.com")

    payload1 = jwt.decode(token1, get_jwt_secret_key(), algorithms=["HS256"])
    payload2 = jwt.decode(token2, get_jwt_secret_key(), algorithms=["HS256"])

    # Each session gets unique channel token
    assert payload1["channel_token"] != payload2["channel_token"]

    # Token has sufficient entropy
    assert len(payload1["channel_token"]) >= 32

def test_cannot_join_other_user_channel():
    """User cannot join another user's channel."""
    # User A creates JWT
    jwt_a = create_jwt_session("alice@example.com")
    payload_a = jwt.decode(jwt_a, get_jwt_secret_key(), algorithms=["HS256"])

    # User B tries to join user A's channel
    jwt_b = create_jwt_session("bob@example.com")
    payload_b = jwt.decode(jwt_b, get_jwt_secret_key(), algorithms=["HS256"])

    # User B's JWT does not contain User A's channel token
    assert payload_b["channel_token"] != payload_a["channel_token"]
    assert payload_b["email"] != payload_a["email"]
```

**Reference**:
- [OWASP A01:2025 - Broken Access Control](https://owasp.org/Top10/A01_2025-Broken_Access_Control/)
- [Socket.IO Security](https://socket.io/docs/v4/security/)

---

## Medium Findings (CVSS 4.0-6.9)

### MEDIUM-1: Cookie Security Configuration

**OWASP Category**: A05:2025 - Security Misconfiguration
**STRIDE**: Tampering, Information Disclosure
**CVSS Score**: 6.1 (Medium)

**Description**: JWT stored in httpOnly cookie. Cookie security flags must be properly configured for production.

**Current State**:
```python
# Current implementation
response.set_cookie(
    "session_token",
    token,
    httponly=True,
    secure=False,  # DEVELOPMENT ONLY - must be True in production
    samesite="Strict",
    max_age=SESSION_TIMEOUT_DAYS * 24 * 3600,
)
```

**Remediation**:

```python
# app/config.py
import os

def get_cookie_settings() -> dict:
    """
    Get secure cookie settings based on environment.

    Production requirements:
    - secure=True (HTTPS only)
    - httponly=True (no JavaScript access)
    - samesite='Strict' or 'Lax' (CSRF protection)
    - domain set correctly
    """
    env = os.environ.get("ENV", "development")
    is_production = env == "production"

    return {
        "httponly": True,
        "secure": is_production,  # Must be True in production
        "samesite": "Strict",
        "max_age": 30 * 24 * 3600,  # 30 days
        "domain": os.environ.get("COOKIE_DOMAIN", None),  # Set in production
        "path": "/",
    }

# app/__init__.py
@app.route("/auth/verify")
async def verify_magic_link():
    # ... JWT creation ...

    jwt_token = create_jwt_session(magic_link.email, channel_token)

    response = redirect("/")
    response.set_cookie(
        "jwt_token",  # Note: rename from session_token for clarity
        jwt_token,
        **get_cookie_settings()
    )

    return response
```

**Production Checklist**:

```python
# Environment-based configuration
def validate_production_security():
    """Validate security settings for production deployment."""
    env = os.environ.get("ENV", "development")

    if env == "production":
        errors = []

        # HTTPS required
        if os.environ.get("FORCE_HTTPS", "false").lower() != "true":
            errors.append("FORCE_HTTPS must be 'true' in production")

        # Secure cookie required
        cookie_settings = get_cookie_settings()
        if not cookie_settings["secure"]:
            errors.append("Cookie 'secure' flag must be True in production")

        # JWT secret key must be strong
        if len(get_jwt_secret_key()) < 32:
            errors.append("JWT_SECRET_KEY must be at least 32 characters")

        # ALLOWED_EMAILS must be configured
        if not os.environ.get("ALLOWED_EMAILS"):
            errors.append("ALLOWED_EMAILS must be set in production")

        if errors:
            raise ValueError("Production security validation failed:\n" + "\n".join(errors))
```

**HSTS Header**:

```python
# Add HSTS for production
@app.after_request
async def add_security_headers(response):
    """Add security headers to all responses."""

    if os.environ.get("ENV") == "production":
        # HTTP Strict Transport Security
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

    # Content Security Policy
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' https://cdn.jsdelivr.net; "
        "connect-src 'self' wss: ws:; "
        "frame-ancestors 'none';"
    )

    # Other security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"

    return response
```

**Reference**:
- [OWASP A05:2025 - Security Misconfiguration](https://owasp.org/Top10/A05_2025-Security_Misconfiguration/)
- [OWASP Cookie Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html#cookies)

---

### MEDIUM-2: WebSocket Authentication Timing

**OWASP Category**: A07:2025 - Authentication Failures
**STRIDE**: Spoofing
**CVSS Score**: 5.9 (Medium)

**Description**: JWT validation occurs on WebSocket connection. Timing of validation relative to channel joining must be secure to prevent race conditions.

**Remediation**:

```python
# app/__init__.py - Secure WebSocket connection flow
@socketio.on("connect")
async def on_connect(sid: str, environ: dict, auth_data: dict | None) -> bool:
    """
    Secure WebSocket connection flow.

    Order of operations:
    1. Extract JWT from cookie
    2. Validate JWT (including ALLOWED_EMAILS)
    3. Store validated user info
    4. Join user's channel
    5. Broadcast connection

    Security: No channel operations before JWT validation.
    """
    # Step 1: Extract JWT
    cookies = environ.get("HTTP_COOKIE", "")
    jwt_token = extract_jwt_from_cookie(cookies)

    if not jwt_token:
        logger.warning(f"Connection rejected {sid}: no JWT")
        return False

    # Step 2: Validate JWT (includes ALLOWED_EMAILS check)
    payload = validate_jwt(jwt_token)

    if not payload:
        logger.warning(f"Connection rejected {sid}: invalid JWT")
        return False

    email = payload["email"]
    channel_token = payload["channel_token"]

    # Step 3: Store validated user info
    # SECURITY: Only store after successful validation
    connected_clients[sid] = {
        "email": email,
        "channel_token": channel_token,
        "ip": environ.get("REMOTE_ADDR"),
        "user_agent": environ.get("HTTP_USER_AGENT", ""),
        "connected_at": datetime.now(timezone.utc)
    }

    # Step 4: Join user's channel
    user_channel = f"user:{email}"
    await socketio_server.enter_room(sid, user_channel)

    # Step 5: Broadcast connection
    await socketio_server.emit("user_joined", {
        "user": email,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }, room=user_channel, skip_sid=sid)

    logger.info(f"Client connected: {email} (total: {len(connected_clients)})")

    return True
```

**Reference**:
- [OWASP A07:2025 - Authentication Failures](https://owasp.org/Top10/A07_2025-Identification_and_Authentication_Failures/)
- [Socket.IO Authentication](https://socket.io/docs/v4/middlewares/)

---

### MEDIUM-3: Stateless Session Trade-offs

**OWASP Category**: A07:2025 - Authentication Failures
**STRIDE**: Spoofing, Repudiation
**CVSS Score**: 5.5 (Medium)

**Description**: Migration from stateful sessions to stateless JWTs changes security properties. These trade-offs must be clearly documented and understood.

**Security Properties Comparison**:

| Property | In-Memory Sessions | JWT Sessions |
|----------|-------------------|--------------|
| Immediate Revocation | ✅ Yes | ❌ No (without version/denylist) |
| Server Restart Tolerance | ❌ Lost | ✅ Preserved |
| Horizontal Scaling | ❌ Requires sync | ✅ Natural |
| Session Storage | ❌ Required | ✅ Not required |
| Token Size | Small (~50 bytes) | Large (~500+ bytes) |
| Token Theft Impact | Session invalidatable | Valid until expiration |
| Audit Trail | ✅ Server-side logs | ⚠️ Requires additional tracking |
| "Logout All Devices" | ✅ Easy | ❌ Requires version strategy |

**Documented Trade-offs**:

```markdown
## JWT vs In-Memory Sessions: Security Trade-offs

### Gains
- **Server Restart Tolerance**: Sessions survive server restarts
- **Horizontal Scalability**: No session synchronization needed
- **Reduced Server Memory**: No in-memory session storage
- **Stateless Architecture**: Simpler infrastructure

### Losses
- **Immediate Revocation**: Cannot invalidate single token before expiration
- **Real-time Session Management**: Cannot view/modify active sessions
- **Granular Access Control**: All-or-nothing access (until token version)
- **Audit Trail**: Limited visibility into session usage

### Mitigations Implemented
1. Token version strategy for "revoke all" capability
2. ALLOWED_EMAILS validation on every request
3. Short expiration with refresh tokens (optional)
4. Comprehensive logging of JWT validation events

### Use Case Suitability
- ✅ Suitable: Internal tools, development, low-security applications
- ⚠️ Requires Review: Public-facing applications, financial data
- ❌ Not Suitable: High-security applications without additional controls
```

**Reference**:
- [OWASP A07:2025 - Authentication Failures](https://owasp.org/Top10/A07_2025-Identification_and_Authentication_Failures/)
- [JWT Best Practices - WorkOS](https://workos.com/blog/jwt-best-practices)

---

## Low Findings (CVSS 0.1-3.9)

### LOW-1: JWT Token Size Impact

**OWASP Category**: A06:2025 - Insecure Design
**STRIDE**: Denial of Service
**CVSS Score**: 3.1 (Low)

**Description**: JWT tokens are larger than opaque session tokens (500+ bytes vs 50 bytes). This impacts bandwidth and storage.

**Impact**:
- Increased bandwidth on every request
- Cookie size limits (4KB)
- WebSocket message overhead

**Remediation**:

```python
# Minimize JWT size
def create_compact_jwt(email: str, channel_token: str) -> str:
    """Create compact JWT with minimal claims."""
    payload = {
        "email": email,           # Essential
        "exp": ...,               # Essential (automatic)
        "iat": ...,               # Essential (automatic)
        "ct": channel_token,       # Abbreviated claim names
        "v": get_token_version(email)  # Abbreviated
    }
    return jwt.encode(payload, get_jwt_secret_key(), algorithm="HS256")

# For large payloads, consider reference tokens
def create_reference_jwt(email: str) -> str:
    """Create minimal JWT that references server-side data."""
    # JWT only contains essential claims
    payload = {
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(days=30),
        "ref": secrets.token_urlsafe(16)  # Reference to server-side data
    }
    return jwt.encode(payload, get_jwt_secret_key(), algorithm="HS256")

# Server-side storage for reference token
jwt_references = {}  # {ref: {channel_token: ..., other_data: ...}}
```

**Reference**:
- [OWASP A06:2025 - Insecure Design](https://owasp.org/Top10/A06_2025-Insecure_Design/)

---

### LOW-2: Magic Link Token Exposure

**OWASP Category**: A05:2025 - Security Misconfiguration
**STRIDE**: Information Disclosure
**CVSS Score**: 2.5 (Low)

**Description**: Magic links are logged to console in development mode. This is intentional but must be disabled in production.

**Current State**:
```python
# Current: Magic links logged to console
print(f"\n=== MAGIC LINK ===")
print(f"To: {email}")
print(f"Link: {magic_link_url}")
print(f"==================\n")
```

**Remediation**:

```python
# app/email.py
import os

class EmailSender(ABC):
    @abstractmethod
    async def send_magic_link(self, email: str, magic_link_url: str) -> bool:
        pass

class ConsoleEmailSender(EmailSender):
    """Development-only email sender that logs magic links."""

    async def send_magic_link(self, email: str, magic_link_url: str) -> bool:
        """Log magic link to console (DEVELOPMENT ONLY)."""
        if os.environ.get("ENV") == "production":
            raise RuntimeError("ConsoleEmailSender must not be used in production")

        # Development mode - log magic link
        print(f"\n=== MAGIC LINK (Development) ===")
        print(f"To: {email}")
        print(f"Link: {magic_link_url}")
        print(f"=================================\n")
        return True

class SendGridEmailSender(EmailSender):
    """Production email sender using SendGrid."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def send_magic_link(self, email: str, magic_link_url: str) -> bool:
        """Send magic link email via SendGrid."""
        # SendGrid API implementation
        ...

# Factory
def get_email_sender() -> EmailSender:
    sender_type = os.environ.get("EMAIL_SENDER", "console")

    if sender_type == "console":
        if os.environ.get("ENV") == "production":
            raise ValueError("Console email sender not allowed in production")
        return ConsoleEmailSender()

    if sender_type == "sendgrid":
        api_key = os.environ.get("SENDGRID_API_KEY")
        if not api_key:
            raise ValueError("SENDGRID_API_KEY must be set")
        return SendGridEmailSender(api_key)

    raise ValueError(f"Unknown EMAIL_SENDER: {sender_type}")
```

**Reference**:
- [OWASP A05:2025 - Security Misconfiguration](https://owasp.org/Top10/A05_2025-Security_Misconfiguration/)

---

## Recommendations

### Must Implement Before I4-001

| ID | Finding | Action |
|----|---------|--------|
| CRITICAL-1 | Token revocation | Implement token version strategy |
| CRITICAL-2 | SECRET_KEY management | Use environment variable, minimum 32 characters |
| CRITICAL-3 | Algorithm confusion | Hardcode HS256, reject "none" algorithm |
| HIGH-1 | ALLOWED_EMAILS validation | Validate on every request, cache with TTL |

### Should Implement for I4-001

| ID | Finding | Action |
|----|---------|--------|
| HIGH-2 | Token expiration | Consider access + refresh tokens |
| HIGH-3 | Channel token security | Generate unique token per session |
| MEDIUM-1 | Cookie security | Configure secure=True for production |
| MEDIUM-2 | WebSocket timing | Validate before channel operations |

### Document for Future Iterations

| ID | Finding | Action |
|----|---------|--------|
| MEDIUM-3 | Stateless trade-offs | Document security properties clearly |
| LOW-1 | Token size | Consider reference tokens for large payloads |
| LOW-2 | Magic link exposure | Ensure console sender disabled in production |

---

## Positive Security Observations

The proposed JWT implementation includes several positive security practices:

1. **Cryptographically Secure Tokens**: Using `secrets.token_urlsafe(32)` for channel tokens provides 256 bits of entropy.

2. **httpOnly Cookies**: JWT stored in httpOnly cookie prevents JavaScript access (XSS protection).

3. **SameSite=Strict**: CSRF protection through strict SameSite cookie attribute.

4. **ALLOWED_EMAILS Mechanism**: Provides user-level access control and immediate revocation capability.

5. **Unique Channel Tokens**: Each session gets unique channel token, preventing cross-session channel access.

6. **WebSocket Authentication**: JWT validated on every WebSocket connection attempt.

---

## Security Testing Requirements

Before marking I4-001 as complete, perform the following security tests:

### JWT Security Tests

- [ ] Verify JWT algorithm hardcoded (cannot be changed via header)
- [ ] Test "none" algorithm rejection
- [ ] Test expired JWT rejection
- [ ] Test JWT with missing claims rejection
- [ ] Test JWT with invalid signature rejection
- [ ] Verify ALLOWED_EMAILS checked on every request
- [ ] Test token version revocation
- [ ] Test email removal from ALLOWED_EMAILS revokes access

### Token Expiration Tests

- [ ] Test JWT expiration enforcement
- [ ] Test token version mismatch handling
- [ ] Test maximum session lifetime

### WebSocket Security Tests

- [ ] Test connection without JWT rejection
- [ ] Test connection with invalid JWT rejection
- [ ] Test connection with expired JWT rejection
- [ ] Test connection with email not in ALLOWED_EMAILS rejection
- [ ] Test channel isolation (User A cannot join User B's channel)
- [ ] Test channel token validation

### Channel Security Tests

- [ ] Test unique channel token per session
- [ ] Test channel token cannot be predicted
- [ ] Test messages only delivered to correct channel

### Environment Security Tests

- [ ] Verify SECRET_KEY loaded from environment
- [ ] Verify SECRET_KEY minimum length enforcement
- [ ] Test application startup without SECRET_KEY (should fail)
- [ ] Test ALLOWED_EMAILS parsing and validation
- [ ] Verify cookie secure flag in production mode

---

## Conclusion

The JWT session implementation for I4-001 introduces significant architectural changes with important security implications. The primary concern is the inability to immediately revoke individual JWT tokens, which must be mitigated through token version strategy and ALLOWED_EMAILS validation.

**Risk Assessment**: **MEDIUM-HIGH**

The implementation can be made secure with the recommended mitigations:

1. **Implement token version strategy** for immediate "revoke all" capability
2. **Validate ALLOWED_EMAILS on every request** for user-level access control
3. **Use strong SECRET_KEY management** with environment variables
4. **Hardcode JWT algorithm** to prevent confusion attacks
5. **Generate unique channel tokens** per session

**Acceptable for Development**: Yes, with mitigations implemented.

**Acceptable for Production**: Yes, with all critical and high findings addressed.

---

## References

- [OWASP Top 10:2025](https://owasp.org/Top10/)
- [OWASP A01:2025 - Broken Access Control](https://owasp.org/Top10/A01_2025-Broken_Access_Control/)
- [OWASP A04:2025 - Cryptographic Failures](https://owasp.org/Top10/A04_2025-Cryptographic_Failures/)
- [OWASP A05:2025 - Security Misconfiguration](https://owasp.org/Top10/A05_2025-Security_Misconfiguration/)
- [OWASP A07:2025 - Authentication Failures](https://owasp.org/Top10/A07_2025-Identification_and_Authentication_Failures/)
- [OWASP JSON Web Token Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/JSON_Web_Token_for_Java_Cheat_Sheet.html)
- [OWASP Session Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)
- [OWASP WebSocket Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/WebSocket_Security_Cheat_Sheet.html)
- [RFC 8725: JWT Best Current Practices](https://rfc-editor.org/rfc/rfc8725)
- [JWT Revocation Strategies](https://www.michal-drozd.com/en/blog/jwt-revocation-strategies/)
- [JWT Best Practices - WorkOS](https://workos.com/blog/jwt-best-practices)
- [JWT Algorithm None Attack](https://ofriperetz.dev/articles/the-jwt-algorithm-none-attack-the-vulnerability-in-1-line-of-code-d9g)
- [NIST SP 800-63B Digital Identity Guidelines](https://pages.nist.gov/800-63-3/sp800-63b.html)
- [CWE-798: Use of Hard-coded Credentials](https://cwe.mitre.org/data/definitions/798.html)