# API Analysis: Basic Broadcast Service (I1-001)

**Project**: Roomz - Real-time Chatroom Web Service
**Task**: I1-001 - Basic baseweb project setup
**Date**: 2026-05-14
**Analyst**: API Architect Agent

## 1. Overview

This document defines the backend architecture for Iteration 1, which establishes a minimal real-time broadcast service using baseweb with SocketIO. The design prioritizes simplicity and rapid iteration while establishing the foundation for future enhancements.

### Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| WebSocket library | SocketIO (not native Quart WebSocket) | Consistent with baseweb, supports reconnection, rooms built-in |
| Message handling | In-memory only, no persistence | Simplicity for iteration 1, persistence added in later iterations |
| Authentication | None (open connection) | Simplifies initial implementation, added in Iteration 2 |
| Broadcast model | All messages to all clients | No rooms yet, rooms added in Iteration 4 |

### Scope

**In Scope:**
- WebSocket connection establishment
- Message broadcast to all connected clients
- Basic message format (sender, content, timestamp)
- Connection/disconnection tracking

**Out of Scope (Future Iterations):**
- Authentication (I2-001, I2-002)
- Persistence (I7-001, I7-002)
- Rooms (I4-001, I4-002)
- Python client library (I3-001)

## 2. Application Structure

### 2.1 Directory Layout

Following the baseweb hello-world pattern:

```
roomz/
  pyproject.toml              # Project configuration with uv
  app/
    __init__.py              # Quart/baseweb app initialization
    pages/
      __init__.py
      chat/
        __init__.py          # Route registration
        chat.js              # Vue 3 component for chat UI
```

### 2.2 Module Responsibilities

| Module | Responsibility |
|--------|---------------|
| `app/__init__.py` | Baseweb initialization, SocketIO setup, connection handlers |
| `app/pages/chat/__init__.py` | Route registration for chat page |
| `app/pages/chat/chat.js` | Frontend Vue 3 component |

### 2.3 Application Factory

```python
# app/__init__.py

from baseweb import Baseweb

# Create baseweb app
server = Baseweb(
  "roomz",
  settings={
    "main_template": "minimal.html"
  }
)

# Import pages to register routes
from . import pages

# ASGI entry point
asgi_app = server._asgi_app if server._asgi_app is not None else server

# Log configuration
server.log_config()
server.log_routes()
```

## 3. SocketIO Event Handlers

### 3.1 Connection Lifecycle

| Event | Direction | Handler | Purpose |
|-------|-----------|---------|---------|
| `connect` | Client → Server | `on_connect(sid, environ, auth)` | Track new connection |
| `disconnect` | Client → Server | `on_disconnect(sid)` | Clean up connection |
| `message` | Bidirectional | `on_message(sid, data)` | Receive and broadcast messages |

### 3.2 Connection Handler

```python
# Connection tracking (in-memory)
connected_clients: set[str] = set()

@server.socketio.on("connect")
async def on_connect(sid: str, environ: dict, auth: dict | None) -> bool:
    """
    Handle new client connection.
    
    No authentication in I1-001 - all connections accepted.
    Future iterations will add auth validation here.
    """
    connected_clients.add(sid)
    server.logger.info(f"Client connected: {sid} (total: {len(connected_clients)})")
    
    # Notify other clients of new connection
    await server.socketio.emit("user_joined", {
        "sid": sid,
        "timestamp": datetime.utcnow().isoformat()
    }, skip_sid=sid)
    
    return True  # Accept connection

@server.socketio.on("disconnect")
async def on_disconnect(sid: str) -> None:
    """
    Handle client disconnection.
    
    Clean up in-memory tracking.
    """
    connected_clients.discard(sid)
    server.logger.info(f"Client disconnected: {sid} (total: {len(connected_clients)})")
    
    # Notify remaining clients
    await server.socketio.emit("user_left", {
        "sid": sid,
        "timestamp": datetime.utcnow().isoformat()
    })
```

### 3.3 Message Handler

```python
@server.socketio.on("message")
async def on_message(sid: str, data: dict) -> dict:
    """
    Receive message from client and broadcast to all connected clients.
    
    Args:
        sid: Socket session ID (unique per connection)
        data: Message payload
        
    Returns:
        Acknowledgment with message ID and timestamp
    """
    # Validate message structure
    if not isinstance(data, dict):
        return {"error": "Invalid message format"}
    
    content = data.get("content")
    if not content or not isinstance(content, str):
        return {"error": "Missing or invalid 'content' field"}
    
    # Sanitize content (basic XSS prevention)
    content = content.strip()[:1000]  # Max 1000 characters
    
    # Create broadcast message
    message = {
        "id": str(uuid.uuid4()),
        "sid": sid,
        "content": content,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    # Broadcast to all clients
    await server.socketio.emit("message", message)
    
    server.logger.debug(f"Broadcast message {message['id']} from {sid}")
    
    # Return acknowledgment
    return {
        "status": "ok",
        "message_id": message["id"],
        "timestamp": message["timestamp"]
    }
```

