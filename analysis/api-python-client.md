# API Analysis: Python Client Library

**Date**: 2026-05-14
**Task**: I3-001 Python client library
**Analyst**: API Architect Agent
**Updated**: 2026-05-15 (synced with implementation)

## 1. Summary

This document defines the API for the `roomz.client` Python module, providing programmatic access to the Roomz real-time chat service. The client follows async-first design principles with sync wrappers, uses the event emitter pattern for real-time updates, and handles cookie-based authentication with session caching for automatic reconnection.

## 2. Architecture Overview

### 2.1 Async-First Design

Following the mandatory design principle, the Python client library implements:

```
Primary: AsyncClient (python-socketio async client)
    ↓
Wrapper: SyncClient (wraps AsyncClient with thread-based event loop)
```

**Rationale**:
- Primary async implementation enables integration with async applications (FastAPI, Quart, asyncio)
- Sync wrapper provides convenience for scripts, CLI tools, and simple applications
- Both APIs share the same underlying connection management and event handling

### 2.2 Event-Based Communication

The client uses an event emitter pattern for real-time updates:

```
Server Events (received):
  - 'authenticated': Session established, user info received
  - 'message': Chat message received
  - 'user_joined': Another user joined
  - 'user_left': Another user left
  - 'disconnect': Connection lost

Client Events (for application use):
  - Application registers handlers via on('event', callback)
  - Client emits events when server messages arrive
```

### 2.3 Authentication Strategy

The client handles cookie-based session authentication with session caching:

1. **Magic Link Flow**: Call `login(email)` to request magic link
2. **Token Verification**: Call `connect(session_token=token)` with magic link token
3. **Session Caching**: Session cookie cached for automatic reconnection
4. **WebSocket Connection**: Cookie passed automatically via shared aiohttp session

## 3. Client Class Design

### 3.1 AsyncClient (Primary)

```python
class AsyncClient:
  """
  Async WebSocket client for Roomz real-time chat.

  Usage:
    # With session caching for auto-reconnect
    client = AsyncClient(
      server_url="http://localhost:8000",
      session_cache_file=Path.home() / ".roomz" / "session.json"
    )
    client.on('message', handle_message)
    await client.login("user@example.com")  # Request magic link
    await client.connect(token="magic-link-token")  # Connect

    # Or without caching
    async with AsyncClient(server_url, session_token) as client:
      client.on('message', handle_message)
      await client.send("Hello, world!")
  """

  def __init__(
    self,
    server_url: str,
    session_token: str = "",
    *,
    reconnect: bool = True,
    reconnect_delay: float = 1.0,
    max_reconnect_attempts: int = 5,
    connection_timeout: float = 10.0,
    session_cache_file: str | Path | None = None,
  ):
    """
    Initialize async client.

    Args:
      server_url: WebSocket server URL (e.g., "http://localhost:8000")
      session_token: Magic link token for authentication (optional, can be passed to connect())
      reconnect: Enable automatic reconnection (default: True)
      reconnect_delay: Initial delay between reconnection attempts in seconds (default: 1.0)
      max_reconnect_attempts: Maximum reconnection attempts (default: 5)
      connection_timeout: Timeout for connection in seconds (default: 10.0)
      session_cache_file: Path to cache session cookie for auto-reconnection (None to disable)
    """

  async def login(self, email: str) -> bool:
    """
    Request a magic link for authentication.

    Args:
      email: User email address

    Returns:
      True if magic link was requested successfully

    Raises:
      ConnectionError: If request fails
    """

  async def connect(self, session_token: str | None = None) -> None:
    """
    Establish WebSocket connection with authentication.

    Args:
      session_token: Optional magic link token. If not provided, attempts
                     to use cached session cookie for reconnection.

    Raises:
      ConnectionError: If connection fails
      AuthenticationError: If authentication fails
    """

  async def disconnect(self) -> None:
    """Close WebSocket connection."""

  async def __aenter__(self) -> "AsyncClient":
    """Async context manager entry. Calls connect()."""

  async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
    """Async context manager exit. Calls disconnect()."""

  async def send(self, content: str) -> dict:
    """
    Send a chat message.

    Args:
      content: Message content

    Returns:
      dict with 'status', 'message_id', 'timestamp' on success
      dict with 'error', 'code' on failure

    Raises:
      ConnectionError: If not connected
    """

  def on(self, event: str, handler: Callable[[dict], None]) -> None:
    """
    Register event handler.

    Args:
      event: Event name ('authenticated', 'message', 'user_joined',
              'user_left', 'disconnect', 'error')
      handler: Callback function receiving event data
    """

  def off(self, event: str, handler: Callable[[dict], None] | None = None) -> None:
    """
    Unregister event handler.

    Args:
      event: Event name
      handler: Specific handler to remove, or None to remove all handlers for event
    """

  def clear_cached_session(self) -> None:
    """Clear cached session cookie."""

  @property
  def connected(self) -> bool:
    """True if WebSocket is connected and authenticated."""

  @property
  def user(self) -> dict | None:
    """Current user info: {'id': str, 'email': str} or None if not authenticated."""

  @property
  def connection_state(self) -> ConnectionState:
    """Current connection state: DISCONNECTED, CONNECTING, CONNECTED, RECONNECTING."""
```

