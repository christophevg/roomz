# API Analysis: JWT Session Tokens (I4-001)

**Task**: I4-001 - JWT Session Tokens
**Date**: 2026-05-15
**Analyst**: API Architect Agent
**Status**: Design Complete

## Executive Summary

This document defines the API design for replacing in-memory session storage with stateless JWT tokens. The key change is that `/auth/verify` will issue a JWT instead of an in-memory session token, enabling server restart tolerance and stateless authentication.

## 1. Current State Analysis

### 1.1 Existing Authentication Flow

```
1. POST /auth/request-magic-link
   - Validates email format
   - Checks rate limit (5 per email per hour)
   - Creates in-memory MagicLink (15 min expiry)
   - Logs magic link URL to console (dev mode)

2. GET /auth/verify?token=xxx
   - Validates magic link token (one-time use)
   - Creates in-memory Session (30 day expiry)
   - Sets httpOnly cookie: session_token=<opaque-token>
   - Redirects to /

3. WebSocket Connection
   - Extracts session_token from cookie
   - Validates against in-memory session_manager
   - Rejects if session not found or expired

4. Server Restart
   - All sessions lost
   - All magic links lost
   - All users must re-authenticate
```

### 1.2 Problems with Current Approach

| Problem | Impact |
|---------|--------|
| Sessions in-memory | Lost on server restart |
| Magic links in-memory | Lost on server restart |
| No ALLOWED_EMAILS check | Anyone with email can authenticate |
| No channel token | No private channel support |
| No revocation mechanism | Cannot instantly revoke access |

## 2. JWT-Based Sessions Design

### 2.1 JWT Token Structure

```json
{
  "sub": "user:<email>",
  "email": "user@example.com",
  "iat": 1713456000,
  "exp": 1716048000,
  "channel_token": "uuid-v4-random-token"
}
```

| Claim | Purpose | Notes |
|-------|---------|-------|
| `sub` | Subject identifier | `user:<email>` for user identification |
| `email` | User email address | Used for ALLOWED_EMAILS validation |
| `iat` | Issued at timestamp | Unix timestamp |
| `exp` | Expiration timestamp | 30 days from iat |
| `channel_token` | Channel access token | UUID v4 for private channel join |

### 2.2 Key Design Decisions

**Decision 1: JWT stored in httpOnly cookie**
- Same as current session_token cookie
- Prevents JavaScript access (XSS protection)
- Automatically sent with WebSocket handshake
- No client-side changes needed for web client

**Decision 2: Channel token embedded in JWT**
- Each JWT contains unique channel_token
- User must present token to join `user:{email}` channel
- Prevents unauthorized channel joins
- Simplified: one token for both auth and channel access

**Decision 3: ALLOWED_EMAILS check on every request**
- Checked at magic link request
- Checked at JWT verification
- Checked at WebSocket connection
- Instant revocation: remove email from allow-list = access denied

**Decision 4: Magic links remain in-memory**
- Short-lived (15 minutes)
- One-time use
- Still need cleanup task
- Acceptable trade-off for development phase

### 2.3 Token Issuance Flow

```
1. POST /auth/request-magic-link
   - Validate email format
   - Check ALLOWED_EMAILS env var
   - Check rate limit
   - Create in-memory MagicLink (unchanged)

2. GET /auth/verify?token=xxx
   - Validate magic link token (unchanged)
   - Generate JWT with channel_token
   - Set httpOnly cookie: session_token=<jwt>
   - Redirect to /

3. WebSocket Connection
   - Extract JWT from cookie
   - Verify JWT signature
   - Check email in ALLOWED_EMAILS
   - Extract channel_token
   - Join user channel: user:{email}

4. Server Restart
   - JWT tokens remain valid (stateless)
   - Magic links lost (acceptable - 15 min expiry)
   - Users reconnect automatically
```

## 3. API Endpoint Changes

### 3.1 POST /auth/request-magic-link

**Changes**: Add ALLOWED_EMAILS validation

**Request** (unchanged):
```json
{
  "email": "user@example.com"
}
```

**Success Response** (unchanged):
```json
{
  "status": "ok",
  "message": "Magic link generated. Check server console."
}
```