## 4. Message Format Specification

### 4.1 Client-to-Server Message (emit)

```javascript
// Client sends
socket.emit("message", {
  content: "Hello, world!"
});
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `content` | string | Yes | Message text (max 1000 characters) |

### 4.2 Server-to-Client Message (broadcast)

```javascript
// Server broadcasts
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "sid": "abc123",
  "content": "Hello, world!",
  "timestamp": "2026-05-14T10:30:00.000Z"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID v4 | Unique message identifier |
| `sid` | string | Socket session ID of sender |
| `content` | string | Sanitized message content |
| `timestamp` | ISO 8601 | UTC timestamp of broadcast |

### 4.3 Presence Events

```javascript
// User joined
{
  "event": "user_joined",
  "sid": "abc123",
  "timestamp": "2026-05-14T10:30:00.000Z"
}

// User left
{
  "event": "user_left",
  "sid": "abc123",
  "timestamp": "2026-05-14T10:30:00.000Z"
}
```

### 4.4 Acknowledgment Response

```javascript
// Server acknowledges successful receipt
{
  "status": "ok",
  "message_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2026-05-14T10:30:00.000Z"
}

// Error response
{
  "error": "Invalid message format"
}
```

## 5. Frontend Integration

### 5.1 Socket.IO Client Setup

The frontend connects using the standard Socket.IO client. Baseweb provides the connection setup in `socketio.js`:

```javascript
// Available globally after baseweb initializes
// window.socket is configured by baseweb's socketio.js

// Listen for messages
socket.on("message", (data) => {
  // data = { id, sid, content, timestamp }
  addMessageToChat(data);
});

// Listen for presence
socket.on("user_joined", (data) => {
  // data = { sid, timestamp }
  addSystemMessage(`User ${data.sid.substring(0, 6)} joined`);
});

socket.on("user_left", (data) => {
  addSystemMessage(`User ${data.sid.substring(0, 6)} left`);
});

// Send message
function sendMessage(content) {
  socket.emit("message", { content }, (ack) => {
    if (ack.status === "ok") {
      // Message sent successfully
    } else {
      // Handle error
      console.error("Failed to send:", ack.error);
    }
  });
}
```

### 5.2 Vue 3 Component Structure

```javascript
// app/pages/chat/chat.js

var ChatRoom = {
  name: 'ChatRoom',
  template: `
    <Page>
      <v-container fluid>
        <v-row>
          <v-col cols="12">
            <v-card>
              <v-card-title>Roomz Chat</v-card-title>
              <v-card-text>
                <div class="messages" ref="messages">
                  <div v-for="msg in messages" :key="msg.id"
                       :class="{'system-message': msg.system}">
                    <span class="timestamp">{{ formatTime(msg.timestamp) }}</span>
                    <span v-if="!msg.system" class="sender">{{ msg.sid?.substring(0,6) }}:</span>
                    <span class="content">{{ msg.content }}</span>
                  </div>
                </div>
              </v-card-text>
              <v-card-actions>
                <v-text-field v-model="input" 
                              @keyup.enter="send()"
                              placeholder="Type a message..."
                              density="compact"
                              hide-details />
                <v-btn color="primary" @click="send()">Send</v-btn>
              </v-card-actions>
            </v-card>
          </v-col>
        </v-row>
      </v-container>
    </Page>
  `,
  data() {
    return {
      messages: [],
      input: ''
    };
  },
  methods: {
    send() {
      if (!this.input.trim()) return;
      socket.emit("message", { content: this.input.trim() });
      this.input = '';
    },
    formatTime(timestamp) {
      return new Date(timestamp).toLocaleTimeString();
    }
  },
  mounted() {
    socket.on("message", (data) => {
      this.messages.push(data);
      this.$nextTick(() => {
        // Auto-scroll to bottom
        const container = this.$refs.messages;
        container.scrollTop = container.scrollHeight;
      });
    });
    socket.on("user_joined", (data) => {
      this.messages.push({
        id: `system-${Date.now()}`,
        system: true,
        content: `User joined`,
        timestamp: data.timestamp
      });
    });
    socket.on("user_left", (data) => {
      this.messages.push({
        id: `system-${Date.now()}`,
        system: true,
        content: `User left`,
        timestamp: data.timestamp
      });
    });
  }
};

app.component('ChatRoom', ChatRoom);
Navigation.add(ChatRoom);
```

## 6. Security Considerations (Open Broadcast)

### 6.1 Current Limitations (Acceptable for I1-001)

| Risk | Mitigation | Future Work |
|------|------------|-------------|
| No authentication | Accept all connections | I2-001, I2-002 add authentication |
| No rate limiting | Not needed for prototype | Add in production iteration |
| No input sanitization | Basic length check only | Full sanitization in I8-001 |
| No message validation | Basic format check | Schema validation in later iterations |
| No HTTPS enforcement | Development mode only | Production deployment adds HTTPS |

### 6.2 Basic Security Measures

