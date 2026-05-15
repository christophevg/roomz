# API Reference

This page documents the Python client library API.

## Module: `roomz`

The main module exports the primary client classes and exceptions.

```python
from roomz import AsyncClient, SyncClient
from roomz import ClientError, ConnectionError, AuthenticationError
from roomz import ConnectionState
```

---

## AsyncClient

Primary async WebSocket client for Roomz real-time chat.

### Constructor

```python
AsyncClient(
  server_url: str,
  session_token: str = "",
  *,
  reconnect: bool = True,
  reconnect_delay: float = 1.0,
  max_reconnect_attempts: int = 5,
  connection_timeout: float = 10.0,
  session_cache_file: str | Path | None = None,
)
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `server_url` | `str` | required | WebSocket server URL (e.g., `http://localhost:8000`) |
| `session_token` | `str` | `""` | Magic link token for authentication |
| `reconnect` | `bool` | `True` | Enable automatic reconnection |
| `reconnect_delay` | `float` | `1.0` | Initial reconnection delay in seconds |
| `max_reconnect_attempts` | `int` | `5` | Maximum reconnection attempts |
| `connection_timeout` | `float` | `10.0` | Connection timeout in seconds |
| `session_cache_file` | `str \| Path \| None` | `None` | Path to cache session cookie |

### Properties

#### `connected` (property)

```python
@property
def connected() -> bool
```

Returns `True` if WebSocket is connected and authenticated.

#### `user` (property)

```python
@property
def user() -> dict | None
```

Returns current user info or `None` if not authenticated.

**Returns:** `{"id": str, "email": str}` or `None`

#### `connection_state` (property)

```python
@property
def connection_state() -> ConnectionState
```

Returns current connection state.

**Returns:** `ConnectionState` enum value

### Methods

#### `on(event, handler)`

```python
def on(event: str, handler: EventHandler) -> None
```

Register an event handler.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `event` | `str` | Event name: `authenticated`, `message`, `user_joined`, `user_left`, `disconnect`, `error` |
| `handler` | `Callable` | Callback function receiving event data (sync or async) |

**Example:**

```python
def on_message(data):
    print(f"{data['user']['email']}: {data['content']}")

client.on("message", on_message)
```

#### `off(event, handler=None)`

```python
def off(event: str, handler: EventHandler | None = None) -> None
```

Unregister an event handler.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `event` | `str` | Event name |
| `handler` | `Callable \| None` | Specific handler to remove, or `None` to remove all handlers for event |

#### `login(email)`

```python
async def login(email: str) -> bool
```

Request a magic link for authentication.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `email` | `str` | User email address |

**Returns:** `True` if magic link was requested successfully

**Raises:** `ConnectionError` if request fails

**Example:**

```python
success = await client.login("user@example.com")
# Check email for magic link...
```

#### `connect(session_token=None)`

```python
async def connect(session_token: str | None = None) -> None
```

Establish WebSocket connection with authentication.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `session_token` | `str \| None` | Magic link token. If not provided, uses cached session. |

**Raises:**
- `ConnectionError` if connection fails
- `AuthenticationError` if authentication fails

**Example:**

```python
# Connect with token
await client.connect(token="magic-link-token")

# Or reconnect with cached session
await client.connect()
```

#### `disconnect()`

```python
async def disconnect() -> None
```

Close WebSocket connection.

**Example:**

```python
await client.disconnect()
```

#### `send(content)`

```python
async def send(content: str) -> dict
```

Send a chat message.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `content` | `str` | Message content |

**Returns:**

On success:
```python
{
  "status": "ok",
  "message_id": "uuid",
  "timestamp": "2024-01-01T12:00:00Z"
}
```

On failure:
```python
{
  "error": "Error message",
  "code": 408  # HTTP status code
}
```

**Raises:** `ConnectionError` if not connected

**Example:**

```python
result = await client.send("Hello, world!")
if "error" in result:
    print(f"Failed: {result['error']}")
else:
    print(f"Message ID: {result['message_id']}")
```

#### `clear_cached_session()`

```python
def clear_cached_session() -> None
```

Clear cached session cookie.

**Example:**

```python
client.clear_cached_session()
```

### Context Manager

`AsyncClient` supports async context manager:

```python
async with AsyncClient(server_url, session_token) as client:
    client.on("message", handler)
    await client.send("Hello!")
```

---

## SyncClient

Synchronous wrapper around `AsyncClient` with background thread.

### Constructor

```python
SyncClient(
  server_url: str,
  session_token: str,
  *,
  reconnect: bool = True,
  reconnect_delay: float = 1.0,
  max_reconnect_attempts: int = 5,
  connection_timeout: float = 10.0,
)
```

**Note:** `session_cache_file` is not supported in `SyncClient`.

### Methods

All methods are synchronous equivalents of `AsyncClient`:

- `connect()` - Establish connection
- `disconnect()` - Close connection
- `send(content)` - Send message (synchronous)
- `on(event, handler)` - Register event handler
- `off(event, handler=None)` - Unregister event handler

### Context Manager

```python
with SyncClient(server_url, session_token) as client:
    client.on("message", handler)
    result = client.send("Hello!")
```

---

## ConnectionState Enum

```python
class ConnectionState(Enum):
  DISCONNECTED = "disconnected"
  CONNECTING = "connecting"
  CONNECTED = "connected"
  RECONNECTING = "reconnecting"
```

---

## Exceptions

### ClientError

Base exception for all client errors.

```python
class ClientError(Exception):
    """Base exception for client errors."""
```

### ConnectionError

Raised when connection fails.

```python
class ConnectionError(ClientError):
    """Connection-related errors."""
```

### AuthenticationError

Raised when authentication fails.

```python
class AuthenticationError(ClientError):
    """Authentication-related errors."""
```

---

## Events

### `authenticated`

Emitted when successfully authenticated.

**Data:**
```python
{
  "user": {"id": "user:email@example.com", "email": "email@example.com"},
  "channel": "user:email@example.com",
  "server_time": "2024-01-01T12:00:00Z"
}
```

### `message`

Emitted when a message is received.

**Data:**
```python
{
  "id": "uuid",
  "user": {"id": "user:email@example.com", "email": "email@example.com"},
  "content": "Message text",
  "timestamp": "2024-01-01T12:00:00Z"
}
```

### `user_joined`

Emitted when a user joins the channel.

**Data:**
```python
{
  "user": {"id": "user:email@example.com", "email": "email@example.com"},
  "timestamp": "2024-01-01T12:00:00Z",
  "total_connections": 1
}
```

### `user_left`

Emitted when a user leaves the channel.

**Data:**
```python
{
  "user": {"id": "user:email@example.com", "email": "email@example.com"},
  "timestamp": "2024-01-01T12:00:00Z",
  "remaining_connections": 0
}
```

### `disconnect`

Emitted when disconnected from server.

**Data:** `{}`

### `error`

Emitted when an error occurs.

**Data:**
```python
{
  "error": "Error message",
  "code": 500
}
```

---

## CLI Commands

The `roomz-cli` command provides a terminal interface.

### `roomz-cli`

```bash
roomz-cli [--server URL]
```

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--server`, `-s` | `http://localhost:8000` | Server URL |

### In-CLI Commands

| Command | Description |
|---------|-------------|
| `/login <email>` | Request magic link |
| `/token <token>` | Connect with token |
| `/logout` | Disconnect and clear session |
| `/quit` | Exit the CLI |