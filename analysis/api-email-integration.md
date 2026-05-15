# API Design: Email Integration (I5-001)

**Date**: 2026-05-15
**Task**: I5-001 - Email Integration with Resend
**Status**: Design Complete

## Summary

This document describes the API design for integrating email delivery into the magic link authentication flow. The design introduces an `EmailSender` abstraction with two implementations: `ConsoleEmailSender` for development and `ResendEmailSender` for production.

## Overview

### Problem

Currently, magic links are only logged to the server console. Users cannot receive magic links via email in production.

### Solution

Create an email abstraction layer that:
1. Supports multiple email providers (Resend for production, console for development)
2. Is configurable via environment variables
3. Handles errors gracefully without breaking the authentication flow
4. Integrates cleanly with the existing `/auth/request-magic-link` endpoint

### Design Principles

- **Async-first**: All email operations are async (network I/O)
- **Fail gracefully**: Email failures should be logged but not crash the auth flow
- **Testable**: Interface allows easy mocking in tests
- **Configurable**: Environment-based provider selection

---

## EmailSender Interface

### Protocol Definition

```python
from typing import Protocol

class EmailSender(Protocol):
  """
  Protocol for email sending implementations.

  Implementations must be async and handle their own error logging.
  """

  async def send_magic_link(self, email: str, magic_link_url: str) -> bool:
    """
    Send magic link email to user.

    Args:
      email: Recipient email address
      magic_link_url: Full URL for magic link verification

    Returns:
      True if email was sent successfully, False otherwise

    Note:
      Implementations should log errors internally rather than raising.
    """
    ...
```

### Why Protocol?

Using `Protocol` instead of an abstract base class:
- Supports structural subtyping (duck typing)
- Allows third-party implementations without inheritance
- Works well with dependency injection
- Easier to mock in tests

---

## Implementations

### ConsoleEmailSender (Development)

For local development and testing, logs the magic link to console.

```python
import logging

logger = logging.getLogger(__name__)

class ConsoleEmailSender:
  """
  Development email sender that logs magic links to console.

  Used when EMAIL_SENDER=console (default for development).
  """

  async def send_magic_link(self, email: str, magic_link_url: str) -> bool:
    """
    Log magic link to console.

    Args:
      email: Recipient email address
      magic_link_url: Full URL for magic link verification

    Returns:
      Always True (logging never fails)
    """
    logger.info(
      f"\n{'=' * 60}\n"
      f"MAGIC LINK for {email}\n"
      f"{magic_link_url}\n"
      f"{'=' * 60}\n"
    )
    return True
```

**Characteristics**:
- Never fails (always returns `True`)
- Logs in same format as current implementation for backward compatibility
- No external dependencies

### ResendEmailSender (Production)

Uses Resend API for email delivery.

```python
import logging
import os

import resend

logger = logging.getLogger(__name__)

class ResendEmailSender:
  """
  Production email sender using Resend API.

  Used when EMAIL_SENDER=resend.

  Configuration:
    RESEND_API_KEY: API key for Resend (required)
    EMAIL_FROM: Sender email address (default: no-reply@yourdomain.com)
  """

  def __init__(self):
    """Initialize Resend client with API key."""
    self.api_key = os.environ.get("RESEND_API_KEY")
    self.from_address = os.environ.get(
      "EMAIL_FROM",
      "no-reply@mail.homemadebycvg.com"
    )

    if not self.api_key:
      raise ValueError(
        "RESEND_API_KEY environment variable must be set for ResendEmailSender"
      )

    resend.api_key = self.api_key

  async def send_magic_link(self, email: str, magic_link_url: str) -> bool:
    """
    Send magic link email via Resend.

    Args:
      email: Recipient email address
      magic_link_url: Full URL for magic link verification

    Returns:
      True if email was sent successfully, False otherwise
    """
    try:
      r = resend.Emails.send({
        "from": self.from_address,
        "to": email,
        "subject": "Your Magic Link for Roomz",
        "html": self._render_magic_link_html(email, magic_link_url),
      })

      logger.info(f"Magic link sent to {email} via Resend: {r['id']}")
      return True

    except Exception as e:
      logger.error(f"Failed to send magic link to {email}: {e}")
      return False

  def _render_magic_link_html(self, email: str, magic_link_url: str) -> str:
    """
    Render HTML email body for magic link.

    Args:
      email: Recipient email address
      magic_link_url: Full URL for magic link verification

    Returns:
      HTML string for email body
    """
    return f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
  <div style="background: #f9f9f9; border-radius: 8px; padding: 30px; margin-top: 20px;">
    <h1 style="color: #1976d2; margin-top: 0;">Sign in to Roomz</h1>
    <p>Hello,</p>
    <p>Click the button below to sign in to Roomz. This link will expire in <strong>15 minutes</strong>.</p>
    <p style="margin: 30px 0;">
      <a href="{magic_link_url}"
         style="background: #1976d2; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; display: inline-block;">
        Sign in to Roomz
      </a>
    </p>
    <p style="color: #666; font-size: 14px;">
      If you didn't request this link, you can safely ignore this email.
    </p>
    <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">
    <p style="color: #999; font-size: 12px;">
      This link can only be used once. If the button doesn't work, copy and paste this URL into your browser:<br>
      <code style="word-break: break-all;">{magic_link_url}</code>
    </p>
  </div>
</body>
</html>
    """.strip()
```