### 3.2 SyncClient (Convenience Wrapper)

```python
class SyncClient:
  """
  Synchronous WebSocket client for Roomz real-time chat.

  Provides a synchronous API wrapping the async implementation.
  Runs async event loop in background thread.

  Usage:
    with SyncClient(server_url, session_token) as client:
      client.on('message', handle_message)
      client.send("Hello, world!")
  """

  def __init__(
    self,
    server_url: str,
    session_token: str,
    *,
    reconnect: bool = True,
    reconnect_delay: float = 1.0,
    max_reconnect_attempts: int = 5,
    connection_timeout: float = 10.0,
  ):
    """Initialize sync client. Same parameters as AsyncClient."""

  def connect(self) -> None:
    """Establish WebSocket connection. Raises ConnectionError if authentication fails."""

  def disconnect(self) -> None:
    """Close WebSocket connection."""

  def __enter__(self) -> "SyncClient":
    """Context manager entry. Calls connect()."""

  def __exit__(self, exc_type, exc_val, exc_tb) -> None:
    """Context manager exit. Calls disconnect()."""

  def send(self, content: str) -> dict:
    """
    Send a chat message.

    Args:
      content: Message content

    Returns:
      dict with 'status', 'message_id', 'timestamp' on success
      dict with 'error', 'code' on failure

    Raises:
      ConnectionError: If not connected
    """

  def on(self, event: str, handler: Callable[[dict], None]) -> None:
    """Register event handler. Same as AsyncClient.on()."""

  def off(self, event: str, handler: Callable[[dict], None] | None = None) -> None:
    """Unregister event handler. Same as AsyncClient.off()."""

  @property
  def connected(self) -> bool:
    """True if WebSocket is connected and authenticated."""

  @property
  def user(self) -> dict | None:
    """Current user info: {'id': str, 'email': str} or None if not authenticated."""

  @property
  def connection_state(self) -> ConnectionState:
    """Current connection state."""
```

## 4. Connection Lifecycle

### 4.1 Connection States

```python
class ConnectionState(Enum):
  """WebSocket connection states."""

  DISCONNECTED = "disconnected"      # Not connected, no reconnection in progress
  CONNECTING = "connecting"          # Connection attempt in progress
  CONNECTED = "connected"            # Connected and authenticated
  RECONNECTING = "reconnecting"      # Reconnection attempt in progress (after disconnect)
```

### 4.2 Connection Flow

```
DISCONNECTED
    ↓ connect() called (with or without token)
CONNECTING
    ↓ Token provided? → Verify token, get session cookie
    ↓ No token? → Load cached session cookie if available
    ↓ WebSocket established
    ↓ authentication validated
CONNECTED (authenticated event received)
    ↓ connection lost
RECONNECTING (if reconnect=True)
    ↓ reconnection attempts (using cached session cookie)
    ├─ success → CONNECTED
    └─ max attempts exceeded → DISCONNECTED
```

