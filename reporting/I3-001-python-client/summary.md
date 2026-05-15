# I3-001: Python Client Library

**Status**: Complete
**Date**: 2026-05-15

## Summary

Implemented a complete Python client library for programmatic access to the Roomz chat service, including:

- **AsyncClient**: Primary async WebSocket client with python-socketio
- **SyncClient**: Synchronous wrapper with background thread
- **CLI (TUI)**: Terminal user interface with Textual framework
- **Session caching**: Automatic reconnection with saved session cookies

## Implementation Details

### AsyncClient (`src/roomz/client/async_client.py`)

Primary async client with:
- `login(email)` - Request magic link for authentication
- `connect(session_token=None)` - Connect with token or cached session
- `send(content)` - Send message with acknowledgment
- `disconnect()` - Close connection
- Event emitter: `on('event', handler)` for real-time updates
- Session caching: `session_cache_file` parameter for auto-reconnect
- Connection state management: DISCONNECTED, CONNECTING, CONNECTED, RECONNECTING
- Exponential backoff reconnection with jitter

### SyncClient (`src/roomz/client/sync_client.py`)

Synchronous wrapper with:
- Background thread running asyncio event loop
- Same API as AsyncClient but synchronous
- Context manager support: `with SyncClient(...) as client:`

### Event System (`src/roomz/client/events.py`)

Event emitter supporting both sync and async handlers:
- `authenticated` - Connection established
- `message` - Chat message received
- `user_joined` - User joined
- `user_left` - User left
- `disconnect` - Connection lost
- `error` - Error occurred

### CLI TUI (`src/roomz/cli/app_tui.py`)

Textual-based terminal UI with:
- Split-screen layout (messages above, input below)
- Color-coded messages (own messages in green, others in blue)
- Commands: `/login`, `/token`, `/logout`, `/quit`
- Session caching for auto-reconnect
- Multiline support (Enter to send, Ctrl+Enter for newline)

### Exceptions (`src/roomz/client/exceptions.py`)

Exception hierarchy:
- `ClientError` - Base exception
- `ConnectionError` - WebSocket connection issues
- `AuthenticationError` - Authentication failures

## Files Added/Modified

### New Files
- `src/roomz/__init__.py` - Package root
- `src/roomz/client/__init__.py` - Client module exports
- `src/roomz/client/async_client.py` - AsyncClient implementation
- `src/roomz/client/sync_client.py` - SyncClient implementation
- `src/roomz/client/events.py` - EventEmitter implementation
- `src/roomz/client/state.py` - ConnectionState enum
- `src/roomz/client/exceptions.py` - Exception classes
- `src/roomz/cli/__init__.py` - CLI package
- `src/roomz/cli/__main__.py` - CLI entry point
- `src/roomz/cli/app_tui.py` - TUI application
- `src/roomz/cli/styles/chat.tcss` - TUI styles
- `tests/test_python_client.py` - Comprehensive test suite (46 tests)
- `analysis/api-python-client.md` - API design document
- `media/cli.png` - CLI screenshot

### Modified Files
- `pyproject.toml` - Added dependencies, CLI entry point, package paths
- `Makefile` - Updated lint/typecheck to include src/
- `README.md` - Added Python client documentation
- `uv.lock` - Dependency lockfile updates

## Tests

All 46 tests pass:
- `TestClientExceptions` - Exception hierarchy
- `TestConnectionState` - State enum
- `TestAsyncClientInit` - Initialization
- `TestAsyncClientEventHandling` - Event emitter
- `TestAsyncClientSend` - Message sending
- `TestSyncClientInit` - Sync client init
- `TestSyncClientEventHandling` - Sync event handling
- `TestAsyncClientConnection` - Connection lifecycle
- `TestAsyncClientLogin` - Magic link request
- `TestAsyncClientSessionCaching` - Session persistence
- `TestAsyncClientContextManager` - Context manager
- `TestSyncClientContextManager` - Sync context manager
- `TestClientModuleExports` - Module exports

3 tests skipped (require running server for integration tests).

## Type Checking

All mypy checks pass with proper type annotations:
- `EventHandler` type alias for sync/async handlers
- Return type annotations fixed
- URL type for aiohttp cookie filtering

## Linting

All ruff checks pass:
- Import order sorted
- Code formatted

## Usage Examples

### AsyncClient

```python
from roomz.client import AsyncClient
from pathlib import Path

async def main():
  client = AsyncClient(
    server_url="http://localhost:8000",
    session_cache_file=Path.home() / ".roomz" / "session.json"
  )

  client.on("message", lambda data: print(f"{data['user']['email']}: {data['content']}"))
  client.on("authenticated", lambda data: print(f"Connected as {data['user']['email']}"))

  await client.login("user@example.com")
  await client.connect(session_token="magic-link-token")

  result = await client.send("Hello!")
  await client.disconnect()
```

### SyncClient

```python
from roomz.client import SyncClient

with SyncClient(server_url="http://localhost:8000", session_token="token") as client:
  client.on("message", lambda data: print(data['content']))
  result = client.send("Hello!")
```

### CLI

```bash
uv run roomz-cli
> /login user@example.com
> /token <magic-link-token>
> Hello, world!
> /logout
> /quit
```

## Acceptance Criteria

- ✅ Python script can connect to server
- ✅ Can send messages that appear in web client
- ✅ Can receive messages from web client
- ✅ Event handlers fire correctly
- ✅ Sync wrapper works for synchronous code
- ✅ Session caching enables auto-reconnect
- ✅ CLI provides terminal interface

## Future Enhancements

- Add `session_cache_file` parameter to SyncClient
- Implement room support (join_room, leave_room)
- Add message history retrieval
- Add reconnection queue for messages during disconnect