```python
# Input validation
MAX_MESSAGE_LENGTH = 1000
MAX_CLIENTS = 1000  # Prevent resource exhaustion

@server.socketio.on("connect")
async def on_connect(sid, environ, auth):
    # Connection limit
    if len(connected_clients) >= MAX_CLIENTS:
        server.logger.warning(f"Rejecting connection {sid}: server full")
        raise ConnectionRefusedError("Server at capacity")
    
    # ... rest of handler
```

### 6.3 XSS Prevention

```python
import html

@server.socketio.on("message")
async def on_message(sid, data):
    content = data.get("content", "")
    # Basic HTML escape for user content
    content = html.escape(content.strip())
    # Truncate to prevent abuse
    content = content[:MAX_MESSAGE_LENGTH]
    # ...
```

### 6.4 CORS Configuration

Baseweb sets `cors_allowed_origins='*'` by default for development. This is acceptable for I1-001 but should be restricted in production:

```python
# Future: Restrict CORS in production
server = Baseweb(
  "roomz",
  settings={
    "main_template": "minimal.html",
    # CORS should be restricted in production
    # "cors_origins": ["https://roomz.example.com"]
  }
)
```

## 7. Error Handling

### 7.1 Server-Side Error Handling

```python
@server.socketio.on("message")
async def on_message(sid, data):
    try:
        # Validate input
        if not isinstance(data, dict):
            return {"error": "Invalid message format", "code": 400}
        
        content = data.get("content")
        if not content:
            return {"error": "Missing 'content' field", "code": 400}
        
        # Process message...
        
    except Exception as e:
        server.logger.error(f"Error processing message from {sid}: {e}")
        return {"error": "Internal server error", "code": 500}
```

### 7.2 Client-Side Error Handling

```javascript
socket.emit("message", { content }, (ack) => {
  if (ack.error) {
    console.error("Server error:", ack.error);
    showErrorMessage(ack.error);
  }
});

socket.on("connect_error", (error) => {
  console.error("Connection failed:", error);
  showConnectionError();
});
```

## 8. Running the Application

### 8.1 Development Server

```bash
# Install dependencies
uv sync

# Run with uvicorn (development with reload)
uv run uvicorn "app:asgi_app" --reload --host 0.0.0.0 --port 8000

# Run with gunicorn (production-like)
uv run gunicorn -w 1 -k uvicorn.workers.UvicornWorker "app:asgi_app"
```

### 8.2 pyproject.toml

```toml
[project]
name = "roomz"
version = "0.1.0"
description = "Real-time chatroom web service"
requires-python = ">=3.10"
dependencies = [
  "baseweb>=0.5.0",
  "gunicorn>=21.0.0",
  "uvicorn[standard]>=0.24.0",
]

[tool.uv.sources]
baseweb = { path = "../baseweb", editable = true }

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

### 8.3 Health Check (Future I8-004)

```python
@server.route("/health")
async def health():
    return {
        "status": "ok",
        "connections": len(connected_clients)
    }
```

## 9. Testing Strategy

### 9.1 Unit Tests

- Test message format validation
- Test connection tracking
- Test broadcast logic

### 9.2 Integration Tests

- Test WebSocket connection establishment
- Test message broadcast to multiple clients
- Test presence notifications

### 9.3 Manual Testing (Acceptance Criteria)

1. Open multiple browser tabs to `http://localhost:8000`
2. Type a message in one tab
3. Verify message appears in all tabs within 100ms
4. Verify connection/disconnection notifications

## 10. Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `baseweb` | >=0.5.0 | Web framework with SocketIO integration |
| `gunicorn` | >=21.0.0 | Production WSGI server |
| `uvicorn[standard]` | >=0.24.0 | ASGI server |
| `python-socketio` | (via baseweb) | WebSocket support |
| `quart` | (via baseweb) | Async Flask framework |

## 11. Action Items

### Implementation Tasks

- [ ] Create `pyproject.toml` with dependencies
- [ ] Create `app/__init__.py` with baseweb initialization
- [ ] Create `app/pages/chat/__init__.py` with route registration
- [ ] Create `app/pages/chat/chat.js` Vue component
- [ ] Implement `on_connect` handler with connection tracking
- [ ] Implement `on_disconnect` handler
- [ ] Implement `on_message` handler with broadcast
- [ ] Add basic input validation and sanitization
- [ ] Test with multiple browser tabs
- [ ] Verify acceptance criteria

### Future Considerations

- Authentication integration (I2-001, I2-002)
- Rooms implementation (I4-001, I4-002)
- Message persistence (I7-001, I7-002)
- Rate limiting (I8-003)
- Health/metrics endpoints (I8-004)

## 12. References

- Baseweb hello-world example: `~/Workspace/agentic/baseweb/examples/hello-world/`
- SocketIO research: `~/Workspace/agentic/baseweb/research/2026-04-30-quart-websocket-options/`
- Functional analysis: `analysis/functional.md`
- Project TODO: `TODO.md`