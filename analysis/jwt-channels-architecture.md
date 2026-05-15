# JWT Sessions & Private Channels Architecture

**Date**: 2026-05-15
**Iteration**: I4

## Overview

This document describes the architecture for stateless JWT-based authentication with user-owned private channels.

## Current State

- Sessions stored in-memory (`session_manager` in `app/auth.py`)
- Magic links stored in-memory (`magic_link_manager` in `app/auth.py`)
- Server restart = all sessions and magic links lost
- All users share a global broadcast channel
- No private communication between users

## Proposed Architecture

### 1. JWT-Based Sessions

Replace in-memory sessions with stateless JWT tokens.

#### JWT Payload

```json
{
  "email": "user@example.com",
  "exp": 1716000000,
  "iat": 1713456000,
  "channel_token": "uuid-v4-random-token"
}
```

#### Components

| Component | Purpose |
|-----------|---------|
| `email` | User identity |
| `exp` | Expiration (30 days) |
| `iat` | Issued at time |
| `channel_token` | Token required to join user's channel |

#### Flow

```
1. POST /auth/request-magic-link
   - Check email against ALLOWED_EMAILS env var
   - Generate magic link token (still in-memory, short-lived)
   - Send email via SendGrid (or log to console in dev)

2. GET /auth/verify?token=xxx
   - Validate magic link token (one-time use)
   - Generate JWT with channel_token
   - Set JWT as httpOnly cookie
   - Redirect to chat

3. WebSocket Connection
   - Extract JWT from cookie
   - Verify JWT signature
   - Check email in ALLOWED_EMAILS
   - Join channel: user:{email}
   - Verify channel_token matches

4. Message Broadcast
   - Emit to user's channel only
   - user:{email} contains all user's connections
```

### 2. User-Owned Private Channels

Each user gets a private channel for their connections.

#### Channel Naming

```
user:{email}
```

Examples:
- `user:alice@example.com`
- `user:bob@company.org`

#### Access Control

The `channel_token` in the JWT ensures only authorized clients can join:

```python
# On WebSocket connect
@socketio.on("connect")
async def on_connect(sid, environ, auth):
    jwt_token = extract_jwt_from_cookie(environ)
    payload = jwt.decode(jwt_token, SECRET_KEY)
    
    # Verify email still allowed
    if payload["email"] not in ALLOWED_EMAILS:
        return False  # Reject connection
    
    # Get channel token
    channel_token = payload["channel_token"]
    
    # Store mapping
    connected_users[sid] = {
        "email": payload["email"],
        "channel_token": channel_token
    }
    
    # Join user's channel
    channel = f"user:{payload['email']}"
    await socketio_server.enter_room(sid, channel)
```

#### Security Properties

| Threat | Mitigation |
|--------|------------|
| User A joins User B's channel | channel_token mismatch |
| Forged JWT | Signature verification |
| Stolen JWT | ALLOWED_EMAILS check (remove email = revoked) |
| Replay attack | JWT expiration |

### 3. Email Allow-List

Environment-based access control.

#### Configuration

```bash
# .env
ALLOWED_EMAILS=alice@example.com,bob@example.com,charlie@example.com
SENDGRID_API_KEY=sg.xxx
SECRET_KEY=random-secret-key-for-jwt
```

#### Validation Points

1. **Magic Link Request**: Reject if email not in list
2. **JWT Verification**: Reject if email removed from list
3. **WebSocket Connection**: Reject if email removed from list

This provides instant revocation without a blacklist.

### 4. Email Integration

SendGrid for production, console logging for development.

#### Email Sender Abstraction

```python
# app/email.py
from abc import ABC, abstractmethod

class EmailSender(ABC):
    @abstractmethod
    async def send_magic_link(self, email: str, magic_link_url: str) -> bool:
        pass

class SendGridEmailSender(EmailSender):
    def __init__(self, api_key: str):
        self.api_key = api_key
    
    async def send_magic_link(self, email: str, magic_link_url: str) -> bool:
        # SendGrid API call
        ...

class ConsoleEmailSender(EmailSender):
    async def send_magic_link(self, email: str, magic_link_url: str) -> bool:
        print(f"\n=== MAGIC LINK ===")
        print(f"To: {email}")
        print(f"Link: {magic_link_url}")
        print(f"==================\n")
        return True
```

#### Configuration

```python
# app/__init__.py
def get_email_sender() -> EmailSender:
    sender_type = os.environ.get("EMAIL_SENDER", "console")
    if sender_type == "sendgrid":
        api_key = os.environ["SENDGRID_API_KEY"]
        return SendGridEmailSender(api_key)
    return ConsoleEmailSender()
```

## Migration Plan

### Phase 1: JWT Sessions (I4-001)

1. Add PyJWT dependency
2. Create JWT utility functions
3. Update `/auth/verify` to issue JWT
4. Update WebSocket auth to validate JWT
5. Add ALLOWED_EMAILS validation
6. Update Python client to handle JWT

### Phase 2: Private Channels (I4-002)

1. Modify WebSocket connect to join user channel
2. Modify message broadcast to use user channel
3. Add channel_token validation
4. Update frontend for user channel
5. Update Python client for user channel

### Phase 3: Email Integration (I5-001, I5-002)

1. Create EmailSender abstraction
2. Implement SendGridEmailSender
3. Implement ConsoleEmailSender
4. Add EMAIL_SENDER configuration
5. Create email template
6. Update /auth/request-magic-link

## File Changes

| File | Changes |
|------|---------|
| `app/auth.py` | JWT generation, EmailSender integration |
| `app/__init__.py` | WebSocket channel logic, JWT validation |
| `app/models.py` | Remove Session, add JWT payload model |
| `app/email.py` | New file - EmailSender classes |
| `pyproject.toml` | Add PyJWT, sendgrid dependencies |
| `src/roomz/client/async_client.py` | Handle JWT, channel token |
| `src/roomz/cli/app_tui.py` | Update for channel token |

## Testing Strategy

1. **Unit tests**: JWT generation/validation
2. **Unit tests**: EmailSender mocks
3. **Unit tests**: Channel token validation
4. **Integration tests**: Full auth flow with JWT
5. **Integration tests**: Multi-user private channels
6. **Manual tests**: SendGrid email delivery