**Characteristics**:
- Requires `RESEND_API_KEY` environment variable
- Returns `False` on failure (logged internally)
- Uses simple HTML email template
- Includes fallback URL for email clients that don't render buttons

---

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `EMAIL_SENDER` | No | `console` | Email provider: `console` or `resend` |
| `RESEND_API_KEY` | Yes (if EMAIL_SENDER=resend) | - | Resend API key |
| `EMAIL_FROM` | No | `no-reply@yourdomain.com` | Sender email address |

### Configuration Selection

```python
import os

def get_email_sender() -> EmailSender:
  """
  Get email sender based on EMAIL_SENDER environment variable.

  Returns:
    EmailSender implementation

  Raises:
    ValueError: If EMAIL_SENDER is 'resend' but RESEND_API_KEY is not set
  """
  sender_type = os.environ.get("EMAIL_SENDER", "console").lower()

  if sender_type == "resend":
    return ResendEmailSender()
  elif sender_type == "console":
    return ConsoleEmailSender()
  else:
    raise ValueError(
      f"Invalid EMAIL_SENDER: {sender_type}. Must be 'console' or 'resend'."
    )
```

### Development vs Production

| Environment | EMAIL_SENDER | Other Requirements |
|-------------|--------------|-------------------|
| Development | `console` (default) | None |
| Staging | `resend` | `RESEND_API_KEY` |
| Production | `resend` | `RESEND_API_KEY`, `EMAIL_FROM` |

---

## Integration with Auth Flow

### Current Implementation (app/__init__.py, lines 153-163)

```python
# Generate magic link token
token = magic_link_manager.create_magic_link(email)

# Generate magic link URL
magic_link_url = f"{request.host_url}auth/verify?token={token}"

# DEVELOPMENT: Log to console
# PRODUCTION: Send email via email service
server.logger.info(f"\n{'=' * 60}\nMAGIC LINK for {email}\n{magic_link_url}\n{'=' * 60}\n")

return jsonify({"status": "ok", "message": "Magic link generated. Check server console."})
```

### Updated Implementation

```python
from .email import get_email_sender

@server.route("/auth/request-magic-link", methods=["POST"])
async def request_magic_link():
  """
  Request a magic link for authentication.
  """
  try:
    data = await request.get_json()
    email = data.get("email", "").lower().strip()
    client_ip = request.remote_addr

    # ... validation and rate limiting ...

    # Generate magic link token
    token = magic_link_manager.create_magic_link(email)

    # Generate magic link URL
    magic_link_url = f"{request.host_url}auth/verify?token={token}"

    # Send magic link email
    email_sender = get_email_sender()
    sent = await email_sender.send_magic_link(email, magic_link_url)

    if not sent:
      server.logger.error(f"Failed to send magic link to {email}")
      return jsonify(
        {
          "type": "https://roomz.local/errors/email-failed",
          "title": "Email Delivery Failed",
          "status": 500,
          "detail": "Failed to send magic link email. Please try again.",
          "instance": "/auth/request-magic-link",
        }
      ), 500

    return jsonify({
      "status": "ok",
      "message": "Magic link sent. Check your email."
    })

  except Exception as e:
    server.logger.error(f"Error creating magic link: {e}")
    return jsonify(
      {
        "type": "https://roomz.local/errors/internal",
        "title": "Internal Server Error",
        "status": 500,
        "detail": "Failed to create magic link. Please try again.",
        "instance": "/auth/request-magic-link",
      }
    ), 500
```