**New Error Response** (403 Forbidden):
```json
{
  "type": "https://roomz.local/errors/not-authorized",
  "title": "Not Authorized",
  "status": 403,
  "detail": "This email is not authorized to access this service.",
  "instance": "/auth/request-magic-link"
}
```

**Implementation**:
```python
ALLOWED_EMAILS = os.environ.get("ALLOWED_EMAILS", "").split(",")

def is_email_allowed(email: str) -> bool:
    """Check if email is in ALLOWED_EMAILS."""
    email_lower = email.lower().strip()
    return email_lower in [e.lower().strip() for e in ALLOWED_EMAILS if e.strip()]
```

### 3.2 GET /auth/verify

**Changes**: Issue JWT instead of in-memory session

**Request** (unchanged):
```
GET /auth/verify?token=<magic-link-token>
```

**Response** (unchanged):
- Redirect to `/` on success
- Set httpOnly cookie: `session_token=<jwt>`

**Implementation Changes**:
```python
# OLD: Create in-memory session
session_data = session_manager.create_session(email)

# NEW: Generate JWT
jwt_token = jwt.encode({
    "sub": f"user:{email}",
    "email": email,
    "iat": int(datetime.now(timezone.utc).timestamp()),
    "exp": int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp()),
    "channel_token": str(uuid.uuid4())
}, JWT_SECRET_KEY, algorithm="HS256")

# Set cookie (same format, different content)
response.set_cookie(
    "session_token",
    jwt_token,
    httponly=True,
    secure=False,  # True in production
    samesite="Strict",
    max_age=30 * 24 * 3600  # 30 days
)
```

### 3.3 GET /auth/me

**Changes**: Validate JWT instead of in-memory session

**Request** (unchanged):
```
GET /auth/me
Cookie: session_token=<jwt>
```

**Success Response** (unchanged):
```json
{
  "status": "ok",
  "user": {
    "email": "user@example.com",
    "created_at": "2024-01-15T10:30:00Z"
  }
}
```

**Implementation Changes**:
```python
# OLD: Validate in-memory session
session = session_manager.validate_token(token)

# NEW: Validate JWT and check ALLOWED_EMAILS
def validate_jwt(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=["HS256"])
        email = payload.get("email")
        
        # Check if email is still allowed
        if not is_email_allowed(email):
            return None
        
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
```

### 3.4 POST /auth/logout

**Changes**: Client-side only (JWT is stateless)

**Request** (unchanged):
```
POST /auth/logout
Cookie: session_token=<jwt>
```

**Response** (unchanged):
```json
{
  "status": "ok"
}
```

**Implementation Changes**:
```python
# OLD: Revoke session in memory
session_manager.revoke_session(token)

# NEW: Just clear cookie (JWT is stateless)
response.delete_cookie("session_token")
# Note: No server-side revocation for JWT
# ALLOWED_EMAILS provides revocation mechanism
```

### 3.5 WebSocket Connection

**Changes**: Validate JWT and join user channel

**Connection Flow**:
```python
@server.socketio.on("connect")
async def on_connect(sid: str, environ: dict, auth_data: dict | None) -> bool:
    # Extract JWT from cookie
    cookies = environ.get("HTTP_COOKIE", "")
    jwt_token = extract_token_from_cookie(cookies)
    
    if not jwt_token:
        return False
    
    # Validate JWT
    payload = validate_jwt(jwt_token)
    if not payload:
        return False
    
    # Check ALLOWED_EMAILS (redundant but explicit)
    email = payload.get("email")
    if not is_email_allowed(email):
        return False
    
    # Extract channel token
    channel_token = payload.get("channel_token")
    
    # Register connection
    connected_clients[sid] = {
        "email": email,
        "channel_token": channel_token,
        "connected_at": datetime.now(timezone.utc),
    }
    
    # Join user's private channel
    user_channel = f"user:{email}"
    await server.socketio.enter_room(sid, user_channel)
    
    # Send authenticated event
    await server.socketio.emit("authenticated", {
        "user": {"id": payload["sub"], "email": email},
        "channel": user_channel,
        "server_time": datetime.now(timezone.utc).isoformat()
    }, to=sid)
    
    return True
```

## 4. Environment Variables

### 4.1 Required

