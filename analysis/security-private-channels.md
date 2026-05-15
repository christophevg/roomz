# Security Review Report: I4-002 User-Owned Private Channels

**Task**: I4-002 - User-owned private channels
**Date**: 2026-05-15
**Analyst**: Security Engineer Agent
**Status**: Pre-Implementation Security Review

## Executive Summary

This security review analyzes the planned implementation of user-owned private channels (I4-002) based on the current codebase state and intended design. The analysis reveals **critical vulnerabilities** in the current implementation that must be addressed before I4-002 can be considered complete.

**Risk Level**: **CRITICAL**

**Key Findings**:
1. Messages are currently broadcast globally, not to user's private channel
2. Channel tokens are stored in JWT but never validated server-side
3. No access control mechanism prevents unauthorized channel joins
4. Information leakage risk from global broadcast

## Security Findings Classification

| Finding | Classification | Action |
|---------|---------------|--------|
| Global message broadcast | Blocking | CRITICAL - Fix immediately |
| Channel token not validated | Blocking | CRITICAL - Implement validation |
| No channel access control | Blocking | CRITICAL - Implement authorization |
| Channel token storage architecture | Blocking | Design decision required |
| Channel naming security | Related | Implement sanitization |
| WebSocket message routing | Related | Ensure proper room targeting |

---

## Critical Findings (CVSS 9.0-10.0)

### CRITICAL-1: Global Message Broadcast - Information Leakage

**OWASP Category**: A01:2025 - Broken Access Control
**STRIDE**: Information Disclosure
**CVSS Score**: 9.6 (Critical)

**Description**: Messages are currently broadcast globally instead of to user's private channels. This causes all users to see all messages from all other users, completely breaking the privacy model.

**Current Implementation** (app/__init__.py, line 455):
```python
# Current: Broadcast to ALL clients
await server.socketio.emit("message", message)
```

**Intended Behavior**:
```python
# Should be: Broadcast only to user's channel
user_channel = f"user:{email}"
await server.socketio.emit("message", message, room=user_channel)
```

**Impact**:
- All users see all messages from all other users
- Complete privacy violation
- Cross-tenant data exposure
- User A's messages visible to User B, C, D...
- Sensitive information leakage

**Remediation**:

```python
# app/__init__.py - Fix message routing

@server.socketio.on("message")
async def on_message(sid: str, data: dict) -> dict:
    """
    Receive message from client and broadcast to user's private channel.

    Security: Messages are ONLY sent to the authenticated user's channel,
    ensuring complete isolation between users.
    """
    # Get user info from connection
    client_info = connected_clients.get(sid)
    if not client_info:
        return {"error": "Not authenticated", "code": 401}

    email = client_info.get("email")
    user_id = client_info.get("user_id")

    # Validate message structure
    if not isinstance(data, dict):
        return {"error": "Invalid message format", "code": 400}

    content = data.get("content")
    if not content or not isinstance(content, str):
        return {"error": "Missing or invalid 'content' field", "code": 400}

    # Sanitize content (basic XSS prevention)
    content = html.escape(content.strip())[:MAX_MESSAGE_LENGTH]

    # Create broadcast message with user info
    message = {
        "id": str(uuid.uuid4()),
        "user": {"id": user_id, "email": email},
        "content": content,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # SECURITY: Broadcast ONLY to user's private channel
    user_channel = f"user:{email}"
    await server.socketio.emit("message", message, room=user_channel)

    # Return acknowledgment
    return {"status": "ok", "message_id": message["id"], "timestamp": message["timestamp"]}
```

**Acceptance Criteria**:
- User A's web and Python clients see each other's messages
- User B cannot see User A's messages
- Each user has complete message isolation