### 4.3 Session Caching

The AsyncClient can cache session cookies for automatic reconnection:

```python
# Enable caching
client = AsyncClient(
  server_url="http://localhost:8000",
  session_cache_file=Path.home() / ".roomz" / "session.json"
)

# First time: login with magic link
await client.login("user@example.com")
await client.connect(session_token="magic-link-token")
# Session cookie is now cached

# Next time: auto-reconnect with cached session
await client.connect()  # Uses cached session cookie

# Clear session on logout
client.clear_cached_session()
```

### 4.4 Reconnection Strategy

```python
# Exponential backoff with jitter
reconnect_delay = base_delay * (2 ** attempt) + random_jitter

# Example sequence (base_delay=1.0, max_attempts=5):
# Attempt 1: wait ~1.0s
# Attempt 2: wait ~2.0s
# Attempt 3: wait ~4.0s
# Attempt 4: wait ~8.0s
# Attempt 5: wait ~16.0s
# → DISCONNECTED (give up)
```

### 4.5 Context Manager Usage

```python
# Async usage (recommended for async applications)
async with AsyncClient(server_url, token) as client:
  client.on('message', handle_message)
  await client.send("Hello!")
  # ... async operations ...

# Sync usage (for scripts and simple applications)
with SyncClient(server_url, token) as client:
  client.on('message', handle_message)
  client.send("Hello!")
  # ... synchronous operations ...
```

## 5. Authentication Flow

### 5.1 Magic Link Authentication

The client supports the full magic link authentication flow:

```python
# 1. Create client with session caching
client = AsyncClient(
  server_url="http://localhost:8000",
  session_cache_file=Path.home() / ".roomz" / "session.json"
)

# 2. Request magic link (sent to email or shown in dev console)
await client.login("user@example.com")

# 3. Connect with magic link token (from email or console)
await client.connect(session_token="magic-link-token-from-email")

# 4. Session cookie is now cached for auto-reconnect
# On restart, just call connect() without token
await client.connect()  # Uses cached session
```

### 5.2 Authentication Implementation

```python
# AsyncClient.connect()
async def connect(self, session_token: str | None = None) -> None:
  """Establish WebSocket connection with authentication."""

  # Create shared aiohttp session for HTTP and WebSocket
  if not self._session:
    self._session = aiohttp.ClientSession()

  # Use provided token or constructor token
  token = session_token or self._session_token

  # Try to load cached session cookie if no token provided
  if not token:
    cached_cookie = self._load_session_cookie()
    if cached_cookie:
      self._session.cookie_jar.update_cookies({"session_token": cached_cookie})

  # Verify magic link token if provided
  if token:
    verify_url = f"{self._server_url}/auth/verify?token={token}"
    async with self._session.get(verify_url) as resp:
      # Server sets session cookie
      # Extract and save session cookie
      ...

  # Connect WebSocket (cookie passed automatically via shared session)
  self._sio = socketio.AsyncClient(http_session=self._session)
  await self._sio.connect(self._server_url)
```

### 5.3 Why This Works

| Client Type | Can Read Set-Cookie Header | Can Use in WebSocket |
|--------------|---------------------------|----------------------|
| **Browser** | No (httpOnly restriction) | Yes (browser passes automatically) |
| **Python** | Yes (no browser restriction) | Yes (via shared aiohttp session) |

## 6. Event System Design

### 6.1 Event Emitter Pattern

```python
class EventEmitter:
  """Simple event emitter for client events."""

  def __init__(self):
    self._handlers: dict[str, list[Callable]] = defaultdict(list)

  def on(self, event: str, handler: Callable[[dict], None]) -> None:
    """Register handler for event."""
    self._handlers[event].append(handler)

  def off(self, event: str, handler: Callable[[dict], None] | None = None) -> None:
    """Unregister handler(s) for event."""
    if handler:
      self._handlers[event].remove(handler)
    else:
      self._handlers[event].clear()

  async def emit(self, event: str, data: dict) -> None:
    """Emit event to all registered handlers (async)."""
    for handler in self._handlers[event]:
      try:
        result = handler(data)
        if asyncio.iscoroutine(result):
          await result
      except Exception as e:
        logger.error(f"Error in {event} handler: {e}")
```

