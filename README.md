# Roomz

A real-time chatroom web service built with Quart (async Flask) providing WebSocket-based communication with a plugin architecture for extensible functionality.

## Overview

Roomz is a chatroom framework that provides:

- **Quart-based WebSocket API** - Real-time bidirectional communication for chat rooms/channels
- **Python client library** - Event-based client for programmatic interaction
- **Web client** - Vuetify-based UI prototype using baseweb
- **Plugin architecture** - Extensible framework for custom chatroom functionality
- **Session management** - Per-user session tracking with resume capability

## Core Components

### 1. WebSocket API Server

Pure API-based service using Quart (async Flask compatible) with WebSocket endpoints:

- Room creation, joining, and leaving
- Real-time message delivery via WebSocket
- Channel/room management
- Session lifecycle management

### 2. Python Client Library

Event-based client library for Python applications:

```python
from roomz import Client

client = Client("wss://roomz.example.com")
client.on("message", handle_message)
client.on("user_joined", handle_join)
await client.connect()
await client.join_room("general")
await client.send("Hello, World!")
```

### 3. Web Client

Vuetify-based web interface (baseweb prototype):

- Modern responsive UI
- Magic link email authentication flow:
  1. User enters email address
  2. System sends magic link via email
  3. User clicks link → authenticated
  4. Token stored in localStorage
- Real-time chat interface
- Room/channel navigation

### 4. Plugin Architecture

Generic chatroom framework with plugin system for extensibility:

```python
from roomz import Room, Plugin

class SessionPlugin(Plugin):
    def on_join(self, room, user):
        # Custom session logic
        pass

room = Room(plugins=[SessionPlugin()])
```

Built-in plugins:
- **Session Management** - Track user sessions across connections
- **Message History** - Persist and retrieve past messages
- **Presence** - Track online/offline status

### 5. Session Management

Per-user session tracking with management endpoints:

| Endpoint | Purpose |
|----------|---------|
| `/new-session` | Start a new chat session |
| `/end-session` | End current session |
| `/resume-session` | Resume a previous session |

Sessions persist across reconnections, allowing users to:
- Return to previous conversations
- Maintain context across browser sessions
- Track session history

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Web Client                        │
│              (Vuetify / Baseweb)                     │
│   ┌─────────────────────────────────────────────┐   │
│   │  Magic Link Auth │ localStorage Token       │   │
│   └─────────────────────────────────────────────┘   │
└────────────────────┬────────────────────────────────┘
                     │ WebSocket
                     ▼
┌─────────────────────────────────────────────────────┐
│              Quart WebSocket Server                  │
│  ┌─────────────┐  ┌─────────────┐  ┌────────────┐  │
│  │  Room Mgmt  │  │  Session    │  │  Plugin    │  │
│  │             │  │  Manager    │  │  System    │  │
│  └─────────────┘  └─────────────┘  └────────────┘  │
│  ┌─────────────────────────────────────────────┐   │
│  │              WebSocket Handler               │   │
│  └─────────────────────────────────────────────┘   │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│           Python Client Library                     │
│        (Event-based API wrapper)                   │
└─────────────────────────────────────────────────────┘
```

## Technology Stack

- **Server**: Quart (async Flask), Uvicorn ASGI
- **WebSocket**: Built-in Quart WebSocket support
- **Client**: Python async/await with event emitters
- **Web UI**: Vuetify 3, baseweb framework
- **Auth**: Magic link email authentication
- **Storage**: Session and message persistence (TBD: Redis/PostgreSQL)

## API Endpoints

### HTTP Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/magic-link` | Request magic link for email |
| POST | `/auth/verify` | Verify magic link token |
| POST | `/session/new` | Create new session |
| POST | `/session/end` | End current session |
| POST | `/session/resume` | Resume previous session |

### WebSocket Events

| Event | Direction | Description |
|-------|-----------|-------------|
| `join` | Client → Server | Join a room |
| `leave` | Client → Server | Leave a room |
| `message` | Bidirectional | Send/receive messages |
| `presence` | Server → Client | User join/leave notifications |
| `error` | Server → Client | Error notifications |

## Project Structure

```
roomz/
├── src/
│   └── roomz/
│       ├── __init__.py
│       ├── server/           # Quart server
│       │   ├── app.py
│       │   ├── websocket.py
│       │   └── routes/
│       ├── client/           # Python client
│       │   ├── __init__.py
│       │   └── client.py
│       ├── plugins/          # Plugin system
│       │   ├── __init__.py
│       │   ├── base.py
│       │   └── session.py
│       └── models/           # Data models
├── web/                     # Web client (baseweb)
│   └── src/
├── tests/
├── docs/
├── pyproject.toml
└── README.md
```

## Status

**Planning Phase** - Initial project setup. See TODO.md for implementation roadmap.