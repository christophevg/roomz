# Roomz WebSocket Testing Strategy

**Date**: 2026-05-14
**Context**: Roomz I2-001 - WebSocket tests skipped

## Current Status

- **45 WebSocket tests skipped** — `AsyncServer` lacks `test_client()`
- **Documentation**: `tests/WEBSOCKET_TESTING.md`
- **Root cause**: Tests written for sync `Server` don't work with `AsyncServer`

## Problem

```python
# ❌ WRONG: AsyncServer doesn't have test_client()
client = server.socketio.test_client(server)  # AttributeError
```

## Recommended Approach

### 1. Unit Test Handler Logic

Extract WebSocket handler logic to pure functions:

```python
# app/websocket_handlers.py
def validate_session_for_connection(cookies: str, session_manager) -> dict | None:
    """Extract token and validate session. Returns user info or None."""
    token = extract_token_from_cookie(cookies)
    if not token:
        return None
    session = session_manager.validate_token(token)
    if not session or session.expires_at < datetime.now(timezone.utc):
        return None
    return {"email": session.email, "id": session.token_hash[:8]}
```

```python
# tests/test_websocket_handlers.py
def test_validate_session_valid():
    session_manager.create_session("test@example.com", ...)
    cookies = "session_token=valid_token"
    result = validate_session_for_connection(cookies, session_manager)
    assert result["email"] == "test@example.com"
```

### 2. Integration Tests with Running Server

```python
# tests/integration/test_websocket_flow.py
@pytest.mark.integration
async def test_chat_flow():
    client = socketio.AsyncClient()
    await client.connect("http://localhost:8000", headers={...})
    await client.emit("message", {"content": "Hello"})
    response = await client.receive()
    assert response["content"] == "Hello"
```

Run with: `pytest -m integration`

## Files to Create

```
app/
└── websocket_handlers.py          # Extracted handler logic

tests/
├── test_websocket_handlers.py    # Unit tests (fast)
└── integration/
    └── test_websocket_flow.py     # Integration tests (slower)
```

## Reference

See `tests/WEBSOCKET_TESTING.md` for full documentation.