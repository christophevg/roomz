# Configuration Reference

Complete reference for all Roomz configuration options.

## Environment Variables

Environment variables can be set via:

1. System environment: `export VARIABLE=value`
2. `.env` file in project root
3. Python dotenv: `python-dotenv` loads `.env` automatically

### Required Variables

#### `JWT_SECRET_KEY`

Secret key for signing JWT tokens.

| Property | Value |
|----------|-------|
| **Required** | Yes |
| **Type** | String |
| **Min Length** | 32 characters |
| **Security** | Must be cryptographically random |

**Generation:**

```bash
# Python
python -c "import secrets; print(secrets.token_urlsafe(32))"

# OpenSSL
openssl rand -base64 32

# Bash
head -c 32 /dev/urandom | base64
```

**Example:**

```bash
export JWT_SECRET_KEY="K7gNU3sdo-OL0wNhqoVWhr3g6s1xYv72ol_pe_Unols"
```

#### `ALLOWED_EMAILS`

Comma-separated list of authorized email addresses.

| Property | Value |
|----------|-------|
| **Required** | Yes |
| **Type** | String (comma-separated emails) |
| **Format** | `email1@example.com,email2@example.com` |
| **Case** | Case-insensitive (normalized to lowercase) |

**Example:**

```bash
# Single user
export ALLOWED_EMAILS="alice@example.com"

# Multiple users
export ALLOWED_EMAILS="alice@example.com,bob@example.com,charlie@example.com"

# With spaces (will be trimmed)
export ALLOWED_EMAILS="alice@example.com, bob@example.com"
```

**Security Note:** Removing an email from this list immediately revokes their access, even with a valid JWT.

---

### Email Configuration

#### `EMAIL_SENDER`

Email delivery method.

| Property | Value |
|----------|-------|
| **Required** | No |
| **Default** | `console` |
| **Values** | `console`, `resend` |

**Values:**

| Value | Description |
|-------|-------------|
| `console` | Logs magic links to console (development) |
| `resend` | Sends emails via Resend API (production) |

**Example:**

```bash
# Development
export EMAIL_SENDER=console

# Production
export EMAIL_SENDER=resend
```

#### `RESEND_API_KEY`

Resend API key for email delivery.

| Property | Value |
|----------|-------|
| **Required** | If `EMAIL_SENDER=resend` |
| **Type** | String |
| **Format** | `re_xxxxxxxxxx` |

**Example:**

```bash
export RESEND_API_KEY=re_1234567890abcdefghijklmnopqrstuv
```