| Variable | Purpose | Example |
|----------|---------|---------|
| `JWT_SECRET_KEY` | Secret key for JWT signing | `256-bit-random-key` |
| `ALLOWED_EMAILS` | Comma-separated email allow-list | `alice@example.com,bob@example.com` |

### 4.2 Optional

| Variable | Purpose | Default |
|----------|---------|---------|
| `JWT_EXPIRY_DAYS` | JWT token lifetime | `30` |
| `MAGIC_LINK_EXPIRY_MINUTES` | Magic link lifetime | `15` |

### 4.3 Configuration

```bash
# .env
JWT_SECRET_KEY=your-256-bit-secret-key-here
ALLOWED_EMAILS=alice@example.com,bob@example.com,charlie@example.com
JWT_EXPIRY_DAYS=30
MAGIC_LINK_EXPIRY_MINUTES=15
```

## 5. WebSocket Event Changes

### 5.1 Event: `authenticated`

**Current**:
```json
{
  "user": {
    "id": "abc123",
    "email": "user@example.com"
  },
  "server_time": "2024-01-15T10:30:00Z"
}
```

**New**:
```json
{
  "user": {
    "id": "user:user@example.com",
    "email": "user@example.com"
  },
  "channel": "user:user@example.com",
  "server_time": "2024-01-15T10:30:00Z"
}
```

**Changes**:
- `user.id` changes from token hash to `user:{email}` format
- Added `channel` field to indicate user's private channel

### 5.2 Event: `message`