### 6.2 Server Events Mapped to Client Events

| Server Event | Client Event | Data Structure |
|--------------|--------------|----------------|
| `authenticated` | `authenticated` | `{'user': {'id': str, 'email': str}}` |
| `message` | `message` | `{'id': str, 'user': {'id': str, 'email': str}, 'content': str, 'timestamp': str}` |
| `user_joined` | `user_joined` | `{'user': {'id': str, 'email': str}, 'timestamp': str}` |
| `user_left` | `user_left` | `{'user': {'id': str, 'email': str}, 'timestamp': str}` |
| `disconnect` | `disconnect` | `{}` |
| N/A | `error` | `{'error': str, 'code': int}` |

### 6.3 Event Handler Signatures

```python
# All event handlers receive a single dict argument
def handle_authenticated(data: dict) -> None:
  """Called when connection is authenticated."""
  print(f"Authenticated as: {data['user']['email']}")

def handle_message(data: dict) -> None:
  """Called when a chat message is received."""
  print(f"{data['user']['email']}: {data['content']}")

def handle_user_joined(data: dict) -> None:
  """Called when another user joins."""
  print(f"User joined: {data['user']['email']}")

def handle_user_left(data: dict) -> None:
  """Called when another user leaves."""
  print(f"User left: {data['user']['email']}")

def handle_disconnect(data: dict) -> None:
  """Called when connection is lost."""
  print("Disconnected from server")

def handle_error(data: dict) -> None:
  """Called on connection or message errors."""
  print(f"Error {data['code']}: {data['error']}")
```

### 6.4 Thread-Safe Event Handling (SyncClient)

For `SyncClient`, event handlers are called from the background thread. Use thread-safe mechanisms:

```python
import queue

message_queue = queue.Queue()

def handle_message(data: dict) -> None:
  """Thread-safe message handler."""
  message_queue.put(data)

with SyncClient(server_url, token) as client:
  client.on('message', handle_message)

  # Process messages in main thread
  while True:
    try:
      msg = message_queue.get(timeout=1.0)
      print(f"Message: {msg}")
    except queue.Empty:
      if not client.connected:
        break
```

## 7. Error Handling Strategy

### 7.1 Error Types

```python
class ClientError(Exception):
  """Base exception for all client errors."""
  pass

class ConnectionError(ClientError):
  """Failed to establish or maintain connection."""
  pass

class AuthenticationError(ClientError):
  """Authentication failed."""
  pass
```

### 7.2 Error Scenarios

| Scenario | Exception | Event | Recovery |
|----------|-----------|-------|----------|
| Invalid session token | `AuthenticationError` on `connect()` | `error` | Obtain new token |
| Connection timeout | `ConnectionError` | `error` | Retry with backoff |
| Network disconnect | N/A | `disconnect` | Auto-reconnect if enabled |
| Max reconnect attempts | N/A | `error` | User action required |
| Message send failed | Returns error dict | None | Check return value |
| Invalid message format | Returns error dict | None | Validate message content |

### 7.3 Error Response Format

Message send operations return error dicts instead of raising exceptions:

```python
# Success response
result = await client.send("Hello!")
# {'status': 'ok', 'message_id': 'uuid', 'timestamp': '2026-05-14T10:30:00Z'}

# Error response
result = await client.send("")
# {'error': 'Missing or invalid content field', 'code': 400}
```

### 7.4 Event-Based Error Handling

```python
client.on('error', handle_error)

async def handle_error(data: dict) -> None:
  """Handle connection errors."""
  error_type = data.get('error')
  code = data.get('code')

  if code == 401:
    # Authentication error - need to re-authenticate
    logger.error("Authentication failed. Obtain new session token.")
    client.clear_cached_session()  # Clear invalid cached session
  elif code == 429:
    # Rate limited
    logger.warning("Rate limited. Slow down.")
  else:
    # Generic error
    logger.error(f"Error {code}: {error_type}")
```

## 8. Usage Examples

