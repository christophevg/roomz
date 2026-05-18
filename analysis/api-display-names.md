# API Design: Display Names (I7-001)

**Date**: 2026-05-18
**Task**: I7-001 - Per-device display names
**Status**: Design Complete

## Summary

This document defines the WebSocket API for per-device display names. Display names allow users to identify which device/client they're using in multi-session scenarios (e.g., "Laptop", "Phone", "Work Computer").

**Key Design Decisions**:
1. **Stateless**: Display names are ephemeral, stored only client-side
2. **Per-connection**: Each WebSocket connection can have its own display name
3. **Server-side broadcasting**: Server tracks display names per connection and broadcasts in presence/message events
4. **Optional**: Display name is entirely optional; falls back to email-only display

## Resources

### Connection (Implicit)

The display name is an attribute of a WebSocket connection, not a standalone resource. It exists only while the connection is active.

## WebSocket Events

### Client → Server: Set Display Name

**Event Name**: `set_display_name`

Sets the display name for the current connection. This can be called at any time while connected.

**Payload**:
```json
{
  "display_name": "Laptop"
}
```

**Field Constraints**:
| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `display_name` | string | Yes | 1-50 characters, no newlines, no control characters, trimmed |

**Validation Rules**:
1. `display_name` must be a string
2. Length: 1-50 characters after trimming
3. Must not contain newlines (`\n`, `\r`)
4. Must not contain control characters (ASCII 0-31, except tab)
5. HTML/entities are escaped server-side (prevents XSS)

**Server Response (Acknowledgment)**:
```json
{
  "status": "ok",
  "display_name": "Laptop"
}
```

**Error Response**:
```json
{
  "error": "Invalid display name: must be 1-50 characters",
  "code": 400
}
```

**Server Behavior**:
1. Validate and sanitize the display name
2. Store in `connected_clients[sid]["display_name"]`
3. Broadcast updated presence to user's channel (same user's other connections)

**Example (Python Client)**:
```python
# Set display name after connection
await client.emit("set_display_name", {"display_name": "Laptop"})

# Change display name anytime
await client.emit("set_display_name", {"display_name": "Work Laptop"})
```

**Example (Web Client)**:
```javascript
socket.emit('set_display_name', { display_name: 'Laptop' }, (ack) => {
  if (ack.status === 'ok') {
    console.log('Display name set to:', ack.display_name);
  }
});
```

### Server → Client: Display Name Changed (Broadcast)

**Event Name**: `display_name_changed`

Broadcast to the user's channel when a connection updates its display name. This allows other devices to see the change in real-time.

**Payload**:
```json
{
  "user": {
    "id": "user:alice@example.com",
    "email": "alice@example.com",
    "display_name": "Laptop"
  },
  "timestamp": "2026-05-18T10:30:00.000Z",
  "connection_id": "abc123"
}
```

**Note**: `connection_id` is a unique identifier for the connection, useful for distinguishing multiple devices. This could be derived from the socket ID or a generated UUID stored on connection.

### Server → Client: Authenticated Event (Modified)

The `authenticated` event now includes display name if set.

**Before**:
```json
{
  "user": {"id": "user:alice@example.com", "email": "alice@example.com"},
  "channel": "user:alice@example.com",
  "server_time": "2026-05-18T10:30:00.000Z"
}
```

**After**:
```json
{
  "user": {
    "id": "user:alice@example.com",
    "email": "alice@example.com",
    "display_name": null
  },
  "channel": "user:alice@example.com",
  "server_time": "2026-05-18T10:30:00.000Z"
}
```

If display name is set:
```json
{
  "user": {
    "id": "user:alice@example.com",
    "email": "alice@example.com",
    "display_name": "Laptop"
  },
  "channel": "user:alice@example.com",
  "server_time": "2026-05-18T10:30:00.000Z"
}
```

### Server → Client: User Joined Event (Modified)

The `user_joined` event now includes display name.

**Payload**:
```json
{
  "user": {
    "id": "user:alice@example.com",
    "email": "alice@example.com",
    "display_name": "Laptop"
  },
  "timestamp": "2026-05-18T10:30:00.000Z",
  "total_connections": 2
}
```

If no display name set:
```json
{
  "user": {
    "id": "user:alice@example.com",
    "email": "alice@example.com",
    "display_name": null
  },
  "timestamp": "2026-05-18T10:30:00.000Z",
  "total_connections": 2
}
```

### Server → Client: User Left Event (Modified)

