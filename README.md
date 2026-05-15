# Roomz

[![PyPI version](https://img.shields.io/pypi/v/roomz.svg)](https://pypi.org/project/roomz/)
[![PyPI downloads](https://img.shields.io/pypi/dm/roomz.svg)](https://pypistats.org/packages/roomz)
[![Python versions](https://img.shields.io/pypi/pyversions/roomz.svg)](https://pypi.org/project/roomz/)
[![License](https://img.shields.io/github/license/christophevg/roomz.svg)](https://github.com/christophevg/roomz/blob/main/LICENSE)
[![CI](https://github.com/christophevg/roomz/actions/workflows/ci.yml/badge.svg)](https://github.com/christophevg/roomz/actions/workflows/ci.yml)
[![Coverage](https://coveralls.io/repos/github/christophevg/roomz/badge.svg)](https://coveralls.io/github/christophevg/roomz)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-blue.svg)](https://github.com/astral-sh/ruff)
[![Type checked: mypy](https://img.shields.io/badge/type%20checked-mypy-blue.svg)](https://mypy.readthedocs.io/)
[![Agentic](https://img.shields.io/badge/workflow-agentic-blueviolet?style=flat-square)](https://christophe.vg/about/Coding-Agent)

A real-time chatroom web service with magic link authentication.

## What is Roomz?

Roomz is a real-time chat application with secure magic link authentication. Built with modern async technology (Quart + SocketIO), it provides seamless real-time messaging with passwordless login.

## Screenshots

| Login | Magic Link | Chat | CLI |
|-------|-------------|------|-----|
| ![Login](https://raw.githubusercontent.com/christophevg/roomz/master/media/login.png) | ![Magic Link](https://raw.githubusercontent.com/christophevg/roomz/master/media/magic-link.png) | ![Chat](https://raw.githubusercontent.com/christophevg/roomz/master/media/chat.png) | ![CLI](https://raw.githubusercontent.com/christophevg/roomz/master/media/cli.png) |

## Features

- **Magic Link Authentication**: Passwordless login via email
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

# Install dev dependencies (for testing)
uv sync --extra dev
```

### Running the Application

```bash
# Start the chat server
uv run gunicorn -k uvicorn.workers.UvicornWorker roomz.server:asgi_app

# Or for development with auto-reload:
uv run uvicorn roomz.server:asgi_app --reload --host 0.0.0.0 --port 8000
```

Open [http://localhost:8000](http://localhost:8000) in your browser.

### Configuration

Roomz uses environment variables for configuration. Create a `.env` file in the project root:

```bash
# Required: JWT secret key (minimum 32 characters)
# Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
JWT_SECRET_KEY=your-256-bit-secret-key-here

# Required: Comma-separated list of allowed email addresses
ALLOWED_EMAILS=user@example.com,other@example.com

# Email Configuration (choose one)
# Development: Log magic links to console (default)
EMAIL_SENDER=console

# Production: Send emails via Resend
# EMAIL_SENDER=resend
# RESEND_API_KEY=re_your_api_key_here
# EMAIL_FROM=noreply@yourdomain.com  # Optional, defaults to no-reply@example.com

# Optional: JWT token expiration in days (default: 30)
JWT_EXPIRY_DAYS=30

# Optional: Magic link expiration in minutes (default: 15)
MAGIC_LINK_EXPIRY_MINUTES=15

# Optional: Rate limit for magic link requests per email per hour (default: 5)
MAGIC_LINK_RATE_LIMIT=5
```

**Security Notes:**
- `JWT_SECRET_KEY` must be at least 32 characters (256 bits)
- `ALLOWED_EMAILS` controls who can authenticate
- Removing an email from `ALLOWED_EMAILS` immediately revokes their access
- Session cookies are httpOnly and SameSite=Strict

**Email Setup:**
- **Development**: Set `EMAIL_SENDER=console` (or leave unset). Magic links are logged to the server console.
- **Production**: Set `EMAIL_SENDER=resend` and provide `RESEND_API_KEY`. Get your API key from [resend.com](https://resend.com).

### Testing

```bash
# Run all tests
uv run pytest tests/ -v

# Run tests with coverage
uv run pytest --cov=src/roomz --cov-report=term-missing

# Run tests across Python versions
uv run tox
```

## How to Use

### Authentication

1. Open the application in your browser
2. Enter your email address
3. Click "Send Magic Link"
4. Check the server console for the magic link (development mode)
5. Click the magic link to authenticate
6. You're now in the chat!

### Chatting

1. After authentication, you see the chat interface
2. Type a message in the input field at the bottom
3. Press **Enter** or click the **Send** button
4. Your message appears instantly to all connected users

### Multiple Users

1. Open the application in multiple browser tabs or windows
2. Authenticate in each tab (can use same or different email)
3. Type messages in any tab
4. All tabs see the messages instantly
5. System messages show when users join or leave

## Python Client Library

Roomz includes a Python client library for programmatic access to the chat service.

### Using the CLI

The easiest way to use Roomz from the command line:

```bash
# Start the CLI
uv run roomz-cli

# Or with a custom server
uv run roomz-cli --server http://your-server:8000
```

**Commands:**
- `/login <email>` - Request a magic link
- `/token <token>` - Connect with magic link token
- `/logout` - Disconnect and clear session
- `/quit` - Exit the CLI

**Features:**
- Session caching (auto-reconnect on restart)
- Split-screen TUI with message history
- Color-coded messages (your messages in green)
- Multiline support (Enter to send, Ctrl+Enter for new line)

### Using the AsyncClient

For programmatic access in your Python applications:

```python
from roomz.client import AsyncClient

# Create client with session caching
client = AsyncClient(
  server_url="http://localhost:8000",
  session_cache_file="~/.roomz/session.json"
)

# Register event handlers
client.on("message", lambda data: print(f"{data['user']['email']}: {data['content']}"))
client.on("user_joined", lambda data: print(f"{data['user']['email']} joined"))

# Request magic link
await client.login("user@example.com")

# Connect with magic link token
await client.connect(token="magic-link-token")

# Or reconnect with cached session
await client.connect()

# Send message
result = await client.send("Hello, world!")
if "error" in result:
  print(f"Failed: {result['error']}")

# Disconnect
await client.disconnect()
client.clear_cached_session()
```

### Using the SyncClient

For synchronous applications:

```python
from roomz.client import SyncClient

with SyncClient(server_url="http://localhost:8000", session_token="token") as client:
  client.on("message", lambda data: print(data['content']))
  result = client.send("Hello!")
```

### Session Caching

The client can cache session cookies for automatic reconnection:

```python
# Enable caching (recommended for CLI apps)
client = AsyncClient(
  server_url="http://localhost:8000",
  session_cache_file=Path.home() / ".roomz" / "session.json"
)

# Disable caching (default)
client = AsyncClient(server_url="http://localhost:8000")
```

## Technology Stack

| Layer | Technology |
|-------|------------|
| Backend | Quart (async Flask), SocketIO |
| Frontend | Vue 3, Vuetify 4 |
| Framework | Baseweb |
| Runtime | Python 3.10+ |
| Server | Gunicorn + Uvicorn |
| Auth | Magic links with httpOnly cookies |

## Architecture

```
Browser (Vue 3 + Vuetify 4)
    ↓ HTTP POST /auth/request-magic-link
    Magic Link Email (or console in dev)
    ↓ HTTP GET /auth/verify?token=...
    JWT Cookie Set (httpOnly, SameSite=Strict)
    ↓ WebSocket with JWT cookie auth
Quart Server + SocketIO
    ↓ JWT Validation + ALLOWED_EMAILS check
Connected Users
```

**Stateless Authentication**: Sessions use JWT tokens, enabling server restarts without losing sessions. Access is controlled by the `ALLOWED_EMAILS` environment variable.

## Project Structure

```
roomz/
├── src/roomz/
│   ├── server/             # Server application
│   │   ├── __init__.py     # Quart app + SocketIO + Auth endpoints
│   │   ├── auth.py         # Magic link and session management
│   │   ├── models.py       # Session and magic link models
│   │   ├── components/     # Vue components
│   │   ├── pages/          # Page modules
│   │   └── static/         # CSS styles
│   ├── client/             # Python client library
│   │   ├── async_client.py # AsyncClient implementation
│   │   ├── sync_client.py  # SyncClient wrapper
│   │   ├── events.py       # Event emitter
│   │   └── exceptions.py   # Client exceptions
│   └── cli/                # Command-line interface
│       ├── app_tui.py      # Textual TUI application
│       └── styles/         # TUI stylesheets
├── tests/                  # Test suite
├── analysis/               # Design documents
├── reporting/              # Task reports
├── pyproject.toml          # Project configuration
└── README.md               # This file
```

## Development

See [TODO.md](TODO.md) for planned features and [REQUIREMENTS.md](REQUIREMENTS.md) for full requirements list.

## License

MIT License - See [LICENSE](LICENSE) for details.

## Credits

Built with:
- [Baseweb](https://github.com/christophevg/baseweb) — Web framework
- [Quart](https://pgjones.gitlab.io/quart/) — Async Flask
- [Socket.IO](https://python-socketio.readthedocs.io/) — Real-time communication
- [Vue 3](https://vuejs.org/) — Frontend framework
- [Vuetify 4](https://vuetifyjs.com/) — Material Design components