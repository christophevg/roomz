# Roomz

A real-time chatroom web service with instant message broadcasting.

[![License](https://img.shields.io/github/license/christophevg/roomz.svg)](https://github.com/christophevg/roomz/blob/master/LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

## What is Roomz?

Roomz is a real-time chat application that lets multiple users communicate instantly in shared chat rooms. Built with modern async technology (Quart + SocketIO), it provides seamless real-time messaging without page refreshes.

**Current Status**: Iteration 1 — Minimal working chat (authentication and rooms coming soon).

## Features

- **Instant Messaging**: Messages appear instantly across all connected users
- **Real-time Updates**: See when users join or leave
- **Responsive Design**: Works on desktop, tablet, and mobile
- **Connection Status**: Visual indicator shows when disconnected
- **Accessibility**: Keyboard navigation and screen reader support

## Quick Start

### Prerequisites

- Python 3.10 or higher
- [uv](https://docs.astral.sh/uv/) package manager

### Installation

```bash
# Clone or navigate to the project
cd /path/to/roomz

# Install dependencies
uv sync
```

### Running the Application

```bash
# Start the chat server
uv run gunicorn -k uvicorn.workers.UvicornWorker app:asgi_app

# Or for development with auto-reload:
uv run uvicorn app:asgi_app --reload --host 0.0.0.0 --port 8000
```

Open [http://localhost:8000](http://localhost:8000) in your browser.

### Testing

```bash
# Run all tests
uv run pytest tests/ -v

# Run passing tests only (some integration tests are skipped)
uv run pytest tests/test_app_structure.py tests/test_chat_page.py -v
```

## How to Use

### Basic Chat

1. Open the application in your browser
2. Start typing messages in the input field at the bottom
3. Press **Enter** or click the **Send** button
4. Your message appears instantly to all connected users

### Multiple Users

1. Open the application in multiple browser tabs or windows
2. Type messages in any tab
3. All tabs see the messages instantly
4. System messages show when users join or leave

### Mobile Access

1. Open the application on your mobile device
2. The interface adapts to your screen size
3. Touch-friendly input field and send button

## Acceptance Testing

You can verify the implementation works correctly:

**Test 1: Basic Messaging**
- Open the application in two browser tabs
- Send a message from Tab 1
- **Expected**: Message appears in both tabs instantly

**Test 2: Multiple Users**
- Open the application in three tabs
- Send messages from different tabs
- **Expected**: All messages appear in chronological order

**Test 3: Connection Status**
- Disconnect your network
- **Expected**: "Connecting to server..." warning appears
- Reconnect your network
- **Expected**: Warning disappears, messaging works

**Test 4: System Messages**
- Open a second tab
- **Expected**: First tab shows "User joined"
- Close the second tab
- **Expected**: First tab shows "User left"

**Test 5: Mobile Responsive**
- Resize browser to 320px width (or open on mobile)
- **Expected**: Chat fills full width, input is touch-friendly

## Technology Stack

| Layer | Technology |
|-------|------------|
| Backend | Quart (async Flask), SocketIO |
| Frontend | Vue 3, Vuetify 4 |
| Framework | Baseweb |
| Runtime | Python 3.10+ |
| Server | Gunicorn + Uvicorn |

## Architecture

```
Browser (Vue 3 + Vuetify 4)
    ↓ WebSocket
Quart Server + SocketIO
    ↓ In-Memory
Connected Users
```

**Current Limitations:**
- No authentication (anyone can connect)
- No message persistence (messages lost on restart)
- No rooms (all users see all messages)

These features are planned for future iterations.

## Project Structure

```
roomz/
├── app/
│   ├── __init__.py          # Quart app + SocketIO handlers
│   └── pages/chat/
│       └── chat.js          # Vue chat component
├── tests/                   # Test suite
├── analysis/                # Design documents
├── reporting/               # Task reports
├── pyproject.toml           # Project configuration
└── README.md                # This file
```

## Development

See [TODO.md](TODO.md) for planned features and [REQUIREMENTS.md](REQUIREMENTS.md) for full requirements list.

See [analysis/](analysis/) for architecture and design documentation.

## Requirements Satisfied

This iteration satisfies: R18, R22, R23, R54, R56, R57, R66, R67, R68, R69, R70

## Next Steps

Future iterations will add:
- **Iteration 2**: Authentication (secret dialog, magic links)
- **Iteration 3**: Python client library
- **Iteration 4**: Multiple chat rooms
- **Iteration 7**: Message persistence (MongoDB)

## License

[Add your license here]

## Credits

Built with:
- [Baseweb](https://github.com/christophevg/baseweb) — Web framework
- [Quart](https://pgjones.gitlab.io/quart/) — Async Flask
- [Socket.IO](https://python-socketio.readthedocs.io/) — Real-time communication
- [Vue 3](https://vuejs.org/) — Frontend framework
- [Vuetify 4](https://vuetifyjs.com/) — Material Design components

## Quick Start

### Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) package manager

### Installation

```bash
# Install dependencies
uv sync

# Install dev dependencies (for testing)
uv sync --extra dev

# Install package in editable mode
uv pip install -e .
```

### Running the Application

```bash
# Start the development server
uv run uvicorn app:asgi_app --reload --host 0.0.0.0 --port 8000
```

Then open [http://localhost:8000](http://localhost:8000) in your browser.

### Testing

```bash
# Run all passing tests
uv run pytest tests/test_app_structure.py -v

# Note: Some SocketIO and async UI tests are skipped pending
# integration test setup with actual WebSocket connections
```

### User Acceptance Testing

**Test 1: Basic Chat**
1. Open http://localhost:8000 in two browser tabs
2. Type a message in Tab 1 and press Enter
3. **Expected**: Message appears in both tabs instantly

**Test 2: System Messages**
1. Open http://localhost:8000 in Tab 1
2. Open another tab (Tab 2)
3. **Expected**: Tab 1 shows "User ... joined"
4. Close Tab 2
5. **Expected**: Tab 1 shows "User ... left"

**Test 3: Mobile Responsive**
1. Resize browser to 320px width (or open on mobile)
2. **Expected**: Chat fills full width, input is touch-friendly

## Architecture (Implemented)

```
app/
├── __init__.py         # Quart app with SocketIO handlers
│   - on_connect: Track connected clients, broadcast user_joined
│   - on_disconnect: Remove client, broadcast user_left
│   - on_message: Validate, sanitize, timestamp, broadcast to all
└── pages/
    └── chat/
        ├── __init__.py  # Route registration
        └── chat.js      # Vue 3 chat component
```