# Server Deployment Guide

This guide covers deploying and running the Roomz server.

## Server Entry Points

Roomz provides two entry points:

| Command | Description |
|---------|-------------|
| `roomz` | Start the chat server (from installed package) |
| `roomz-cli` | Start the CLI client |

## Running the Server

### Development Mode

```bash
# Using the installed command
roomz

# Or directly with uvicorn (hot reload)
uvicorn app:asgi_app --reload --host 0.0.0.0 --port 8000
```

### Production Mode

```bash
# Using gunicorn with uvicorn workers
gunicorn -k uvicorn.workers.UvicornWorker app:asgi_app --bind 0.0.0.0:8000 --workers 4

# Or directly with uvicorn
uvicorn app:asgi_app --host 0.0.0.0 --port 8000
```

### Environment Variables

Create a `.env` file or set environment variables:

```bash
# Required
export JWT_SECRET_KEY="your-256-bit-secret-key-here"
export ALLOWED_EMAILS="user1@example.com,user2@example.com"

# Email configuration
export EMAIL_SENDER="resend"  # or "console" for development
export RESEND_API_KEY="re_your_api_key_here"
export EMAIL_FROM="noreply@yourdomain.com"

# Optional tuning
export JWT_EXPIRY_DAYS="30"
export MAGIC_LINK_EXPIRY_MINUTES="15"
export MAGIC_LINK_RATE_LIMIT="5"
```

## Configuration Reference

### Required Variables

#### `JWT_SECRET_KEY`

Secret key for signing JWT tokens.

- **Required**: Yes
- **Min Length**: 32 characters (256 bits)
- **Generate with**: `python -c "import secrets; print(secrets.token_urlsafe(32))"`

```bash
export JWT_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
```

#### `ALLOWED_EMAILS`

Comma-separated list of email addresses allowed to authenticate.

- **Required**: Yes
- **Format**: `email1@example.com,email2@example.com`
- **Case-insensitive**: Emails are normalized to lowercase

```bash
export ALLOWED_EMAILS="alice@example.com,bob@example.com"
```

### Email Configuration

#### `EMAIL_SENDER`

Email sending method.

- **Values**: `console` (development) or `resend` (production)
- **Default**: `console`

```bash
# Development - logs magic links to console
export EMAIL_SENDER=console

# Production - sends via Resend
export EMAIL_SENDER=resend
```

#### `RESEND_API_KEY`

API key for Resend email service.

- **Required**: Only if `EMAIL_SENDER=resend`
- **Get from**: [resend.com](https://resend.com)

```bash
export RESEND_API_KEY=re_your_api_key_here
```

#### `EMAIL_FROM`

Sender email address for magic link emails.

- **Default**: `no-reply@example.com`
- **Required**: No, but recommended for production

```bash
export EMAIL_FROM=noreply@yourdomain.com
```

### Optional Variables

#### `JWT_EXPIRY_DAYS`

JWT token lifetime in days.

- **Default**: `30`
- **Range**: 1-365 days recommended

#### `MAGIC_LINK_EXPIRY_MINUTES`

Magic link validity period in minutes.

- **Default**: `15`
- **Security**: Shorter is more secure

#### `MAGIC_LINK_RATE_LIMIT`

Maximum magic link requests per email per hour.

- **Default**: `5`
- **Security**: Prevents spam

## Integration into Other Applications

### Quart Application

Roomz uses the Baseweb framework which is built on Quart. You can integrate Roomz into an existing Quart application:

```python
from quart import Quart
from roomz.app import server

# Create your Quart app
app = Quart(__name__)

# Import Roomz components
# Note: This approach requires careful integration

# Or run Roomz as a separate service and use the client library
```

### Using as a Library

For custom integrations, use the client library:

```python
from roomz import AsyncClient

# Connect to a Roomz server
client = AsyncClient(server_url="https://chat.yourdomain.com")
await client.connect(token="your-magic-link")
```

## Security Considerations

### JWT Security

- **Secret Key**: Use a strong, randomly-generated key (minimum 256 bits)
- **Algorithm**: HS256 (hardcoded, not configurable)
- **Storage**: httpOnly cookies prevent XSS access
- **SameSite**: Strict prevents CSRF attacks

### Magic Link Security

- **Single Use**: Tokens are invalidated after first use
- **Short Lifetime**: 15-minute default expiration
- **Rate Limited**: 5 requests per email per hour
- **Hashed Storage**: Tokens stored as SHA-256 hashes

### CORS Configuration

For production with a separate frontend:

```python
# In your Quart app configuration
# Note: Roomz uses Baseweb which handles CORS

# Configure allowed origins
ALLOWED_ORIGINS = ["https://yourdomain.com"]
```

### Production Checklist

- [ ] Set secure JWT_SECRET_KEY (256+ bits)
- [ ] Configure ALLOWED_EMAILS for all users
- [ ] Set EMAIL_SENDER=resend for production
- [ ] Configure RESEND_API_KEY
- [ ] Set EMAIL_FROM to your domain
- [ ] Enable HTTPS (set cookie secure=True)
- [ ] Configure rate limiting at reverse proxy level
- [ ] Set up logging and monitoring

## Reverse Proxy Configuration

### Nginx

```nginx
server {
    listen 443 ssl http2;
    server_name chat.yourdomain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket timeout
    proxy_read_timeout 86400;
}
```

### Caddy

```text
chat.yourdomain.com {
    reverse_proxy localhost:8000 {
        # WebSocket support
        header_up Host {host}
        header_up X-Real-IP {remote_host}
        header_up X-Forwarded-For {remote_host}
        header_up X-Forwarded-Proto {scheme}
    }
}
```

## Monitoring and Logging

Roomz logs using Python's standard logging module:

```python
import logging

# Configure logging level
logging.basicConfig(level=logging.INFO)
```

Key log messages:

- `Client connected: {email}` - User authenticated
- `Client disconnected: {email}` - User disconnected
- `User authenticated: {email}` - Magic link verified
- `Magic link created for {email}` - Link sent
- `Rejected connection {sid}` - Connection rejected

## Scaling Considerations

### Stateless Authentication

Roomz uses JWT tokens stored in httpOnly cookies, making the server stateless. This allows:

- Multiple server instances behind a load balancer
- Server restarts without losing sessions
- Horizontal scaling

### WebSocket Connections

For WebSocket scaling across multiple servers:

1. Use a Socket.IO Redis adapter
2. Configure sticky sessions at load balancer level
3. Consider connection limits per instance

### Magic Link Storage

Magic links are stored in memory by default. For production scaling:

- Replace in-memory storage with Redis
- Implement distributed rate limiting

```python
# Current: In-memory
from roomz.app.auth import magic_link_manager, magic_link_limiter

# For scaling: Implement Redis-backed versions
```

## Troubleshooting

### Common Issues

#### "JWT_SECRET_KEY environment variable must be set"

Set the environment variable:
```bash
export JWT_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
```

#### "This email is not authorized to access this service"

Add the email to ALLOWED_EMAILS:
```bash
export ALLOWED_EMAILS="user@example.com"
```

#### "Failed to send magic link email"

Check your email configuration:
- `EMAIL_SENDER=console` for development
- `EMAIL_SENDER=resend` requires valid `RESEND_API_KEY`

#### WebSocket connection fails

- Check CORS configuration
- Verify WebSocket support in reverse proxy
- Check browser console for errors