### 8.1 Basic Async Usage (with Session Caching)

```python
import asyncio
from pathlib import Path
from roomz.client import AsyncClient

async def main():
  server_url = "http://localhost:8000"

  # Create client with session caching
  client = AsyncClient(
    server_url=server_url,
    session_cache_file=Path.home() / ".roomz" / "session.json"
  )

  # Register event handlers
  client.on('message', lambda data: print(f"{data['user']['email']}: {data['content']}"))
  client.on('user_joined', lambda data: print(f"Joined: {data['user']['email']}"))
  client.on('user_left', lambda data: print(f"Left: {data['user']['email']}"))
  client.on('authenticated', lambda data: print(f"Authenticated as: {data['user']['email']}"))

  # Try to connect with cached session
  try:
    await client.connect()
    print("Connected with cached session")
  except Exception:
    # No cached session, need to login
    print("Requesting magic link...")
    await client.login("user@example.com")
    print("Check server console for magic link")
    # In real app, you'd wait for user to provide token
    token = input("Enter magic link token: ")
    await client.connect(session_token=token)

  # Send message
  result = await client.send("Hello from Python!")
  if 'error' in result:
    print(f"Failed to send: {result['error']}")
  else:
    print(f"Message sent: {result['message_id']}")

  # Keep running
  await asyncio.sleep(60)

  # Disconnect
  await client.disconnect()

asyncio.run(main())
```

### 8.2 Basic Sync Usage

```python
from roomz.client import SyncClient

def handle_message(data):
  print(f"{data['user']['email']}: {data['content']}")

server_url = "http://localhost:8000"
session_token = "your-session-token"

with SyncClient(server_url, session_token) as client:
  client.on('message', handle_message)

  print(f"Connected as: {client.user['email']}")

  # Send message
  result = client.send("Hello from Python!")
  print(f"Message sent: {result['message_id']}")

  # Keep running
  import time
  time.sleep(60)
```

### 8.3 Chat Application Class (CLI Example)

```python
import asyncio
from pathlib import Path
from roomz.client import AsyncClient

class ChatApp:
  def __init__(self, server_url: str):
    self.client = AsyncClient(
      server_url=server_url,
      session_cache_file=Path.home() / ".roomz" / "session.json"
    )
    self.messages = []

  async def on_message(self, data: dict) -> None:
    """Handle incoming message."""
    self.messages.append(data)
    print(f"{data['user']['email']}: {data['content']}")

  async def on_user_joined(self, data: dict) -> None:
    """Handle user joined."""
    print(f">>> {data['user']['email']} joined the chat")

  async def on_user_left(self, data: dict) -> None:
    """Handle user left."""
    print(f">>> {data['user']['email']} left the chat")

  async def run(self) -> None:
    """Run chat application."""
    # Register handlers
    self.client.on('message', self.on_message)
    self.client.on('user_joined', self.on_user_joined)
    self.client.on('user_left', self.on_user_left)

    # Try cached session first
    try:
      await self.client.connect()
    except Exception:
      # Need to login
      email = input("Email: ")
      await self.client.login(email)
      token = input("Magic link token: ")
      await self.client.connect(session_token=token)

    print(f"Connected as: {self.client.user['email']}")

    # Interactive input loop
    loop = asyncio.get_event_loop()
    while True:
      # Read input non-blocking
      line = await loop.run_in_executor(None, input, "> ")
      if line.lower() in ('/quit', '/exit'):
        break
      if line.lower() == '/logout':
        await self.client.disconnect()
        self.client.clear_cached_session()
        break

      result = await self.client.send(line)
      if 'error' in result:
        print(f"Error: {result['error']}")

    await self.client.disconnect()

# Run
app = ChatApp("http://localhost:8000")
asyncio.run(app.run())
```

### 8.4 Testing with Mock Server

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from roomz.client import AsyncClient

@pytest.mark.asyncio
async def test_client_connects_and_sends_message():
  # Mock server
  mock_sio = AsyncMock()
  mock_sio.connected = True
  mock_sio.emit = AsyncMock(return_value={'status': 'ok', 'message_id': 'test-id'})

  client = AsyncClient("http://test", "test-token")
  client._sio = mock_sio

  # Connect
  await client.connect()
  assert client.connected

  # Send message
  result = await client.send("Test message")
  assert result['status'] == 'ok'
  assert result['message_id'] == 'test-id'
