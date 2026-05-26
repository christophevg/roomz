# Roomz

> Real-time chatroom web service with magic link authentication

## Overview

Roomz is a Python package providing a real-time chat application with secure magic link authentication. It includes both a web server built with Quart/SocketIO and a Python client library for programmatic access. The package features passwordless authentication via email magic links, instant messaging across all connected users, and both async and synchronous client implementations.

## Installation

```bash
pip install roomz
```

For development:

```bash
pip install roomz[dev]
```

## Quick Start

### Server Setup

```bash
# Set required environment variables
export JWT_SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
export ALLOWED_EMAILS=user@example.com
export EMAIL_SENDER=console  # Development mode

# Start the server
roomz
# Or with uvicorn for development
uvicorn roomz.server:asgi_app --reload --host 0.0.0.0 --port 8000
```

### Python Client (Async)

```python
from roomz.client import AsyncClient

async with AsyncClient(config={"server_url": "http://localhost:8000"}) as client:
    # Register event handlers
    client.on("message", lambda data: print(f"{data['user']['email']}: {data['content']}"))
    client.on("user_joined", lambda data: print(f"{data['user']['email']} joined"))

    # Request magic link
    await client.login("user@example.com")

    # Connect with magic link token
    await client.connect(token="magic-link-token")

    # Send message
    await client.send("Hello, world!")

    # Disconnect
    await client.disconnect()
```

### Python Client (Sync)

```python
from roomz.client import SyncClient

with SyncClient(config={"server_url": "http://localhost:8000"}, session_token="token") as client:
    client.on("message", lambda data: print(data['content']))
    result = client.send("Hello!")
    if "error" in result:
        print(f"Failed: {result['error']}")
```

### CLI Interface

```bash
# Start CLI with auto-discovered config
roomz-cli

# Start CLI with specific server
roomz-cli --server http://localhost:8000
```

CLI commands:
- `/login <email>` - Request a magic link
- `/token <token>` - Connect with magic link token
- `/name <name>` - Set display name
- `/logout` - Disconnect and clear session
- `/quit` - Exit the CLI

## Key Components

### AsyncClient

The primary async WebSocket client for Roomz real-time chat.

**Key Features:**
- Automatic configuration discovery from environment variables and config files
- Session caching for automatic reconnection
- Event-driven architecture with handlers for `message`, `user_joined`, `user_left`, `connected`, `disconnected`, and `error` events
- Automatic reconnection with configurable backoff
- Display name support

**Configuration Priority:**
1. Explicit `config` parameter (highest)
2. Explicit `config_path` parameter
3. Prefixed environment variable (e.g., `DEV_ROOMZ_SERVER_URL`)
4. Unprefixed environment variable (e.g., `ROOMZ_SERVER_URL`)
5. `./roomz.toml` (current directory)
6. `~/.roomz.toml` (user home directory)
7. Default Config() (lowest)

```python
from roomz.client import AsyncClient, Config

# Explicit configuration
config = Config(server_url="http://localhost:5000", display_name="Alice")
client = AsyncClient(config=config)

# Config file
client = AsyncClient(config_path="~/.roomz.toml")

# Auto-discovery
client = AsyncClient()

# With session caching
client = AsyncClient(
    session_cache_file="~/.roomz/session.json",
    reconnect=True,
    reconnect_delay=1.0,
    max_reconnect_attempts=5
)
```

### SyncClient

Synchronous wrapper around AsyncClient with background thread management.

```python
from roomz.client import SyncClient

# Context manager auto-connects/disconnects
with SyncClient(session_token="token") as client:
    client.on("message", handler)
    client.send("Hello!")
```

### Config

Configuration management with auto-discovery from multiple sources.

```python
from roomz.client.config import Config

# Explicit config
config = Config(server_url="http://localhost:5000", display_name="Alice")

# Load from file
config = Config.load("~/.roomz.toml")

# Auto-discover
config, path = Config.auto_discover()
```

**Environment Variables:**
- `ROOMZ_SERVER_URL` - Server URL
- `ROOMZ_DISPLAY_NAME` - Display name
- `ROOMZ_PREFIX` - Environment variable prefix (e.g., "DEV" → "DEV_ROOMZ_*")

**Config File Format** (`~/.roomz.toml`):
```toml
[client]
server_url = "http://localhost:5000"
display_name = "Alice"
```

### Server

Quart web application with SocketIO support for real-time messaging.