**Get your key:** [resend.com](https://resend.com)

#### `EMAIL_FROM`

Sender email address for magic link emails.

| Property | Value |
|----------|-------|
| **Required** | No |
| **Default** | `no-reply@example.com` |
| **Type** | String |

**Example:**

```bash
export EMAIL_FROM=noreply@yourdomain.com
```

---

### Optional Variables

#### `JWT_EXPIRY_DAYS`

JWT token lifetime in days.

| Property | Value |
|----------|-------|
| **Required** | No |
| **Default** | `30` |
| **Type** | Integer |
| **Range** | 1-365 recommended |

**Example:**

```bash
# 7-day sessions
export JWT_EXPIRY_DAYS=7

# 90-day sessions
export JWT_EXPIRY_DAYS=90
```

#### `MAGIC_LINK_EXPIRY_MINUTES`

Magic link validity period in minutes.

| Property | Value |
|----------|-------|
| **Required** | No |
| **Default** | `15` |
| **Type** | Integer |
| **Range** | 5-60 recommended |

**Example:**

```bash
# 10-minute expiration
export MAGIC_LINK_EXPIRY_MINUTES=10
```

**Security Note:** Shorter expiration is more secure. Magic links are single-use.

#### `MAGIC_LINK_RATE_LIMIT`

Maximum magic link requests per email per hour.

| Property | Value |
|----------|-------|
| **Required** | No |
| **Default** | `5` |
| **Type** | Integer |
| **Range** | 1-20 recommended |

**Example:**

```bash
# Allow 3 requests per hour
export MAGIC_LINK_RATE_LIMIT=3
```

---

## Client Configuration

### AsyncClient Parameters

```python
from roomz import AsyncClient

client = AsyncClient(
  server_url="http://localhost:8000",  # Required: Server URL
  session_token="",                      # Optional: Magic link token
  reconnect=True,                        # Auto-reconnect on disconnect
  reconnect_delay=1.0,                   # Initial delay in seconds
  max_reconnect_attempts=5,              # Max reconnection attempts
  connection_timeout=10.0,               # Connection timeout in seconds
  session_cache_file=None,               # Cache file path for session
)
```

### SyncClient Parameters

```python
from roomz import SyncClient

client = SyncClient(
  server_url="http://localhost:8000",  # Required: Server URL
  session_token="token",                # Required: Magic link token
  reconnect=True,                       # Auto-reconnect on disconnect
  reconnect_delay=1.0,                  # Initial delay in seconds
  max_reconnect_attempts=5,             # Max reconnection attempts
  connection_timeout=10.0,              # Connection timeout in seconds
)
```

### Session Caching

Enable session caching for automatic reconnection:

```python
from pathlib import Path

client = AsyncClient(
  server_url="http://localhost:8000",
  session_cache_file=Path.home() / ".roomz" / "session.json"
)
```

**How it works:**

1. After successful authentication, session cookie is saved to file
2. On restart, client loads cached session
3. Reconnects automatically without new magic link
4. Call `client.clear_cached_session()` to logout

---

## Server Configuration

### Entry Point

The server entry point is defined in `pyproject.toml`:

```toml
[project.scripts]
roomz = "app:asgi_app"
```

### Running

```bash
# Development (hot reload)
uvicorn app:asgi_app --reload --port 8000

# Production (gunicorn)
gunicorn -k uvicorn.workers.UvicornWorker app:asgi_app --bind 0.0.0.0:8000 --workers 4

# Using installed command
roomz
```

### ASGI Application

The ASGI application is available as:

```python
from app import asgi_app

# Use with any ASGI server
# uvicorn, hypercorn, daphne, etc.
```

---

## .env File Example

Complete `.env` file example:

```bash
# =============================================================================
# REQUIRED CONFIGURATION
# =============================================================================

# JWT secret key (generate with: python -c "import secrets; print(secrets.token_urlsafe(32))")
JWT_SECRET_KEY=your-256-bit-secret-key-here-minimum-32-characters

# Allowed email addresses (comma-separated)
ALLOWED_EMAILS=alice@example.com,bob@example.com

# =============================================================================
# EMAIL CONFIGURATION
# =============================================================================

# Email sender: "console" for development, "resend" for production
EMAIL_SENDER=console

# Resend API key (required if EMAIL_SENDER=resend)
# RESEND_API_KEY=re_your_api_key_here

# Sender email address (optional)
# EMAIL_FROM=noreply@yourdomain.com

# =============================================================================
# OPTIONAL TUNING
# =============================================================================

# JWT token lifetime in days (default: 30)
# JWT_EXPIRY_DAYS=30

# Magic link expiration in minutes (default: 15)
# MAGIC_LINK_EXPIRY_MINUTES=15

# Rate limit: max requests per email per hour (default: 5)
# MAGIC_LINK_RATE_LIMIT=5
```

---

## Configuration Validation

Roomz validates configuration on startup:

### JWT_SECRET_KEY

- Must be set
- Minimum 32 characters
- Error if invalid

```python
# Error: JWT_SECRET_KEY environment variable must be set
# Error: JWT_SECRET_KEY must be at least 32 characters
```

### ALLOWED_EMAILS

- Must be set (can be empty for no access)
- Emails validated for format
- Case-insensitive matching

### Email Sender

- `console`: Logs magic links to server console
- `resend`: Requires valid `RESEND_API_KEY`

---

## Security Best Practices

### Production Checklist

- [ ] Use 256+ bit JWT secret key
- [ ] Generate secret key with `secrets.token_urlsafe(32)`
- [ ] Set `EMAIL_SENDER=resend` for production
- [ ] Configure verified `EMAIL_FROM` domain
- [ ] Use HTTPS (set cookie `secure=True`)
- [ ] Rotate JWT secret key periodically
- [ ] Audit `ALLOWED_EMAILS` regularly
- [ ] Monitor rate limit violations

### Secret Key Rotation

To rotate the JWT secret key:

1. Generate new key
2. Update environment variable
3. Restart server
4. All users will need to re-authenticate

```bash
# Generate new key
NEW_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")

# Update .env
sed -i "s/^JWT_SECRET_KEY=.*/JWT_SECRET_KEY=$NEW_KEY/" .env

# Restart server
pkill -f "uvicorn app:asgi_app"
uvicorn app:asgi_app --port 8000
```