The `user_left` event now includes display name.

**Payload**:
```json
{
  "user": {
    "id": "user:alice@example.com",
    "email": "alice@example.com",
    "display_name": "Laptop"
  },
  "timestamp": "2026-05-18T10:30:00.000Z",
  "remaining_connections": 1
}
```

### Server → Client: Message Event (Modified)

The `message` event's `user` object now includes display name.

**Payload**:
```json
{
  "id": "msg_abc123",
  "user": {
    "id": "user:alice@example.com",
    "email": "alice@example.com",
    "display_name": "Laptop"
  },
  "content": "Hello from my laptop!",
  "timestamp": "2026-05-18T10:30:00.000Z"
}
```

If no display name set:
```json
{
  "id": "msg_abc123",
  "user": {
    "id": "user:alice@example.com",
    "email": "alice@example.com",
    "display_name": null
  },
  "content": "Hello!",
  "timestamp": "2026-05-18T10:30:00.000Z"
}
```

## Client-Side Storage

### Web Client

**Storage**: `localStorage`

```javascript
// Set display name
localStorage.setItem('roomz_display_name', 'Laptop');

// Get display name
const displayName = localStorage.getItem('roomz_display_name');

// Clear display name
localStorage.removeItem('roomz_display_name');
```

**Flow**:
1. On page load, check `localStorage` for existing display name
2. After authentication (`authenticated` event), send `set_display_name` if stored
3. User can change via `/name <name>` command in message input

### Python Client

**Storage Priority**:
1. `ROOMZ_DISPLAY_NAME` environment variable
2. `~/.roomz/config.toml` file

**Config File Format** (`~/.roomz/config.toml`):
```toml
[client]
display_name = "Laptop"
```

**Flow**:
1. Check `os.environ.get("ROOMZ_DISPLAY_NAME")` first
2. If not set, load `~/.roomz/config.toml` and read `client.display_name`
3. After authentication, send `set_display_name` if configured
4. User can change via `/name <name>` command in TUI

## Display Format

When displaying messages or presence events, clients should format as:

| Display Name | Email | Display Text |
|--------------|-------|---------------|
| Set | `alice@example.com` | `Laptop (alice@example.com)` |
| Not set | `alice@example.com` | `alice@example.com` |
| Empty string | `alice@example.com` | `alice@example.com` |
| `null` | `alice@example.com` | `alice@example.com` |

**Implementation**:
```javascript
function formatUser(user) {
  if (user.display_name && user.display_name.trim()) {
    return `${user.display_name.trim()} (${user.email})`;
  }
  return user.email;
}
```

```python
def format_user(user: dict) -> str:
    display_name = user.get("display_name")
    if display_name and display_name.strip():
        return f"{display_name.strip()} ({user['email']})"
    return user["email"]
```

## Security Considerations

### Input Sanitization

**Newline Prevention**: Display names must not contain newlines. This prevents log injection and UI manipulation.

```python
# Server-side validation
def validate_display_name(name: str) -> str | None:
    """Validate and sanitize display name. Returns None if invalid."""
    if not name:
        return None

    # Trim whitespace
    name = name.strip()

    # Length check
    if not (1 <= len(name) <= 50):
        return None

    # No newlines
    if '\n' in name or '\r' in name:
        return None

    # No control characters (ASCII 0-31, except tab)
    for char in name:
        if ord(char) < 32 and char != '\t':
            return None

    # HTML escape for XSS prevention (stored display_names are also escaped)
    import html
    name = html.escape(name)

    return name
```

### No Server Storage

Display names are **ephemeral**:
- Not stored in any database or file
- Lost when the WebSocket connection closes
- Must be re-sent by the client on each connection

**Implications**:
- No privacy concerns about storing user data
- No need for display name history or audit
- Users must re-enter display name on each session (or client stores locally)

### Rate Limiting

Consider rate limiting `set_display_name` events to prevent abuse:
- Max 5 changes per minute per connection
- No rate limit needed if change is infrequent

**Recommendation**: Start without rate limiting; add if abuse observed.

## Server-Side Implementation

### Connection Tracking Update

```python
# In connected_clients[sid]:
connected_clients[sid] = {
    "email": email,
    "user_id": user_id,
    "ip": environ.get("REMOTE_ADDR"),
    "connected_at": datetime.now(timezone.utc),
    "display_name": None,  # Added
    "connection_id": str(uuid.uuid4()),  # Added for unique identification
}
```

