# WebSocket Testing Strategy

## Current Situation

All WebSocket tests in `test_websocket.py` are currently **skipped** (45 tests).

### Why?

The tests were written for sync SocketIO which has `test_client()`:

```python
# Works with sync Server, NOT with AsyncServer
client = server.socketio.test_client(server)
```

Roomz uses `AsyncServer` (async SocketIO with Quart), which **does not support** `test_client()`:

```python
# AsyncServer has no test_client method
socketio.AsyncServer(async_mode="asgi")  # No test_client()
```

## Proposed Solutions

### Option 1: Unit Test Handler Logic (Recommended for Now)

Extract WebSocket handler logic into pure functions that can be tested without SocketIO:

```python
# app/websocket_handlers.py

def validate_session_for_connection(cookies: str, session_manager) -> dict | None:
    """
    Extract token from cookies, validate session.
    
    Returns user info dict or None if invalid.
    """
    token = extract_token_from_cookie(cookies)
    if not token:
        return None
    session = session_manager.validate_token(token)
    if not session:
        return None
    if datetime.now(timezone.utc) > session.expires_at:
        return None
    return {"email": session.email, "token_hash": session.token_hash}


def create_broadcast_message(sid: str, session, content: str) -> dict:
    """
    Create a broadcast message dict with user info.
    """
    return {
        "id": str(uuid.uuid4()),
        "user": {"id": session.token_hash[:8], "email": session.email},
        "content": html.escape(content.strip())[:MAX_MESSAGE_LENGTH],
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
```

**Tests:**

```python
# tests/test_websocket_handlers.py

def test_validate_session_valid():
    session_manager.create_session("test@example.com", ...)
    cookies = "session_token=valid_token"
    result = validate_session_for_connection(cookies, session_manager)
    assert result["email"] == "test@example.com"

def test_validate_session_expired():
    # ... test expired session is rejected
```

**Pros:**
- Fast, runs with other unit tests
- No server setup needed
- Tests core logic thoroughly

**Cons:**
- Doesn't test actual WebSocket communication
- Handler integration not tested

### Option 2: Integration Tests with Running Server

Create integration tests that start the server and connect real clients:

```python
# tests/integration/test_websocket_flow.py

import pytest
import socketio
import subprocess
import time

@pytest.fixture(scope="module")
def server():
    """Start the server as a subprocess."""
    proc = subprocess.Popen(["uv", "run", "uvicorn", "app:asgi_app", "--port", "8001"])
    time.sleep(2)  # Wait for server to start
    yield
    proc.terminate()

@pytest.mark.integration
async def test_chat_flow(server):
    """Test complete chat flow with real WebSocket."""
    client = socketio.AsyncClient()
    await client.connect("http://localhost:8001", headers={...})
    
    # Test message sending
    await client.emit("message", {"content": "Hello"})
    response = await client.receive()
    assert response["content"] == "Hello"
```

**Run integration tests:**
```bash
uv run pytest -m integration
```

**Pros:**
- Tests actual WebSocket communication
- Catches real-world issues
- Validates full flow

**Cons:**
- Slower (needs server startup)
- More complex setup
- Port conflicts possible

### Option 3: Both Approaches (Best Coverage)

Combine unit tests for handler logic with integration tests for WebSocket flow:

```
tests/
├── test_websocket_handlers.py    # Unit tests (fast)
├── test_websocket.py             # Skipped - kept as spec
└── integration/
    └── test_websocket_flow.py    # Integration tests (slower)
```

**Run separately:**
```bash
# Fast unit tests
uv run pytest tests/test_websocket_handlers.py

# Slower integration tests
uv run pytest -m integration
```

## Current Test Status

```bash
$ uv run pytest tests/ -v
================== 90 passed, 45 skipped, 0 warnings ===================
```

The 45 skipped tests are in `test_websocket.py` - they define what needs to be tested but need infrastructure.

## Recommended Path Forward

1. **Immediate**: Implement Option 1 (unit test handler logic)
   - Fast, no infrastructure changes
   - Core logic tested
   - Run with regular test suite

2. **Short-term**: Set up integration test infrastructure (Option 2)
   - Create `tests/integration/` directory
   - Add `@pytest.mark.integration` decorator
   - CI can run both unit and integration tests

3. **Keep**: Existing `test_websocket.py` as specification
   - Tests are well-structured
   - Document what integration tests should verify
   - Can be migrated to integration tests later

## Files to Create

```
app/
└── websocket_handlers.py          # Extracted handler logic

tests/
├── test_websocket_handlers.py    # Unit tests
└── integration/
    └── test_websocket_flow.py    # Integration tests
```

## References

- [python-socketio Testing](https://python-socketio.readthedocs.io/en/latest/testing.html)
- [Quart Testing](https://quart.palletsprojects.com/en/latest/testing.html)
- [AsyncClient Documentation](https://python-socketio.readthedocs.io/en/latest/api.html#socketio.AsyncClient)