**Current**:
```json
{
  "id": "uuid",
  "user": {
    "id": "abc123",
    "email": "user@example.com"
  },
  "content": "Hello world",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

**New**: No changes to message format

### 5.3 Event: `user_joined` / `user_left`

**Current**:
```json
{
  "user": {
    "id": "abc123",
    "email": "user@example.com"
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

**New**: No changes to user presence events

### 5.4 Private Channel Broadcast (I4-002)

**Note**: This is for I4-002, documented here for context.

```python
# Broadcast to user's private channel only
await server.socketio.emit("message", message, room=f"user:{email}")
```

## 6. Security Considerations

### 6.1 JWT Security

| Aspect | Implementation |
|--------|----------------|
| Algorithm | HS256 (HMAC-SHA256) |
| Key Length | 256+ bits recommended |
| Key Storage | Environment variable |
| Expiration | 30 days (configurable) |

### 6.2 Revocation Mechanisms

| Mechanism | Implementation |
|-----------|----------------|
| Email removed from ALLOWED_EMAILS | Instant - checked on every request |
| JWT expiration | 30 days max |
| Client-side logout | Clear cookie |
| Server restart | No effect - stateless |

### 6.3 Attack Mitigation

| Attack | Mitigation |
|--------|------------|
| Token theft | httpOnly cookie, HTTPS |
| Token tampering | JWT signature verification |
| Replay attacks | JWT expiration |
| Unauthorized access | ALLOWED_EMAILS check |
| Brute force | Rate limiting on magic link |

### 6.4 ALLOWED_EMAILS Validation Points

```
┌─────────────────────────────────────────────────────────────┐
│                    Authentication Flow                       │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  POST /auth/request-magic-link                               │
│  ┌─────────────────┐                                        │
│  │ Check email in  │── No ──> 403 Forbidden                 │
│  │ ALLOWED_EMAILS  │                                        │
│  └────────┬────────┘                                        │
│           │ Yes                                              │
│           ▼                                                  │
│  GET /auth/verify                                            │
│  ┌─────────────────┐                                        │
│  │ Check email in  │── No ──> 403 Forbidden                 │
│  │ ALLOWED_EMAILS  │                                        │
│  └────────┬────────┘                                        │
│           │ Yes                                              │
│           ▼                                                  │
│  WebSocket Connection                                       │
│  ┌─────────────────┐                                        │
│  │ Check email in  │── No ──> Reject connection             │
│  │ ALLOWED_EMAILS  │                                        │
│  └────────┬────────┘                                        │
│           │ Yes                                              │
│           ▼                                                  │
│  ┌─────────────────┐                                        │
│  │ JWT Valid       │── No ──> Reject connection            │
│  │ (signature/exp) │                                        │
│  └────────┬────────┘                                        │
│           │ Yes                                              │
│           ▼                                                  │
│  ┌─────────────────┐                                        │
│  │ Accept          │                                        │
│  │ Connection      │                                        │
│  └─────────────────┘                                        │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## 7. Python Client Compatibility

### 7.1 Current Client Behavior

The Python client:
1. Calls `/auth/verify?token=xxx` with magic link token
2. Receives httpOnly cookie `session_token`
3. Uses cookie for WebSocket connection
4. Caches cookie in `session_cache_file`

### 7.2 Required Changes

**None required for basic operation.** The client:
- Already uses cookie-based authentication
- Cookie format remains the same (name: `session_token`)
- WebSocket connection unchanged

**Optional enhancement**: Expose `channel` from `authenticated` event.

```python
# New property on client
@property
def channel(self) -> str | None:
    """User's private channel name."""
    return self._channel

# In _on_authenticated
async def _on_authenticated(self, data: dict) -> None:
    self._user = data.get("user")
    self._channel = data.get("channel")  # NEW
    self._connection_state = ConnectionState.CONNECTED
    await self._events.emit("authenticated", data)
```

### 7.3 Migration Path

| Phase | Client Change |
|-------|---------------|
| I4-001 | No changes required |
| I4-002 | Optional: use `channel` for private messages |

## 8. Implementation Notes

### 8.1 File Changes

| File | Changes |
|------|---------|
| `app/auth.py` | Add JWT functions, remove SessionManager for sessions |
| `app/__init__.py` | Update WebSocket auth, add channel join logic |
| `pyproject.toml` | Add `PyJWT` dependency |
| `src/roomz/client/async_client.py` | Optional: expose `channel` property |

### 8.2 New Functions in `app/auth.py`

```python
import jwt
import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "development-key-change-me")
JWT_EXPIRY_DAYS = int(os.environ.get("JWT_EXPIRY_DAYS", "30"))
ALLOWED_EMAILS = [e.strip().lower() for e in os.environ.get("ALLOWED_EMAILS", "").split(",") if e.strip()]

def is_email_allowed(email: str) -> bool:
    """Check if email is in ALLOWED_EMAILS."""
    return email.lower().strip() in ALLOWED_EMAILS

def generate_jwt(email: str) -> str:
    """Generate JWT for authenticated user."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": f"user:{email}",
        "email": email,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=JWT_EXPIRY_DAYS)).timestamp()),
        "channel_token": str(uuid4())
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm="HS256")

def validate_jwt(token: str) -> dict | None:
    """Validate JWT and return payload if valid."""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=["HS256"])
        email = payload.get("email", "").lower()
        
        # Check if email is still allowed
        if not is_email_allowed(email):
            return None
        
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
```

### 8.3 SessionManager Removal

**Keep**: Magic link management (still in-memory)
**Remove**: Session creation and validation (replaced by JWT)

```python
# Remove from auth.py
class SessionManager:
    # ... entire class removed

# Remove global instance
session_manager = SessionManager()  # REMOVED

# Keep
magic_link_manager = MagicLinkManager()  # Still needed
magic_link_limiter = RateLimiter(...)    # Still needed
```

### 8.4 Models Changes

**Remove**: `Session` dataclass
**Keep**: `MagicLink` dataclass

```python
# app/models.py
# Remove Session dataclass entirely
# Keep MagicLink dataclass for magic link flow
```

## 9. Testing Strategy

### 9.1 Unit Tests

| Test | Description |
|------|-------------|
| `test_generate_jwt` | JWT generation with correct claims |
| `test_validate_jwt_valid` | Valid JWT returns payload |
| `test_validate_jwt_expired` | Expired JWT returns None |
| `test_validate_jwt_invalid_signature` | Invalid signature returns None |
| `test_is_email_allowed` | Email in allow-list |
| `test_is_email_not_allowed` | Email not in allow-list |
| `test_email_case_insensitive` | Case-insensitive email matching |

### 9.2 Integration Tests

| Test | Description |
|------|-------------|
| `test_magic_link_with_allowed_email` | Full flow with allowed email |
| `test_magic_link_with_blocked_email` | Rejected at magic link request |
| `test_jwt_websocket_connection` | WebSocket connects with valid JWT |
| `test_jwt_websocket_blocked_email` | Connection rejected if email removed |
| `test_server_restart_preserves_auth` | Server restart, reconnect still works |
| `test_logout_clears_cookie` | Logout clears JWT cookie |

### 9.3 Acceptance Criteria

| Criteria | Verification |
|----------|--------------|
| Login with magic link, get JWT | Cookie contains valid JWT |
| Server restart, reconnect still works | WebSocket reconnects successfully |
| Remove email from ALLOWED_EMAILS, access denied | WebSocket connection rejected |

## 10. Backward Compatibility

### 10.1 API Compatibility

| Endpoint | Change | Impact |
|----------|--------|--------|
| `/auth/request-magic-link` | Add 403 response | New error code |
| `/auth/verify` | JWT instead of opaque token | Cookie format same |
| `/auth/me` | JWT validation | Response format same |
| `/auth/logout` | No server-side revocation | Behavior same |
| WebSocket | JWT validation | Handshake same |

### 10.2 Client Compatibility

| Client | Impact |
|--------|--------|
| Web client | No changes required |
| Python client | No changes required |
| Future clients | Cookie-based auth works |

### 10.3 Breaking Changes

| Change | Mitigation |
|--------|------------|
| `user.id` format | Python client uses `email` for display |
| `session_manager` removed | Internal only |

## 11. Dependencies

### 11.1 New Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `PyJWT` | ^2.8.0 | JWT generation and validation |

### 11.2 pyproject.toml

```toml
[project]
dependencies = [
    # ... existing dependencies
    "PyJWT>=2.8.0",
]
```

## 12. Action Items

### 12.1 Backend Implementation (Priority Order)

1. **Add PyJWT dependency**:
   - Update `pyproject.toml`
   - Run `uv sync`

2. **Add JWT utility functions** (`app/auth.py`):
   - `is_email_allowed(email: str) -> bool`
   - `generate_jwt(email: str) -> str`
   - `validate_jwt(token: str) -> dict | None`

3. **Update `/auth/request-magic-link`**:
   - Add ALLOWED_EMAILS validation
   - Return 403 if email not allowed

4. **Update `/auth/verify`**:
   - Replace `session_manager.create_session()` with `generate_jwt()`
   - Keep magic link validation unchanged

5. **Update `/auth/me`**:
   - Replace `session_manager.validate_token()` with `validate_jwt()`

6. **Update `/auth/logout`**:
   - Remove `session_manager.revoke_session()` call
   - Just clear cookie

7. **Update WebSocket `on_connect`**:
   - Replace `session_manager.validate_token()` with `validate_jwt()`
   - Add ALLOWED_EMAILS check
   - Join user channel (preparation for I4-002)

8. **Remove SessionManager**:
   - Delete `SessionManager` class from `app/auth.py`
   - Delete `Session` dataclass from `app/models.py`
   - Remove `session_manager` global instance
   - Remove cleanup task for sessions (keep for magic links)

### 12.2 Python Client (Optional for I4-001)

1. **Add `channel` property** (optional):
   - Extract `channel` from `authenticated` event
   - Expose as property for I4-002 use

### 12.3 Configuration

1. **Add environment variables**:
   - Document `JWT_SECRET_KEY`
   - Document `ALLOWED_EMAILS`
   - Update `.env.example`

2. **Update README**:
   - Add JWT authentication documentation
   - Add ALLOWED_EMAILS configuration

### 12.4 Tests

1. **Unit tests**:
   - JWT generation and validation
   - ALLOWED_EMAILS check
   - Email case handling

2. **Integration tests**:
   - Full authentication flow
   - WebSocket connection
   - Server restart resilience

## 13. Conclusion

This design replaces in-memory sessions with stateless JWT tokens while maintaining backward compatibility with the existing Python client. The key benefits are:

1. **Server restart tolerance**: JWT tokens survive server restarts
2. **Instant revocation**: Remove email from ALLOWED_EMAILS to revoke access
3. **Stateless architecture**: No session storage needed
4. **Private channel preparation**: `channel_token` embedded in JWT for I4-002

The implementation requires minimal changes to the API surface and maintains compatibility with the existing cookie-based authentication flow.