```

## 9. Package Structure

### 9.1 Module Organization

```
src/roomz/
  __init__.py            # Package root
  client/
    __init__.py          # Exports: AsyncClient, SyncClient, ConnectionState, exceptions
    async_client.py      # AsyncClient implementation
    sync_client.py       # SyncClient implementation (wraps AsyncClient)
    events.py            # EventEmitter, event types
    state.py             # ConnectionState enum
    exceptions.py        # ClientError, ConnectionError, AuthenticationError
```

### 9.2 Package Exports

```python
# src/roomz/client/__init__.py
from .async_client import AsyncClient
from .sync_client import SyncClient
from .state import ConnectionState
from .exceptions import (
  ClientError,
  ConnectionError,
  AuthenticationError,
)

__all__ = [
  "AsyncClient",
  "SyncClient",
  "ConnectionState",
  "ClientError",
  "ConnectionError",
  "AuthenticationError",
]
```

### 9.3 Dependencies

The client library is part of the main `roomz` package:

```toml
# pyproject.toml
[project]
name = "roomz"
dependencies = [
  "python-socketio[asyncio]>=5.10.0",  # WebSocket client
  "aiohttp>=3.9.0",  # Async HTTP (for python-socketio)
]
```

## 10. Implementation Requirements

### 10.1 Server-Side Changes

**None required.** The existing authentication flow supports Python clients via cookie-based authentication using shared aiohttp sessions.

### 10.2 Client Implementation Status

- [x] Core Classes: `AsyncClient` with python-socketio
- [x] Event System: `EventEmitter` for handler registration
- [x] State Management: `ConnectionState` tracking
- [x] Sync Wrapper: `SyncClient` with background thread
- [x] Error Handling: Exception hierarchy and error propagation
- [x] Session Caching: Cache session cookies for auto-reconnect
- [x] Magic Link Support: `login()` method for requesting magic links
- [x] Tests: Unit tests with mocked Socket.IO

## 11. Future Enhancements

1. **SyncClient Session Caching**:
   - Add `session_cache_file` parameter to SyncClient
   - Mirror AsyncClient's caching behavior

2. **Room Support** (I4-001):
   - Add `join_room(room_id: str)` method
   - Add `leave_room(room_id: str)` method
   - Add `send(content: str, room_id: str | None)` method
   - Add `room_joined`, `room_left` events

3. **Message History** (I7-002):
   - Add `get_history(room_id: str, limit: int = 50)` method
   - Add `on('history', handler)` for receiving history on join

4. **Reconnection Queue**:
   - Queue messages during reconnection
   - Send queued messages on reconnection

5. **Heartbeat/Ping-Pong**:
   - Implement client-side ping timeout detection
   - Configurable heartbeat interval

## 12. Acceptance Criteria

| Criterion | Verification |
|-----------|--------------|
| Python script can connect | Manual test with valid session token |
| Send and receive messages | Integration test with running server |
| Event handlers fire correctly | Unit test with mocked Socket.IO |
| Sync wrapper works | Manual test in synchronous script |
| Connection state management | Unit test for state transitions |
| Reconnection works | Integration test with server restart |
| Session caching works | Manual test with restart |
| Error handling | Unit test for error scenarios |
| Documentation | README with usage examples |

## 13. References

- **Server Implementation**: `/app/__init__.py` - WebSocket handlers and authentication
- **Authentication Module**: `/app/auth.py` - Session management, magic link flow
- **Models**: `/app/models.py` - Session and MagicLink dataclasses
- **Frontend Client**: `/app/pages/chat/chat.js` - JavaScript client reference
- **CLI Implementation**: `/src/roomz/cli/app_tui.py` - Textual TUI using AsyncClient
- **Tests**: `/tests/test_python_client.py` - Unit tests for client library
- **README**: `/README.md` - Usage examples for CLI and Python client