# API Analysis: User-Owned Private Channels (I4-002)

**Project**: Roomz - Real-time Chatroom Web Service
**Task**: I4-002 - User-owned private channels
**Date**: 2026-05-15
**Analyst**: API Architect Agent

## 1. Overview

This document defines the API design for transitioning from global message broadcast to user-owned private channels. Each user gets a dedicated channel (`user:{email}`) that only their authenticated connections can join.

### Current State

| Aspect | Current Implementation |
|--------|------------------------|
| Channel join | User joins `user:{email}` on connect |
| Message broadcast | Global broadcast to all connected clients |
| user_joined event | Global broadcast to all clients |
| user_left event | Global broadcast to all clients |
| Channel validation | JWT contains `channel_token`, but not enforced |

### Target State

| Aspect | Target Implementation |
|--------|----------------------|
| Channel join | User joins `user:{email}` on connect (unchanged) |
| Message broadcast | Emit only to user's channel (`user:{email}`) |
| user_joined event | Emit only to user's channel (self-notification) |
| user_left event | Emit only to user's other connections |
| Channel validation | JWT `channel_token` validated on connect |

### Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Message routing | Per-user channel only | Private chat per user across multiple clients (web + Python) |
| Presence events | Per-user channel only | Privacy - no cross-user awareness in MVP |
| Channel naming | `user:{email}` | Simple, predictable, tied to identity |
| Multi-device | Same channel for all devices | All user's connections share the same channel |

## 2. Channel Membership Model

### 2.1 Channel Namespace

```
user:{email}
```

Examples:
- `user:alice@example.com`
- `user:bob@company.org`

### 2.2 Channel Access Control

Access to a channel is controlled by the JWT:

```json
{
  "sub": "user:alice@example.com",
  "email": "alice@example.com",
  "iat": 1713456000,
  "exp": 1716000000,
  "channel_token": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "ver": 1
}
```

| Claim | Purpose |
|-------|---------|
| `email` | Determines channel name (`user:{email}`) |
| `channel_token` | Unique token bound to this user's channel |
| `sub` | User identifier (same as `user:{email}`) |

### 2.3 Membership Rules

1. **Single channel per user**: All of a user's connections join the same channel
2. **Exclusive access**: Only connections with valid JWT for that email can join
3. **Multi-device support**: Web, Python CLI, and future clients all join the same channel

### 2.4 Connection State Model

```
                    +-------------+
                    | DISCONNECTED|
                    +------+------+
                           |
                    connect() with valid JWT
                           |
                           v
                    +-------------+
                    | CONNECTING  |
                    +------+------+
                           |
              Server sends 'authenticated'
                           |
                           v
                    +-------------+
            +------>|  CONNECTED  |
            |       +------+------+
            |              |
        disconnect        | send()
            |              |
            |              v
            |       +-------------+
            +-------| RECONNECTING|
                    +-------------+
```

## 3. WebSocket Event Flow Design

### 3.1 Event Overview

| Event | Direction | Scope | Purpose |
|-------|-----------|-------|---------|
| `connect` | Client -> Server | Connection | Establish WebSocket with JWT |
| `authenticated` | Server -> Client | Per-connection | Confirm authentication, send user info |
| `message` | Bidirectional | Per-channel | Send/receive chat messages |
| `user_joined` | Server -> Client | Per-channel | Notify when user's new connection joins |
| `user_left` | Server -> Client | Per-channel | Notify when user's connection leaves |
| `disconnect` | Client -> Server | Connection | Close WebSocket |
| `error` | Server -> Client | Per-connection | Error notification |

### 3.2 Connection Flow (Unchanged from I4-001)

```
Client                          Server
  |                               |
  |-- connect with JWT cookie --->|
  |                               |
  |                               |-- Validate JWT
  |                               |-- Check email in ALLOWED_EMAILS
  |                               |-- Extract channel_token
  |                               |-- Store connection metadata
  |                               |-- Join room: user:{email}
  |                               |
  |<-- authenticated -------------|
  |    {user, channel, server_time}
  |                               |
```