### Event Handler

```python
@server.socketio.on("set_display_name")
async def on_set_display_name(sid: str, data: dict) -> dict:
    """
    Handle display name setting from client.

    Args:
        sid: Socket session ID
        data: {display_name: str}

    Returns:
        {status: "ok", display_name: str} or {error: str, code: int}
    """
    # Get client info
    client_info = connected_clients.get(sid)
    if not client_info:
        return {"error": "Not authenticated", "code": 401}

    # Validate
    display_name = data.get("display_name")
    validated = validate_display_name(display_name) if display_name else None

    if display_name and validated is None:
        return {"error": "Invalid display name: must be 1-50 characters, no newlines", "code": 400}

    # Store
    client_info["display_name"] = validated

    # Broadcast to user's channel (same user's other connections)
    user_channel = USER_CHANNEL_FORMAT.format(client_info["email"])
    await server.socketio.emit(
        "display_name_changed",
        {
            "user": {
                "id": client_info["user_id"],
                "email": client_info["email"],
                "display_name": validated,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "connection_id": client_info.get("connection_id"),
        },
        room=user_channel,
        skip_sid=sid,
    )

    return {"status": "ok", "display_name": validated}
```

## Backward Compatibility

### Client Compatibility

Clients that don't send `set_display_name` will work unchanged:
- `user.display_name` will be `null`
- Display falls back to email-only

### Message Format

The `user` object in events is extended (additive change):
- Old clients: ignore `display_name` field
- New clients: use `display_name` if present

### Event Compatibility

| Event | Change | Compatibility |
|-------|--------|---------------|
| `authenticated` | Add `user.display_name` | Backward compatible |
| `user_joined` | Add `user.display_name` | Backward compatible |
| `user_left` | Add `user.display_name` | Backward compatible |
| `message` | Add `user.display_name` | Backward compatible |
| `set_display_name` | New event | Optional for clients |

## Testing Scenarios

### Basic Flow

1. Client connects with JWT
2. Client sends `set_display_name` with display name
3. Server acknowledges with `{status: "ok", display_name: "..."}`
4. Other connections receive `display_name_changed` event
5. Messages from this client include `display_name`

### Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Empty string display name | Server stores `null`, displays email-only |
| Whitespace-only name | Server stores `null` after trim |
| Name with newlines | Server rejects with error |
| Name > 50 chars | Server rejects with error |
| Name with HTML | Server escapes HTML, stores escaped version |
| Unicode characters | Allowed (e.g., emoji, accented characters) |
| Reconnect after disconnect | Client must re-send `set_display_name` |
| Multiple devices, same user | Each can have different display name |

### Multiple Devices Test

1. User connects Device A (no display name)
2. User connects Device B (sets display name "Laptop")
3. Device A sees: `alice@example.com joined` (no display name)
4. Device B sees: `alice@example.com joined` (from Device A)
5. Device B sets name: both devices see `display_name_changed`
6. Device A sets name "Phone": both devices see update
7. Both devices show messages with correct display names

## Implementation Tasks

1. **Server**: Add `display_name` to `connected_clients` structure
2. **Server**: Add `set_display_name` event handler with validation
3. **Server**: Update `user_joined`, `user_left`, `message` events to include `display_name`
4. **Server**: Add `display_name_changed` broadcast
5. **Web Client**: Store display name in `localStorage`
6. **Web Client**: Send `set_display_name` on connect if stored
7. **Web Client**: Add `/name <name>` command handling
8. **Web Client**: Update message/presence display to show `{name} ({email})`
9. **Python Client**: Add `set_display_name` method to AsyncClient
10. **Python Client**: Load display name from env/config
11. **Python TUI**: Add `/name <name>` command
12. **Python TUI**: Update message display

## API Summary

| Event | Direction | Purpose |
|-------|-----------|---------|
| `set_display_name` | Client → Server | Set display name for connection |
| `display_name_changed` | Server → Client | Broadcast name change to user's channel |
| `authenticated` | Server → Client | **Modified**: Includes `user.display_name` |
| `user_joined` | Server → Client | **Modified**: Includes `user.display_name` |
| `user_left` | Server → Client | **Modified**: Includes `user.display_name` |
| `message` | Server → Client | **Modified**: Includes `user.display_name` |

## Related Documents

- TODO.md - Task I7-001 definition
- analysis/api-jwt-sessions.md - JWT authentication design
- analysis/api-private-channels.md - Private channel architecture