### Key Changes

1. Import `get_email_sender` from new `email` module
2. Call `await email_sender.send_magic_link(email, magic_link_url)`
3. Check return value and return error if email failed
4. Update success message to reflect email delivery

---

## Error Handling Strategy

### Error Types

| Error Type | HTTP Status | Scenario |
|------------|-------------|----------|
| `email-failed` | 500 | Email provider returned error |
| `internal` | 500 | Unexpected exception |

### Error Response Format (RFC 7807)

```json
{
  "type": "https://roomz.local/errors/email-failed",
  "title": "Email Delivery Failed",
  "status": 500,
  "detail": "Failed to send magic link email. Please try again.",
  "instance": "/auth/request-magic-link"
}
```

### Graceful Degradation

**ConsoleEmailSender**: Never fails, always returns `True`.

**ResendEmailSender**:
- Catches all exceptions internally
- Logs error with full context
- Returns `False` to indicate failure
- Does not raise exceptions to caller

### Retry Strategy

No automatic retry at the email sender level:
- User can click "Send Magic Link" again
- Rate limiter prevents abuse (5 requests per email per hour)
- Simple error handling keeps code maintainable

**Future Enhancement**: Add exponential backoff retry with queuing system.

---

## File Structure

```
app/
  email/
    __init__.py         # Exports get_email_sender, EmailSender
    protocol.py         # EmailSender protocol definition
    console.py          # ConsoleEmailSender implementation
    resend.py           # ResendEmailSender implementation
  auth.py               # Existing auth module
  __init__.py           # Updated to use email module
```

### Module Responsibilities

| Module | Responsibility |
|--------|---------------|
| `protocol.py` | EmailSender protocol definition |
| `console.py` | ConsoleEmailSender implementation |
| `resend.py` | ResendEmailSender implementation |
| `__init__.py` | Factory function `get_email_sender()` |

---

## Dependencies

### New Dependencies

```toml
[project.dependencies]
resend = ">=0.5.0"
```

### Optional: Async Email Support

The Resend Python SDK is synchronous. For true async support, consider:

1. **Run in thread pool** (recommended for now):
   ```python
   import asyncio
   from concurrent.futures import ThreadPoolExecutor

   executor = ThreadPoolExecutor(max_workers=4)

   async def send_magic_link(self, email: str, magic_link_url: str) -> bool:
     loop = asyncio.get_event_loop()
     return await loop.run_in_executor(
       executor,
       self._sync_send,
       email,
       magic_link_url
     )
   ```

2. **Use httpx directly** (alternative):
   - Implement async HTTP client for Resend API
   - More control but more code to maintain

**Recommendation**: Start with thread pool executor. The Resend SDK is maintained by Resend, so we get updates and fixes automatically.

---

## Testing Strategy

### Unit Tests

```python
import pytest
from unittest.mock import AsyncMock, patch

from app.email import ConsoleEmailSender, get_email_sender

class TestConsoleEmailSender:
  @pytest.mark.asyncio
  async def test_send_magic_link_returns_true(self):
    sender = ConsoleEmailSender()
    result = await sender.send_magic_link(
      "test@example.com",
      "https://example.com/auth/verify?token=abc123"
    )
    assert result is True

class TestGetEmailSender:
  def test_returns_console_by_default(self):
    with patch.dict(os.environ, {}, clear=True):
      sender = get_email_sender()
      assert isinstance(sender, ConsoleEmailSender)

  def test_returns_resend_when_configured(self):
    with patch.dict(os.environ, {"EMAIL_SENDER": "resend", "RESEND_API_KEY": "test"}):
      sender = get_email_sender()
      assert isinstance(sender, ResendEmailSender)

  def test_raises_on_invalid_sender(self):
    with patch.dict(os.environ, {"EMAIL_SENDER": "invalid"}):
      with pytest.raises(ValueError, match="Invalid EMAIL_SENDER"):
        get_email_sender()
```

