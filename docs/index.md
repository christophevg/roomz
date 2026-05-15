# Roomz Documentation

> Real-time chatroom web service with magic link authentication

[![PyPI version](https://img.shields.io/pypi/v/roomz.svg)](https://pypi.org/project/roomz/)
[![Python versions](https://img.shields.io/pypi/pyversions/roomz.svg)](https://pypi.org/project/roomz/)
[![License](https://img.shields.io/github/license/christophevg/roomz.svg)](https://github.com/christophevg/roomz/blob/main/LICENSE)
[![Documentation Status](https://readthedocs.org/projects/roomz/badge/?version=latest)](https://roomz.readthedocs.io/en/latest/?badge=latest)

## What is Roomz?

Roomz is a real-time chat application with secure magic link authentication. Built with modern async technology (Quart + SocketIO), it provides:

- **Passwordless authentication** via magic links sent by email
- **Real-time messaging** with instant delivery across all connected clients
- **WebSocket-powered communication** using Socket.IO
- **User-owned private channels** for secure, isolated messaging
- **Session management** with JWT tokens stored in httpOnly cookies
- **CLI and Python client libraries** for programmatic access

## Key Features

- **Magic Link Authentication**: Passwordless login via email
- **Instant Messaging**: Messages appear instantly across all connected users
- **Real-time Updates**: See when users join or leave
- **Connection Status**: Visual indicator shows when disconnected
- **Session Caching**: Client library caches sessions for automatic reconnection
- **Rate Limiting**: Protection against magic link spam
- **Private Channels**: Each user gets their own isolated messaging channel

## Installation

```bash
pip install roomz
```

For development:

```bash
pip install roomz[dev]
```

## Quick Start

### Running the Server

```bash
# Set required environment variables
export JWT_SECRET_KEY="your-256-bit-secret-key-here"
export ALLOWED_EMAILS="user@example.com,other@example.com"

# Start the server
roomz

# Or with gunicorn for production
gunicorn -k uvicorn.workers.UvicornWorker app:asgi_app
```

Open [http://localhost:8000](http://localhost:8000) in your browser.

### Using the Python Client

```python
from roomz import AsyncClient

# Create client with session caching
client = AsyncClient(
  server_url="http://localhost:8000",
  session_cache_file="~/.roomz/session.json"
)

# Register event handlers
client.on("message", lambda data: print(f"{data['user']['email']}: {data['content']}"))
client.on("user_joined", lambda data: print(f"{data['user']['email']} joined"))

# Connect and authenticate
await client.connect(token="magic-link-token")

# Send a message
result = await client.send("Hello, world!")
```

### Using the CLI

```bash
# Start the CLI
roomz-cli

# Or with a custom server
roomz-cli --server http://your-server:8000
```

**CLI Commands:**

- `/login <email>` - Request a magic link
- `/token <token>` - Connect with magic link token
- `/logout` - Disconnect and clear session
- `/quit` - Exit the CLI

## Architecture

```
Browser (Vue 3 + Vuetify 4)
    | HTTP POST /auth/request-magic-link
    v
Magic Link Email (or console in dev)
    | HTTP GET /auth/verify?token=...
    v
JWT Cookie Set (httpOnly, SameSite=Strict)
    | WebSocket with JWT cookie auth
    v
Quart Server + SocketIO
    | JWT Validation + ALLOWED_EMAILS check
    v
User's Private Channel (user:{email})
```

**Key Security Features:**

- Stateless authentication with JWT tokens
- httpOnly, SameSite=Strict cookies
- Magic links are single-use and expire in 15 minutes
- Rate limiting on magic link requests (5 per email per hour)
- Server-side validation of ALLOWED_EMAILS on every request

## Contents

```{toctree}
:maxdepth: 2
:caption: Documentation

installation
quickstart
api
server
configuration
```

```{toctree}
:maxdepth: 1
:caption: Development

contributing
changelog
```

## Links

- **Repository**: <https://github.com/christophevg/roomz>
- **Issues**: <https://github.com/christophevg/roomz/issues>
- **PyPI**: <https://pypi.org/project/roomz/>

## License

MIT License - See [LICENSE](https://github.com/christophevg/roomz/blob/main/LICENSE) for details.