**Server Handler**:
```python
@server.socketio.on("connect")
async def on_connect(sid: str, environ: dict, auth_data: dict | None) -> bool:
    # Extract and validate JWT
    token = extract_token_from_cookie(environ.get("HTTP_COOKIE", ""))
    payload = validate_jwt(token)
    if not payload:
        return False  # Reject

    email = payload.get("email")
    channel_token = payload.get("channel_token")

    # Store connection info
    connected_clients[sid] = {
        "email": email,
        "channel_token": channel_token,
        "user_id": payload.get("sub"),
        "connected_at": datetime.now(timezone.utc),
    }

    # Join user's private channel
    user_channel = f"user:{email}"
    await server.socketio.enter_room(sid, user_channel)

    # Send authenticated event
    await server.socketio.emit("authenticated", {
        "user": {"id": payload.get("sub"), "email": email},
        "channel": user_channel,
        "server_time": datetime.now(timezone.utc).isoformat(),
    }, to=sid)

    return True
```

### 3.3 Message Flow (CHANGED)

```
Client A                        Server                        Client B
(same user)                     (routes to user channel)      (same user)
  |                               |                               |
  |-- message {content} --------->|                               |
  |                               |                               |
  |                               |-- Create message object       |
  |                               |-- Emit to user:{email} ------>|
  |<-- ack {status, message_id} --|                               |
  |                               |                               |
```

**Server Handler** (CHANGED - emit to channel instead of global):
```python
@server.socketio.on("message")
async def on_message(sid: str, data: dict) -> dict:
    client_info = connected_clients.get(sid)
    if not client_info:
        return {"error": "Not authenticated", "code": 401}

    email = client_info.get("email")
    user_id = client_info.get("user_id")

    # Validate and sanitize content
    content = data.get("content")
    if not content or not isinstance(content, str):
        return {"error": "Missing or invalid 'content' field", "code": 400}
    content = html.escape(content.strip())[:MAX_MESSAGE_LENGTH]

    # Create message
    message = {
        "id": str(uuid.uuid4()),
        "user": {"id": user_id, "email": email},
        "content": content,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # CHANGED: Emit to user's channel only, not global
    user_channel = f"user:{email}"
    await server.socketio.emit("message", message, room=user_channel)

    return {"status": "ok", "message_id": message["id"], "timestamp": message["timestamp"]}
```

### 3.4 Presence Events (CHANGED)

#### user_joined Event

**Current Behavior**: Broadcast globally to all users.

**New Behavior**: Emit only to the user's channel (to notify their other connections).

```python
# In on_connect, after joining room and sending authenticated event:

# CHANGED: Emit to user's channel only (skip the new connection)
await server.socketio.emit("user_joined", {
    "user": {"id": user_id, "email": email},
    "connection": {"sid": sid[:8]},  # Truncated for privacy
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "total_connections": count_user_connections(email),
}, room=user_channel, skip_sid=sid)
```

**Rationale**:
- User's other devices are notified of the new connection
- Other users do NOT see this (privacy)
- This enables multi-device awareness for the same user

#### user_left Event

**Current Behavior**: Broadcast globally to all users.

**New Behavior**: Emit only to the user's remaining connections.

```python
@server.socketio.on("disconnect")
async def on_disconnect(sid: str) -> None:
    client_info = connected_clients.pop(sid, None)
    if not client_info:
        return

    email = client_info.get("email")
    user_id = client_info.get("user_id")

    # CHANGED: Emit to user's channel only (notify their other connections)
    user_channel = f"user:{email}"
    remaining = count_user_connections(email)

    await server.socketio.emit("user_left", {
        "user": {"id": user_id, "email": email},
        "connection": {"sid": sid[:8]},
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "remaining_connections": remaining,
    }, room=user_channel)
```

### 3.5 Error Events

Error events are sent directly to the problematic connection:

```python
# Example: Invalid message format
await server.socketio.emit("error", {
    "type": "validation_error",
    "message": "Invalid message format",
    "code": 400,
}, to=sid)
```

## 4. Message Routing Rules

### 4.1 Routing Decision Matrix

| Event | Emit Target | Room | skip_sid | Notes |
|-------|-------------|------|----------|-------|
| `authenticated` | Single connection | N/A (to=sid) | N/A | Per-connection confirmation |
| `message` | User's channel | `user:{email}` | No | Include sender |
| `user_joined` | User's channel | `user:{email}` | Yes | Notify other devices |
| `user_left` | User's channel | `user:{email}` | No | Notify remaining devices |
| `error` | Single connection | N/A (to=sid) | N/A | Error handling |

### 4.2 Helper Functions

```python
def count_user_connections(email: str) -> int:
    """Count active connections for a user."""
    return sum(1 for c in connected_clients.values() if c.get("email") == email)

def get_user_channel(email: str) -> str:
    """Get the channel name for a user."""
    return f"user:{email}"

def get_user_sids(email: str) -> list[str]:
    """Get all connection SIDs for a user."""
    return [sid for sid, info in connected_clients.items() if info.get("email") == email]
```