### Integration Tests

```python
import pytest
from unittest.mock import patch, MagicMock

class TestResendEmailSender:
  def test_requires_api_key(self):
    with patch.dict(os.environ, {}, clear=True):
      with pytest.raises(ValueError, match="RESEND_API_KEY"):
        ResendEmailSender()

  @pytest.mark.asyncio
  async def test_send_magic_link_success(self):
    with patch.dict(os.environ, {"RESEND_API_KEY": "test-key"}):
      with patch("resend.Emails.send") as mock_send:
        mock_send.return_value = {"id": "email_123"}

        sender = ResendEmailSender()
        result = await sender.send_magic_link(
          "test@example.com",
          "https://example.com/auth/verify?token=abc123"
        )

        assert result is True
        mock_send.assert_called_once()

  @pytest.mark.asyncio
  async def test_send_magic_link_failure(self):
    with patch.dict(os.environ, {"RESEND_API_KEY": "test-key"}):
      with patch("resend.Emails.send") as mock_send:
        mock_send.side_effect = Exception("API error")

        sender = ResendEmailSender()
        result = await sender.send_magic_link(
          "test@example.com",
          "https://example.com/auth/verify?token=abc123"
        )

        assert result is False
```

---

## Security Considerations

### Email Content

- Magic link URL is single-use (validated on `/auth/verify`)
- Link expires in 15 minutes
- HTML is properly escaped (template uses variable interpolation)
- No sensitive information in email beyond the link

### Rate Limiting

- Existing rate limiter applies (5 requests per email per hour)
- Prevents email flooding attacks
- Should be sufficient for magic link authentication

### Sender Address

- `EMAIL_FROM` must be a verified sender in Resend
- Use consistent sender domain for deliverability
- Consider SPF/DKIM/DMARC for production

### Logging

- Email addresses are logged (for debugging)
- Magic link URLs are logged in development mode only
- Resend API keys are never logged

---

## Acceptance Criteria

| Criteria | Verification |
|----------|-------------|
| Development mode logs magic link to console | Manual test with `EMAIL_SENDER=console` |
| Production mode sends email via Resend | Manual test with `EMAIL_SENDER=resend` |
| Email failures return proper error response | Unit test for `send_magic_link` returning `False` |
| User receives magic link, clicks, authenticates | End-to-end test |
| Configuration is environment-based | Unit test for `get_email_sender()` |
| Resend dependency added | Check `pyproject.toml` |

---

## Action Items

1. **Create email module** (`app/email/`)
   - [ ] Create `protocol.py` with `EmailSender` protocol
   - [ ] Create `console.py` with `ConsoleEmailSender`
   - [ ] Create `resend.py` with `ResendEmailSender`
   - [ ] Create `__init__.py` with `get_email_sender()` factory

2. **Update dependencies**
   - [ ] Add `resend` to `pyproject.toml`
   - [ ] Run `uv sync`

3. **Update auth endpoint**
   - [ ] Import `get_email_sender` in `app/__init__.py`
   - [ ] Replace console logging with email sender call
   - [ ] Add error handling for email failures
   - [ ] Update success message

4. **Configuration**
   - [ ] Add `EMAIL_SENDER` to `.env.example`
   - [ ] Add `RESEND_API_KEY` to `.env.example`
   - [ ] Add `EMAIL_FROM` to `.env.example`

5. **Testing**
   - [ ] Unit tests for `ConsoleEmailSender`
   - [ ] Unit tests for `ResendEmailSender`
   - [ ] Unit tests for `get_email_sender()`
   - [ ] Integration test for auth flow with email

6. **Documentation**
   - [ ] Update README with email configuration instructions
   - [ ] Document environment variables

---

## Future Considerations

### Email Templates

For more complex emails, consider:
- Jinja2 templates
- Separate HTML and text versions
- Localization support

### Email Queuing

For high volume, consider:
- Background job queue (Celery, RQ)
- Retry with exponential backoff
- Email status tracking

### Multiple Providers

For redundancy, consider:
- Fallback email providers
- Provider health checking
- Circuit breaker pattern

### Analytics

Track:
- Email delivery rates
- Open rates (tracking pixel)
- Click rates (link tracking)
- Bounce rates