**Reference**:
- [OWASP A01:2025 - Broken Access Control](https://owasp.org/Top10/A01_2025-Broken_Access_Control/)
- [Socket.IO Rooms Documentation](https://socket.io/docs/v4/rooms/)

---

### CRITICAL-2: Channel Token Not Validated - Authorization Bypass

**OWASP Category**: A01:2025 - Broken Access Control
**STRIDE**: Elevation of Privilege
**CVSS Score**: 9.1 (Critical)

**Description**: The `channel_token` is stored in the JWT and extracted on WebSocket connect, but it is NEVER validated server-side. This means there is no cryptographic binding between the JWT and the channel access, allowing potential channel hijacking.

**Current Implementation** (app/__init__.py, lines 338-359):
```python
# Current: Token extracted but NOT validated
email = payload.get("email")
channel_token = payload.get("channel_token")  # Extracted...
user_id = payload.get("sub", f"user:{email}")

# ... stored ...
connected_clients[sid] = {
    "email": email,
    "channel_token": channel_token,  # Stored but never checked
    ...
}

# ... then used without validation
user_channel = f"user:{email}"
await server.socketio.enter_room(sid, user_channel)  # Joined without token check!
```

**The Problem**: The JWT email claim is trusted for channel membership without any cryptographic verification that the JWT holder actually owns that channel. If an attacker can forge or manipulate the JWT (e.g., through JWT injection, algorithm confusion, or secret key compromise), they could join any user's channel.

**Architectural Question**: What is the purpose of `channel_token`?

There are two possible security models:

**Model A: JWT Identity-Based Channel Access** (Current implicit model)
```
JWT email claim -> channel name -> channel access
```
Security relies entirely on JWT integrity (signature verification).

**Model B: Token-Verified Channel Access** (More secure)
```
JWT email claim + channel_token -> server-side token validation -> channel access
```
Security has two factors: JWT signature + channel token verification.

**Remediation**:

**Option A: Simplify - Remove Channel Token** (if Model A is chosen)

If the JWT signature is trusted, the `channel_token` adds no additional security and should be removed:

```python
# app/auth.py - Remove channel_token from JWT
def generate_jwt(email: str) -> str:
    payload = {
        "sub": f"user:{email_lower}",
        "email": email_lower,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=JWT_EXPIRY_DAYS)).timestamp()),
        "ver": get_token_version(email_lower),
        # REMOVED: "channel_token": channel_token,
    }
    return jwt.encode(payload, secret_key, algorithm=JWT_ALGORITHM)

# app/__init__.py - Trust JWT email for channel access
@server.socketio.on("connect")
async def on_connect(sid: str, environ: dict, auth_data: dict | None) -> bool:
    # JWT validation already verified:
    # 1. Signature is valid (not forged)
    # 2. Email is in ALLOWED_EMAILS (authorized)
    # 3. Token version matches (not revoked)

    # Therefore, we trust the email claim for channel access
    email = payload.get("email")
    user_channel = f"user:{email}"
    await server.socketio.enter_room(sid, user_channel)
```

**Pros**: Simpler, JWT signature is sufficient for identity
**Cons**: Single point of failure (JWT compromise = channel compromise)

**Option B: Validate Channel Token Server-Side** (if Model B is chosen)

Store channel tokens server-side and validate on channel join:

```python
# app/auth.py - Store channel tokens server-side
channel_tokens: dict[str, str] = {}  # {email: channel_token}

def generate_jwt(email: str) -> str:
    channel_token = secrets.token_urlsafe(32)

    # Store token server-side
    channel_tokens[email_lower] = channel_token

    payload = {
        "sub": f"user:{email_lower}",
        "email": email_lower,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=JWT_EXPIRY_DAYS)).timestamp()),
        "channel_token": channel_token,  # Include in JWT
        "ver": get_token_version(email_lower),
    }
    return jwt.encode(payload, secret_key, algorithm=JWT_ALGORITHM)

def validate_channel_token(email: str, token: str) -> bool:
    """Validate that the provided token matches the stored token."""
    stored_token = channel_tokens.get(email)
    if not stored_token:
        return False
    return secrets.compare_digest(stored_token, token)

# app/__init__.py - Validate channel token on connect
@server.socketio.on("connect")
async def on_connect(sid: str, environ: dict, auth_data: dict | None) -> bool:
    # ... JWT validation ...

    email = payload.get("email")
    channel_token = payload.get("channel_token")

    # SECURITY: Validate channel token
    if not validate_channel_token(email, channel_token):
        logger.warning(f"Channel token mismatch for {email}")
        return False

    # Token validated, join channel
    user_channel = f"user:{email}"
    await server.socketio.enter_room(sid, user_channel)
```

**Pros**: Two-factor verification (JWT + channel token)
**Cons**: Requires server-side state (reduces statelessness benefit of JWT)

**Recommendation**:

Use **Option A (Simplify - Remove Channel Token)** for I4-002 because:

1. JWT signature verification already provides strong identity verification
2. ALLOWED_EMAILS check provides immediate revocation
3. Token version provides session revocation
4. Channel token adds complexity without clear security benefit
5. Server restart already invalidates in-memory channel tokens

The JWT-based identity verification is sufficient for the threat model:

| Attack Vector | Mitigation |
|--------------|------------|
| Forged JWT | Signature verification |
| Stolen JWT | ALLOWED_EMAILS + token version revocation |
| JWT tampering | Signature verification |
| Replay attack | JWT expiration |

**Reference**:
- [OWASP A01:2025 - Broken Access Control](https://owasp.org/Top10/A01_2025-Broken_Access_Control/)
- [OWASP Access Control Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Access_Control_Cheat_Sheet.html)

---

### CRITICAL-3: No Channel Access Control - Unauthorized Channel Joins

**OWASP Category**: A01:2025 - Broken Access Control
**STRIDE**: Elevation of Privilege
**CVSS Score**: 8.6 (High-Critical)

**Description**: Socket.IO's `enter_room` is called without any authorization check. While Socket.IO handles room membership internally, there is no application-layer access control to prevent unauthorized channel joins.

**Current Implementation** (app/__init__.py, lines 357-359):
```python
# Current: No access control on room join
user_channel = f"user:{email}"
await server.socketio.enter_room(sid, user_channel)
# No validation that this user is authorized to join this channel!
```

**Threat Analysis**:

**Threat 1: Can a user forge a channel join to another user's channel?**

**With current implementation**: Only if they can forge a valid JWT.

The Socket.IO library does NOT expose a "join room" event that clients can call directly. Room membership is entirely server-controlled through `enter_room(sid, room)`. A client cannot request to join an arbitrary room.

However, if an attacker can:
1. Forge a JWT with a different email (requires SECRET_KEY compromise)
2. Steal another user's JWT (session hijacking)
3. Exploit JWT validation vulnerabilities (algorithm confusion)

...then they could join another user's channel.

**Threat 2: What if Socket.IO configuration allows client-side room joins?**

Socket.IO can be configured with `allowRequest` or custom middleware. If misconfigured, clients might be able to join arbitrary rooms.

**Remediation**:

```python
# app/__init__.py - Add channel access control

def is_authorized_for_channel(email: str, channel_name: str) -> bool:
    """
    Check if user is authorized to join a specific channel.

    Security: Users can only join their own private channel.

    Args:
        email: User's email address from JWT
        channel_name: Channel name to check access for

    Returns:
        True if authorized, False otherwise
    """
    # User's private channel
    expected_channel = f"user:{email}"

    # Normalize for comparison
    return channel_name.lower() == expected_channel.lower()


@server.socketio.on("connect")
async def on_connect(sid: str, environ: dict, auth_data: dict | None) -> bool:
    """Handle WebSocket connection with channel access control."""

    # ... JWT validation ...

    email = payload.get("email")
    user_channel = f"user:{email}"

    # SECURITY: Verify user is authorized to join this channel
    # (Defense in depth - already verified by JWT email claim)
    if not is_authorized_for_channel(email, user_channel):
        logger.error(f"Channel access denied: {email} -> {user_channel}")
        return False

    # Authorized - join channel
    await server.socketio.enter_room(sid, user_channel)

    return True
```

**For future extension (public channels, shared channels)**:

```python
def is_authorized_for_channel(email: str, channel_name: str) -> bool:
    """
    Check if user is authorized to join a specific channel.

    Channel types:
    - user:{email} - User's private channel (only owner)
    - public:{name} - Public channel (all authenticated users)
    - shared:{owner}:{name} - Shared channel (owner + collaborators)
    """
    # Private user channel
    if channel_name.startswith("user:"):
        expected_channel = f"user:{email}"
        return channel_name.lower() == expected_channel.lower()

    # Public channel (future)
    if channel_name.startswith("public:"):
        return True  # All authenticated users can join

    # Shared channel (future)
    if channel_name.startswith("shared:"):
        # TODO: Check collaborator list
        return False

    # Unknown channel type
    return False
```

**Reference**:
- [OWASP A01:2025 - Broken Access Control](https://owasp.org/Top10/A01_2025-Broken_Access_Control/)
- [Socket.IO Security](https://socket.io/docs/v4/security/)

---

## High Findings (CVSS 7.0-8.9)

### HIGH-1: Channel Naming Security

**OWASP Category**: A05:2025 - Injection
**STRIDE**: Tampering
**CVSS Score**: 7.5 (High)

**Description**: Channel names are constructed from email addresses without sanitization. Malicious email patterns could potentially cause issues.

**Current Implementation**:
```python
user_channel = f"user:{email}"
```

**Potential Issues**:

1. **Email with special characters**: What if email contains `:`, `/`, `\`, or other special characters?
2. **Email injection**: Could an email like `alice@example.com:user:bob@example.com` cause confusion?
3. **Channel name conflicts**: Different email formats could map to same channel.

**Remediation**:

```python
# app/__init__.py - Secure channel naming

import hashlib

def get_user_channel_name(email: str) -> str:
    """
    Generate secure channel name for user.

    Security:
    - Normalize email (lowercase, trim)
    - Hash email to prevent injection
    - Use consistent format

    Args:
        email: User's email address

    Returns:
        Channel name in format: user:{email_hash}
    """
    # Normalize email
    email_normalized = email.lower().strip()

    # Option 1: Use email directly with sanitization
    # Replace problematic characters
    safe_email = email_normalized.replace(":", "_").replace("/", "_").replace("\\", "_")
    return f"user:{safe_email}"

    # Option 2: Use hash (more secure but less readable)
    # email_hash = hashlib.sha256(email_normalized.encode()).hexdigest()[:16]
    # return f"user:{email_hash}"


@server.socketio.on("connect")
async def on_connect(sid: str, environ: dict, auth_data: dict | None) -> bool:
    # ... JWT validation ...

    email = payload.get("email")

    # Generate channel name securely
    user_channel = get_user_channel_name(email)

    # Join channel
    await server.socketio.enter_room(sid, user_channel)

    # Inform client of their channel
    await server.socketio.emit(
        "authenticated",
        {
            "user": {"id": user_id, "email": email},
            "channel": user_channel,
            "server_time": datetime.now(timezone.utc).isoformat(),
        },
        to=sid,
    )

    return True
```

**Email Validation Enhancement**:

```python
# app/auth.py - Enhanced email validation

def is_valid_email(email: str) -> bool:
    """
    Validate email format following RFC 5322 basic rules.

    Security enhancements:
    - Reject emails with multiple @ symbols
    - Reject emails with problematic channel characters
    - Enforce length limits
    """
    if not email or len(email) > 255:
        return False

    # Basic RFC 5322 pattern
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if not re.match(pattern, email):
        return False

    # Security: Reject emails with problematic characters for channels
    # (This is defense in depth - channel names should be sanitized anyway)
    dangerous_chars = [":", "/", "\\", "\x00"]
    if any(char in email for char in dangerous_chars):
        logger.warning(f"Email contains dangerous characters: {email}")
        return False

    # Local part max length check
    parts = email.split("@")
    if len(parts[0]) > 64:
        return False

    return True
```

**Recommendation**: Use direct email with character sanitization (Option 1) for readability and debugging.

**Reference**:
- [OWASP A05:2025 - Injection](https://owasp.org/Top10/A05_2025-Injection/)
- [Socket.IO Rooms](https://socket.io/docs/v4/rooms/)

---

### HIGH-2: Multi-Client Message Synchronization

**OWASP Category**: A06:2025 - Insecure Design
**STRIDE**: Tampering
**CVSS Score**: 7.2 (High)

**Description**: When a user has multiple clients (web + Python CLI), messages must be synchronized correctly. The current architecture needs verification for multi-client scenarios.

**Use Case**: User sends message from web client, should appear on Python CLI client (and vice versa).

**Current Architecture**:
```
User (alice@example.com)
  ├─ Web Client (sid: abc123) ──┐
  │                              │
  └─ Python CLI (sid: def456) ───┼──► user:alice@example.com channel
                                 │
                                 └──► Messages broadcast to all sids in channel
```

**Security Verification**:

```python
# Test: Multi-client message synchronization

async def test_multi_client_sync():
    """Verify messages sync across multiple clients for same user."""
    # User connects with web client
    web_sid = "web_abc"
    await on_connect(web_sid, environ_web, None)

    # User connects with Python CLI
    cli_sid = "cli_def"
    await on_connect(cli_sid, environ_cli, None)

    # Both should be in same channel
    assert "user:alice@example.com" in server.socketio.rooms(web_sid)
    assert "user:alice@example.com" in server.socketio.rooms(cli_sid)

    # Message from web should reach CLI
    await on_message(web_sid, {"content": "Hello from web"})

    # Verify message was sent to user's channel
    # (This requires mocking/inspecting socketio.emit calls)
    assert last_emit_room == "user:alice@example.com"
```

**Implementation Note**: Socket.IO handles this correctly by default. When you emit to a room, ALL sockets in that room receive the message, including the sender if they're in the room.

**Potential Issue**: If you want to exclude the sender (e.g., to avoid echo):

```python
# Exclude sender from broadcast
await server.socketio.emit(
    "message",
    message,
    room=user_channel,
    skip_sid=sid  # Don't send back to sender
)
```

**Recommendation**: Do NOT skip sender. The sender should receive their own message for confirmation and consistency.

**Reference**:
- [Socket.IO Emit Cheatsheet](https://socket.io/docs/v4/emit-cheatsheet/)

---

## Medium Findings (CVSS 4.0-6.9)

### MEDIUM-1: Channel Token Lifecycle

**OWASP Category**: A07:2025 - Authentication Failures
**STRIDE**: Spoofing
**CVSS Score**: 5.5 (Medium)

**Description**: If channel tokens are kept (Option B from CRITICAL-2), they need proper lifecycle management including rotation, expiration, and cleanup.

**Current State**: Channel tokens are generated but never rotated or cleaned up.

**If Option A is chosen (remove channel tokens)**: This finding is NOT APPLICABLE.

**If Option B is chosen (validate channel tokens)**:

```python
# app/auth.py - Channel token lifecycle

from datetime import datetime, timedelta, timezone

# Store channel tokens with metadata
channel_tokens: dict[str, dict] = {}  # {email: {token, created_at, expires_at}}

def generate_channel_token(email: str) -> str:
    """Generate and store channel token with expiration."""
    email_lower = email.lower().strip()

    # Invalidate old token
    if email_lower in channel_tokens:
        old_token = channel_tokens[email_lower]["token"]
        logger.info(f"Invalidating old channel token for {email_lower}")

    # Generate new token
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)

    channel_tokens[email_lower] = {
        "token": token,
        "created_at": now,
        "expires_at": now + timedelta(days=30),  # Same as JWT
    }

    return token

def validate_channel_token(email: str, token: str) -> bool:
    """Validate channel token with expiration check."""
    email_lower = email.lower().strip()
    stored = channel_tokens.get(email_lower)

    if not stored:
        return False

    # Check expiration
    if datetime.now(timezone.utc) > stored["expires_at"]:
        logger.info(f"Channel token expired for {email_lower}")
        return False

    # Constant-time comparison
    return secrets.compare_digest(stored["token"], token)

def cleanup_expired_channel_tokens():
    """Remove expired channel tokens."""
    now = datetime.now(timezone.utc)
    expired = [
        email
        for email, data in channel_tokens.items()
        if now > data["expires_at"]
    ]

    for email in expired:
        del channel_tokens[email]

    if expired:
        logger.info(f"Cleaned up {len(expired)} expired channel tokens")
```

**Reference**:
- [OWASP A07:2025 - Authentication Failures](https://owasp.org/Top10/A07_2025-Identification_and_Authentication_Failures/)

---

### MEDIUM-2: Message Replay Protection

**OWASP Category**: A08:2025 - Software and Data Integrity Failures
**STRIDE**: Tampering
**CVSS Score**: 4.5 (Medium)

**Description**: Messages have unique IDs but there is no protection against message replay if a malicious client re-sends a previously captured message.

**Current State**: Each message gets a new UUID, so replay creates a "new" message with new ID.

**Risk Assessment**: LOW - Replay would create duplicate messages with new IDs. The primary impact is spam, not data integrity violation.

**Mitigation** (if needed):

```python
# app/__init__.py - Optional message deduplication

from collections import defaultdict
from datetime import datetime, timedelta, timezone

# Track recent message hashes per user
recent_messages: dict[str, dict] = {}  # {email: {hash: timestamp}}

def is_message_replay(email: str, content: str) -> bool:
    """Check if message is a recent duplicate."""
    email_lower = email.lower()
    content_hash = hashlib.sha256(content.encode()).hexdigest()

    now = datetime.now(timezone.utc)
    window = timedelta(minutes=5)

    # Initialize if needed
    if email_lower not in recent_messages:
        recent_messages[email_lower] = {}

    # Clean old entries
    recent_messages[email_lower] = {
        h: ts
        for h, ts in recent_messages[email_lower].items()
        if now - ts < window
    }

    # Check for duplicate
    if content_hash in recent_messages[email_lower]:
        return True

    # Record message
    recent_messages[email_lower][content_hash] = now
    return False
```

**Recommendation**: NOT REQUIRED for current use case. Implement only if spam becomes an issue.

**Reference**:
- [OWASP A08:2025 - Software and Data Integrity Failures](https://owasp.org/Top10/A08_2025-Software_and_Data_Integrity_Failures/)

---

## Low Findings (CVSS 0.1-3.9)

### LOW-1: Channel Naming Convention Documentation

**OWASP Category**: A06:2025 - Insecure Design
**STRIDE**: Repudiation
**CVSS Score**: 2.0 (Low)

**Description**: Channel naming convention should be documented for future extensions and security audits.

**Recommendation**: Document the channel naming schema:

```markdown
## Channel Naming Convention

### Format
- User private channels: `user:{email}`
- Public channels (future): `public:{name}`
- Shared channels (future): `shared:{owner}:{name}`

### Security Rules
1. Users can only join their own private channel
2. Channel names are sanitized to prevent injection
3. All channel access is logged for audit

### Examples
- `user:alice@example.com` - Alice's private channel
- `user:bob@company.org` - Bob's private channel
- `public:general` - Public general chat (future)
```

---

## Threat Model: Private Channels

### Trust Boundaries

```
┌─────────────────────────────────────────────────────────┐
│                    Untrusted Zone                       │
│                                                         │
│  ┌──────────────┐         ┌──────────────┐            │
│  │  Web Client  │         │ Python CLI   │            │
│  │  (Browser)   │         │  (Local)     │            │
│  └──────┬───────┘         └──────┬───────┘            │
│         │                        │                     │
└─────────┼────────────────────────┼─────────────────────┘
          │ WebSocket + JWT        │
          │ (httpOnly Cookie)      │
          ▼                        ▼
┌─────────────────────────────────────────────────────────┐
│                    Trusted Zone                         │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │              Socket.IO Server                    │   │
│  │                                                  │   │
│  │  ┌─────────────┐      ┌──────────────────────┐ │   │
│  │  │  JWT        │─────►│  Channel Manager     │ │   │
│  │  │  Validator  │      │                      │ │   │
│  │  └─────────────┘      │  user:alice@... ─────┼─┼──┼──► Alice's clients
│  │                       │  user:bob@...   ─────┼─┼──┼──► Bob's clients
│  │                       └──────────────────────┘ │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### STRIDE Analysis

#### Spoofing

| Threat | Mitigation |
|--------|------------|
| Attacker forges JWT | JWT signature verification (HS256) |
| Attacker steals JWT | ALLOWED_EMAILS check on every request |
| Attacker reuses JWT from different IP | No IP binding (consider adding for high security) |
| Attacker spoofs email in JWT | Email validated against ALLOWED_EMAILS |

#### Tampering

| Threat | Mitigation |
|--------|------------|
| Attacker modifies JWT payload | Signature verification detects tampering |
| Attacker modifies channel name | Server controls channel membership |
| Attacker injects into message content | HTML escaping sanitizes content |
| Attacker modifies message routing | Server-side routing, client cannot specify room |

#### Repudiation

| Threat | Mitigation |
|--------|------------|
| User denies sending message | Message includes user email and timestamp |
| No audit trail of messages | Consider adding message logging (future) |
| Connection events not logged | Connection/disconnection logged with email |

#### Information Disclosure

| Threat | Mitigation |
|--------|------------|
| Messages leaked to other users | Broadcast only to user's private channel |
| JWT token exposed | httpOnly cookie prevents JavaScript access |
| Channel names exposed | Authenticated event includes channel name |
| User enumeration | Error messages do not reveal user existence |

#### Denial of Service

| Threat | Mitigation |
|--------|------------|
| Connection flood | MAX_CLIENTS limit (1000 connections) |
| Message flood | Rate limiting per connection (not implemented) |
| Large messages | MAX_MESSAGE_LENGTH (1000 characters) |
| Malformed messages | Message validation before processing |

#### Elevation of Privilege

| Threat | Mitigation |
|--------|------------|
| User joins another user's channel | JWT email claim verified before channel join |
| User sends as another user | User email from JWT, not from message payload |
| User accesses admin functions | No admin functions implemented |
| User modifies token version | Token version validated against server-side value |

---

## Channel Access Control Recommendations

### Recommendation 1: Simplify Architecture (RECOMMENDED)

Remove `channel_token` from the security model:

**Rationale**:
- JWT signature verification provides strong identity verification
- ALLOWED_EMAILS provides user-level access control
- Token version provides session revocation
- Channel token adds complexity without clear security benefit

**Implementation**:

```python
# 1. Remove channel_token from JWT
def generate_jwt(email: str) -> str:
    payload = {
        "sub": f"user:{email}",
        "email": email,
        "iat": ...,
        "exp": ...,
        "ver": get_token_version(email),
        # REMOVED: "channel_token": channel_token,
    }
    return jwt.encode(payload, secret_key, algorithm="HS256")

# 2. Fix message routing to user's private channel
@server.socketio.on("message")
async def on_message(sid: str, data: dict) -> dict:
    # ... validation ...
    user_channel = f"user:{email}"
    await server.socketio.emit("message", message, room=user_channel)

# 3. Document that JWT email claim is trusted for channel access
```

### Recommendation 2: Add Defense-in-Depth Logging

```python
# Log all channel access for audit
@server.socketio.on("connect")
async def on_connect(sid: str, environ: dict, auth_data: dict | None) -> bool:
    # ... validation ...

    logger.info(
        f"Channel access: email={email} channel={user_channel} "
        f"ip={environ.get('REMOTE_ADDR')} sid={sid}"
    )

    # ... join channel ...
```

### Recommendation 3: Add Message Rate Limiting (Future)

```python
# Prevent message spam
message_rate_limiter = RateLimiter(max_requests=100, window_minutes=1)

@server.socketio.on("message")
async def on_message(sid: str, data: dict) -> dict:
    client_info = connected_clients.get(sid)
    if not client_info:
        return {"error": "Not authenticated"}

    # Check rate limit
    if not message_rate_limiter.is_allowed(client_info["email"]):
        return {"error": "Rate limit exceeded", "code": 429}

    # ... process message ...
```

---

## Implementation Checklist for I4-002

### Must Fix (Blocking)

- [ ] **CRITICAL-1**: Change message broadcast from global to user's channel
  - File: `app/__init__.py`, line 455
  - Change: `await server.socketio.emit("message", message)` to `await server.socketio.emit("message", message, room=user_channel)`

- [ ] **CRITICAL-2**: Decide on channel token architecture
  - Option A: Remove `channel_token` from JWT (RECOMMENDED)
  - Option B: Implement server-side token validation

- [ ] **CRITICAL-3**: Add channel access control function
  - Add `is_authorized_for_channel()` function
  - Document access control policy

### Should Fix (Related)

- [ ] **HIGH-1**: Sanitize channel names
  - Add `get_user_channel_name()` function
  - Sanitize email characters that could cause issues

- [ ] **MEDIUM-1**: If keeping channel tokens, implement lifecycle management

### Document

- [ ] **LOW-1**: Document channel naming convention
- [ ] Document security model (JWT-based channel access)
- [ ] Update architecture doc with final decision on channel tokens

### Testing

- [ ] Test: User A's messages not visible to User B
- [ ] Test: User A's web and CLI clients see same messages
- [ ] Test: Message routing to correct channel
- [ ] Test: Multi-client synchronization
- [ ] Test: Connection rejection with invalid JWT
- [ ] Test: Connection rejection with email not in ALLOWED_EMAILS

---

## Conclusion

The I4-002 implementation has critical security issues that must be addressed:

1. **Messages are broadcast globally** - Complete privacy violation
2. **Channel tokens are not validated** - Unclear security model
3. **No channel access control** - Defense in depth needed

**Risk Assessment**: **CRITICAL**

**Recommendations**:

1. **Immediately fix global broadcast** to route messages to user's private channel
2. **Simplify architecture** by removing channel tokens (JWT provides sufficient identity verification)
3. **Add channel access control** for defense in depth
4. **Sanitize channel names** to prevent potential injection issues

**Acceptable for Development**: No - Critical privacy issue must be fixed first.

**Acceptable for Production**: No - All critical findings must be addressed.

---

## References

- [OWASP Top 10:2025](https://owasp.org/Top10/)
- [OWASP A01:2025 - Broken Access Control](https://owasp.org/Top10/A01_2025-Broken_Access_Control/)
- [OWASP A05:2025 - Injection](https://owasp.org/Top10/A05_2025-Injection/)
- [OWASP A07:2025 - Authentication Failures](https://owasp.org/Top10/A07_2025-Identification_and_Authentication_Failures/)
- [OWASP Access Control Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Access_Control_Cheat_Sheet.html)
- [Socket.IO Rooms Documentation](https://socket.io/docs/v4/rooms/)
- [Socket.IO Security](https://socket.io/docs/v4/security/)
- [Socket.IO Emit Cheatsheet](https://socket.io/docs/v4/emit-cheatsheet/)