## 5. API Contract for Emit Events

### 5.1 Client-to-Server Events

#### message

Send a chat message to the user's channel.

**Request**:
```json
{
  "content": "Hello from my phone!"
}
```

**Acknowledgment (success)**:
```json
{
  "status": "ok",
  "message_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2026-05-15T10:30:00.000Z"
}
```

**Acknowledgment (error)**:
```json
{
  "error": "Missing or invalid 'content' field",
  "code": 400
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `content` | string | Yes | Message text (max 1000 characters, HTML-escaped) |

### 5.2 Server-to-Client Events

#### authenticated

Confirmation of successful authentication. Sent once per connection.

```json
{
  "user": {
    "id": "user:alice@example.com",
    "email": "alice@example.com"
  },
  "channel": "user:alice@example.com",
  "server_time": "2026-05-15T10:30:00.000Z"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `user.id` | string | User identifier |
| `user.email` | string | User email address |
| `channel` | string | Channel name the client joined |
| `server_time` | ISO 8601 | Server timestamp |

#### message

Chat message broadcast to the user's channel.

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "user": {
    "id": "user:alice@example.com",
    "email": "alice@example.com"
  },
  "content": "Hello from my phone!",
  "timestamp": "2026-05-15T10:30:00.000Z"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID v4 | Unique message identifier |
| `user.id` | string | Sender's user ID |
| `user.email` | string | Sender's email |
| `content` | string | Sanitized message content |
| `timestamp` | ISO 8601 | Server timestamp when message was created |

#### user_joined

Notification that a new connection joined the user's channel (sent to other devices).

```json
{
  "user": {
    "id": "user:alice@example.com",
    "email": "alice@example.com"
  },
  "connection": {
    "sid": "abc12345"
  },
  "timestamp": "2026-05-15T10:30:00.000Z",
  "total_connections": 2
}
```

| Field | Type | Description |
|-------|------|-------------|
| `user.id` | string | User ID (same as receiving user) |
| `user.email` | string | User email |
| `connection.sid` | string | Truncated session ID (first 8 chars) |
| `timestamp` | ISO 8601 | Connection timestamp |
| `total_connections` | integer | Total active connections for this user |

#### user_left

Notification that a connection left the user's channel (sent to remaining devices).

```json
{
  "user": {
    "id": "user:alice@example.com",
    "email": "alice@example.com"
  },
  "connection": {
    "sid": "abc12345"
  },
  "timestamp": "2026-05-15T10:35:00.000Z",
  "remaining_connections": 1
}
```

| Field | Type | Description |
|-------|------|-------------|
| `user.id` | string | User ID |
| `user.email` | string | User email |
| `connection.sid` | string | Truncated session ID that left |
| `timestamp` | ISO 8601 | Disconnection timestamp |
| `remaining_connections` | integer | Remaining connections for this user |

#### error

Error notification sent to a specific connection.

```json
{
  "type": "validation_error",
  "message": "Invalid message format",
  "code": 400
}
```

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | Error type identifier |
| `message` | string | Human-readable error message |
| `code` | integer | HTTP-like error code |

## 6. Edge Cases

### 6.1 Multi-Device Connections

**Scenario**: User Alice connects from web browser, then connects from Python CLI.

```
Time    Action                              Channel Members
-----   ----------------------------------  ----------------------
T0      Alice connects via web              [web_sid]
T1      Server emits user_joined to web     [web_sid]
        (skipped - only one connection)
T2      Alice connects via Python CLI       [web_sid, cli_sid]
T3      Server emits user_joined to web     [web_sid, cli_sid]
        (cli_sid skipped as sender)
T4      Alice sends message from web        -> emit to user:alice
        -> web and CLI both receive         [web_sid, cli_sid]
T5      Alice sends message from CLI        -> emit to user:alice
        -> web and CLI both receive         [web_sid, cli_sid]
```

**Implementation**:
- All connections join the same `user:{email}` room
- SocketIO handles routing to all room members automatically
- `skip_sid` prevents echoing back to sender for presence events

### 6.2 Server Restart / Reconnection

**Scenario**: Server restarts while user has active connections.

```
Time    Action                              Client State
-----   ----------------------------------  ----------------------
T0      Alice connected via web and CLI     CONNECTED
T1      Server restarts                     DISCONNECTED
T2      Clients detect disconnect           RECONNECTING
T3      Clients auto-reconnect with JWT     CONNECTING
        (JWT still valid - 30 day expiry)
T4      Server validates JWT, joins room    CONNECTED
T5      Server emits authenticated          CONNECTED
```

**Implementation Notes**:
- JWT is stateless - survives server restart
- Python client has auto-reconnect with exponential backoff
- Web client should implement similar reconnect logic
- Reconnected client joins the same channel

**Required**: Web client needs reconnect logic:

```javascript
// In web client
socket.on("disconnect", () => {
  console.log("Disconnected, attempting reconnect...");
  // Socket.IO client handles reconnection automatically
  // but we should update UI state
});

socket.on("connect", () => {
  console.log("Reconnected");
  // Server will re-authenticate via JWT cookie
});
```

### 6.3 Network Interruption

**Scenario**: User's network briefly drops.

```
Time    Action                              Channel State
-----   ----------------------------------  ----------------------
T0      Alice connected (web, CLI)          [web_sid, cli_sid]
T1      Network drops on web                (web_sid still in room)
T2      Socket.IO ping timeout              Server removes web_sid
T3      Server emits user_left to CLI       [cli_sid]
        (remaining_connections: 1)
T4      Network restores on web             (new connection attempt)
T5      Web reconnects with JWT             [cli_sid, new_web_sid]
T6      Server emits user_joined to CLI     [cli_sid, new_web_sid]
```

**Implementation Notes**:
- Socket.IO handles heartbeat/ping timeout detection
- Server removes stale connections automatically
- Reconnection creates new sid but same channel

### 6.4 Concurrent Message Sending

**Scenario**: User sends messages from multiple devices simultaneously.

```
Time    Web Client              Server              CLI Client
-----   --------------------    ----------------    --------------------
T0      send("Hello")           |                   |
T1                              | receive msg       send("World")
T2      |                       | queue both        |
T3      |                       | process Hello     |
T4      receive Hello ----------| emit to channel   |
T5      |                       | process World     |
T6      receive World ----------| emit to channel   |
```

**Implementation Notes**:
- Each message gets unique UUID
- Server processes sequentially (async)
- All devices receive messages in server order

### 6.5 JWT Expiration During Session

**Scenario**: User's JWT expires while connected.

```
Time    Action                                  Result
-----   --------------------------------------  ----------------------
T0      User connects with JWT (exp: T+30days)  Connected
T1      ... days pass ...                       Connected
T30     JWT expires                             Connected (still valid)
        (but WebSocket already established)
T31     Network drop, reconnect attempt         Reconnect fails
        (JWT expired)                           Authentication rejected
```

**Implementation Notes**:
- WebSocket connection persists even if JWT expires
- Reconnection requires valid JWT
- Client should detect 401 and redirect to login

**Required**: Client-side JWT expiry handling:

```python
# In Python client
async def _attempt_reconnection(self):
    try:
        await self._sio.connect(...)
    except Exception:
        if "authentication" in str(e).lower():
            # JWT expired - need new magic link
            self.clear_cached_session()
            await self._events.emit("error", {
                "error": "Session expired. Please login again.",
                "code": 401,
            })
```

### 6.6 Email Removed from Allow-List

**Scenario**: Admin removes user's email from ALLOWED_EMAILS.

```
Time    Action                                  Result
-----   --------------------------------------  ----------------------
T0      User connected                          Connected
T1      Admin removes email from ALLOWED_EMAILS Connected
T2      User sends message                      Message sent
T3      Network drop, reconnect attempt         Reconnect fails
        (email not in allow-list)               Connection rejected
```

**Implementation Notes**:
- JWT validation checks ALLOWED_EMAILS on every connect
- Provides instant revocation without blacklist
- Active connections are NOT terminated (only on reconnect)

**Future Enhancement**: Active connection monitoring:
```python
# Optional: Periodically re-validate email allow-list
async def validate_active_connections():
    for sid, info in list(connected_clients.items()):
        if not is_email_allowed(info.get("email")):
            await server.socketio.disconnect(sid)
```

## 7. Security Considerations

### 7.1 Channel Isolation

| Threat | Mitigation |
|--------|------------|
| User A tries to join User B's channel | JWT email claim determines channel; cannot forge JWT |
| Eavesdropping on another user's messages | Server never emits to wrong channel |
| Session hijacking | httpOnly cookie prevents JS access |

### 7.2 JWT Security

| Aspect | Implementation |
|--------|---------------|
| Algorithm | HS256 (HMAC-SHA256) |
| Key strength | 256+ bits |
| Expiration | 30 days |
| Claims validation | `sub`, `email`, `exp`, `iat`, `channel_token` |
| Revocation | Remove email from ALLOWED_EMAILS |

### 7.3 Channel Token

The `channel_token` claim in the JWT provides an additional layer:

```json
{
  "channel_token": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

**Current Usage**: Stored but not actively validated.

**Future Enhancement**: Validate channel_token on sensitive operations:

```python
# Future: Require channel_token for sensitive operations
@server.socketio.on("admin_action")
async def on_admin_action(sid: str, data: dict) -> dict:
    client_info = connected_clients.get(sid)
    provided_token = data.get("channel_token")

    if provided_token != client_info.get("channel_token"):
        return {"error": "Invalid channel token", "code": 403}

    # Proceed with action
```

## 8. Implementation Checklist

### Backend Changes (app/__init__.py)

- [ ] Change `on_message` to emit to `room=user_channel` instead of global
- [ ] Change `user_joined` to emit to `room=user_channel` with `skip_sid=sid`
- [ ] Change `user_left` to emit to `room=user_channel`
- [ ] Add `count_user_connections()` helper function
- [ ] Add connection count to presence events
- [ ] Add truncated SID to presence events for privacy

### Python Client Changes (src/roomz/client/async_client.py)

- [ ] No changes needed - client already handles all events
- [ ] Update documentation to reflect private channel behavior

### Web Client Changes (if needed)

- [ ] Verify reconnect logic handles JWT expiry gracefully
- [ ] Update UI to show multi-device connection status
- [ ] Display connection count in presence events

### Testing

- [ ] Unit test: message routes to correct channel
- [ ] Unit test: user_joined emits only to user's channel
- [ ] Unit test: user_left emits only to user's channel
- [ ] Integration test: multi-device message delivery
- [ ] Integration test: reconnection after server restart
- [ ] Integration test: JWT expiry handling
- [ ] Integration test: email removed from allow-list

## 9. Migration Notes

### Breaking Changes

| Change | Impact | Mitigation |
|--------|--------|------------|
| Messages no longer global | Users cannot see other users' messages | Intended - private channels |
| user_joined no longer global | Users unaware of other users | Intended - privacy focus |
| user_left no longer global | Users unaware of other users | Intended - privacy focus |

### Backward Compatibility

- WebSocket protocol unchanged (same event names)
- Message format unchanged (same fields)
- JWT validation unchanged
- Only routing behavior changes

### Rollback Plan

If issues arise, revert to global broadcast:

```python
# Rollback: Emit globally instead of per-channel
await server.socketio.emit("message", message)  # Remove room parameter
await server.socketio.emit("user_joined", data)  # Remove room parameter
await server.socketio.emit("user_left", data)    # Remove room parameter
```

## 10. Future Considerations

### Public Channels (Post-I4)

For public/shared channels, add channel type:

```python
# Future: Support multiple channel types
channel_types = {
    "user:{email}": "private",      # Only user's connections
    "room:{room_id}": "shared",     # Multiple users with access
    "global": "public",             # Everyone
}
```

### Cross-User Messaging

For future 1:1 messaging between users:

```python
# Future: Send message to another user's channel
@server.socketio.on("direct_message")
async def on_direct_message(sid: str, data: dict) -> dict:
    target_email = data.get("to")
    target_channel = f"user:{target_email}"

    # Check if sender has permission to message target
    if not can_message(sender_email, target_email):
        return {"error": "Not authorized", "code": 403}

    await server.socketio.emit("message", message, room=target_channel)
```

### Room Support

For named conversation spaces (postponed to 2.0):

```python
# Future: Room-based channels
@server.socketio.on("join_room")
async def on_join_room(sid: str, data: dict) -> dict:
    room_id = data.get("room_id")
    await server.socketio.enter_room(sid, f"room:{room_id}")
```

## 11. Acceptance Criteria Verification

From TODO.md:

| Criteria | How Verified |
|----------|--------------|
| User A's web and Python clients see each other's messages | Integration test: both clients connect, send messages, both receive |
| User B cannot join User A's channel without valid token | Unit test: attempt join with wrong JWT, verify rejection |
| Multiple users have separate, private conversations | Integration test: 2 users, 2 clients each, verify message isolation |