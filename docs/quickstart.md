# Quick Start

This guide will get you up and running with Roomz in minutes.

## Prerequisites

- Python 3.10 or higher
- An email service (Resend) or use console mode for development

## Step 1: Configuration

Create a `.env` file in your project root:

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
# EMAIL_FROM=noreply@yourdomain.com
```

### Security Notes

1. **JWT_SECRET_KEY** must be at least 32 characters (256 bits)
2. **ALLOWED_EMAILS** controls who can authenticate
3. Removing an email from ALLOWED_EMAILS immediately revokes their access
4. Session cookies are httpOnly and SameSite=Strict

## Step 2: Start the Server

```bash
# Development (with auto-reload)
uvicorn app:asgi_app --reload --host 0.0.0.0 --port 8000

# Production
gunicorn -k uvicorn.workers.UvicornWorker app:asgi_app
```

Or using the installed command:

```bash
roomz
```

## Step 3: Authentication

1. Open [http://localhost:8000](http://localhost:8000) in your browser
2. Enter your email address (must be in ALLOWED_EMAILS)
3. Click "Send Magic Link"
4. In development mode, check the server console for the magic link
5. Click the magic link to authenticate
6. You're now in the chat!

## Step 4: Chatting

- Type a message in the input field at the bottom
- Press **Enter** or click **Send**
- Messages appear instantly to all connected users
- System messages show when users join or leave

## Using the Python Client

### AsyncClient (Recommended)

```python
import asyncio
from roomz import AsyncClient

async def main():
  # Create client with session caching
  client = AsyncClient(
    server_url="http://localhost:8000",
    session_cache_file="~/.roomz/session.json"
  )

  # Register event handlers
  def on_message(data):
    print(f"{data['user']['email']}: {data['content']}")

  def on_joined(data):
    print(f"User joined: {data['user']['email']}")

  client.on("message", on_message)
  client.on("user_joined", on_joined)

  # Request magic link (for first-time auth)
  await client.login("user@example.com")
  # Check email for magic link...

  # Connect with magic link token
  await client.connect(token="your-magic-link-token")

  # Send a message
  result = await client.send("Hello, world!")
  if "error" in result:
    print(f"Failed: {result['error']}")
  else:
    print(f"Sent: {result['message_id']}")

  # Disconnect when done
  await client.disconnect()

asyncio.run(main())
```

### SyncClient (Synchronous Applications)

```python
from roomz import SyncClient

with SyncClient(server_url="http://localhost:8000", session_token="token") as client:
  client.on("message", lambda data: print(data['content']))
  result = client.send("Hello!")
```

### Context Manager Pattern

```python
from roomz import AsyncClient

async def chat():
  async with AsyncClient(server_url="http://localhost:8000", session_token="token") as client:
    client.on("message", lambda data: print(data['content']))
    await client.send("Hello!")
```

## Using the CLI

The CLI provides a terminal interface for chatting:

```bash
# Start with default server (http://localhost:8000)
roomz-cli

# Connect to custom server
roomz-cli --server http://your-server:8000
```

### CLI Commands

| Command | Description |
|---------|-------------|
| `/login <email>` | Request a magic link |
| `/token <token>` | Connect with magic link token |
| `/logout` | Disconnect and clear session |
| `/quit` | Exit the CLI |

### CLI Features

- Session caching (auto-reconnect on restart)
- Split-screen TUI with message history
- Color-coded messages (your messages in green)
- Multiline support (Enter to send, Ctrl+Enter for new line)

## Multiple Users

To test with multiple users:

1. Open multiple browser tabs/windows
2. Authenticate with different email addresses (all must be in ALLOWED_EMAILS)
3. Send messages from any tab
4. All users see messages in real-time

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `JWT_SECRET_KEY` | Yes | - | Secret key for JWT signing (min 32 chars) |
| `ALLOWED_EMAILS` | Yes | - | Comma-separated allowed emails |
| `EMAIL_SENDER` | No | `console` | Email sender: `console` or `resend` |
| `RESEND_API_KEY` | If resend | - | Resend API key |
| `EMAIL_FROM` | No | `no-reply@example.com` | Sender email address |
| `JWT_EXPIRY_DAYS` | No | `30` | JWT token lifetime in days |
| `MAGIC_LINK_EXPIRY_MINUTES` | No | `15` | Magic link lifetime in minutes |
| `MAGIC_LINK_RATE_LIMIT` | No | `5` | Max requests per email per hour |

## Next Steps

- See {doc}`api` for full client API reference
- See {doc}`server` for server deployment guide
- See {doc}`configuration` for all configuration options