**Entry Point:**
```python
from roomz.server import asgi_app
# asgi_app is the Quart application ready for deployment
```

**Key Features:**
- Magic link authentication
- JWT session management with httpOnly cookies
- Real-time message broadcasting
- User presence tracking
- Display name support
- Channel-based messaging (private user channels)

## Common Patterns

### Session Caching

Enable session caching for automatic reconnection:

```python
from pathlib import Path
from roomz.client import AsyncClient

client = AsyncClient(
    config=Config(server_url="http://localhost:8000"),
    session_cache_file=Path.home() / ".roomz" / "session.json"
)

# Session is automatically cached after successful connection
await client.connect(token="magic-link-token")

# On restart, cached session is used
await client.connect()  # No token needed - uses cache
```

### Display Names

Set a custom display name that appears in chat messages:

```python
# Set display name
await client.set_display_name("Alice")
# Messages show as: "Alice (alice@example.com)"

# Clear display name
await client.set_display_name(None)
# Messages show as: "alice@example.com"
```

Or via environment variable:
```bash
export ROOMZ_DISPLAY_NAME="Alice"
```

Or via config file:
```toml
[client]
display_name = "Alice"
```

### Event Handling

```python
from roomz.client import AsyncClient

client = AsyncClient()

# Connection events
client.on("connected", lambda: print("Connected!"))
client.on("disconnected", lambda: print("Disconnected"))

# Message events
client.on("message", lambda data: print(f"{data['user']['email']}: {data['content']}"))

# Presence events
client.on("user_joined", lambda data: print(f"{data['user']['email']} joined"))
client.on("user_left", lambda data: print(f"{data['user']['email']} left"))

# Error events
client.on("error", lambda data: print(f"Error: {data['error']}"))
```

### Reconnection

```python
client = AsyncClient(
    config=Config(server_url="http://localhost:8000"),
    reconnect=True,
    reconnect_delay=1.0,
    max_reconnect_attempts=5,
    connection_timeout=10.0
)
```

### Environment-Based Configuration

Multiple environments with prefix:

```bash
# Development
export ROOMZ_PREFIX=DEV
export DEV_ROOMZ_SERVER_URL=http://localhost:8000

# Production
export ROOMZ_PREFIX=PROD
export PROD_ROOMZ_SERVER_URL=https://chat.example.com
```

## Dependencies

**Core:**
- `baseweb>=0.5.2` - Web framework
- `gunicorn>=21.0.0` - WSGI server
- `uvicorn[standard]>=0.24.0` - ASGI server
- `python-socketio[asyncio]>=5.10.0` - WebSocket support
- `aiohttp>=3.9.0` - Async HTTP client
- `rich>=13.0.0` - Terminal output
- `textual>=0.47.0` - TUI framework
- `resend>=2.30.1` - Email service
- `PyJWT>=2.8.0` - JWT tokens
- `python-dotenv>=1.2.2` - Environment variables

**Optional:**
- `tomli>=2.0.0` - TOML parsing (Python < 3.11)

**Development:**
- `pytest>=8.0.0` - Testing
- `pytest-asyncio>=0.23.0` - Async test support
- `pytest-cov>=5.0.0` - Coverage
- `mypy>=1.13.0` - Type checking
- `ruff>=0.8.0` - Linting

## Version Notes

**Current Version:** 0.2.0

**Version History:**
- **0.2.0** - Current release with display names, configuration discovery, and session caching
- **0.1.2** - Initial stable release with async/sync clients and CLI

## References

- **Homepage:** https://github.com/christophevg/roomz
- **Documentation:** https://github.com/christophevg/roomz#readme
- **Repository:** https://github.com/christophevg/roomz
- **Issues:** https://github.com/christophevg/roomz/issues
- **PyPI:** https://pypi.org/project/roomz/

## Entry Points

The package provides two CLI entry points:

1. **`roomz`** - Start the chat server
   ```bash
   roomz  # Starts gunicorn with uvicorn worker
   ```

2. **`roomz-cli`** - Start the CLI client
   ```bash
   roomz-cli [--server URL]
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

## Security

- JWT tokens require minimum 32-character secret key (256 bits)
- Session cookies are httpOnly and SameSite=Strict
- Email access control via `ALLOWED_EMAILS` environment variable
- Rate limiting for magic link requests (default: 5 per hour per email)
- Magic link expiration (default: 15 minutes)
- JWT token expiration (default: 30 days)

## License

MIT License