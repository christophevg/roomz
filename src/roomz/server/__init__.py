"""
Roomz - Real-time Chatroom Web Service

A minimal chat application with SocketIO support for real-time message broadcasting.
"""

import asyncio
import html
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from baseweb import Baseweb
from quart import jsonify, redirect, request

# Import authentication module (for side effects)
from . import auth as auth
from .auth import (
  JWT_EXPIRY_DAYS,
  generate_jwt,
  is_email_allowed,
  is_valid_email,
  magic_link_limiter,
  magic_link_manager,
  validate_jwt,
)

# Create baseweb app with SocketIO support
server = Baseweb("roomz", settings={"main_template": "minimal.html"})  # type: ignore[no-untyped-call]

# Import email module after server is created (avoids circular import)
from .email import get_email_sender  # noqa: E402

HERE = Path(__file__).resolve().parent
server.register_stylesheet("roomz.css", HERE / "static" / "css")  # type: ignore[no-untyped-call]

# In-memory connection tracking: {sid: {email, user_id, ip, connected_at, display_name, connection_id}}
connected_clients: dict[str, dict[str, Any]] = {}

# Message sanitization constants
MAX_MESSAGE_LENGTH = 1000
MAX_CLIENTS = 1000

# Display name constraints
MAX_DISPLAY_NAME_LENGTH = 50


def validate_display_name(name: str | None) -> str | None:
  """
  Validate and sanitize display name.

  Args:
    name: Display name to validate

  Returns:
    Validated display name, or None if invalid/empty
  """
  if not name:
    return None

  # Trim whitespace
  name = name.strip()

  # Length check
  if not (1 <= len(name) <= MAX_DISPLAY_NAME_LENGTH):
    return None

  # No newlines
  if "\n" in name or "\r" in name:
    return None

  # No control characters (ASCII 0-31, except tab)
  for char in name:
    if ord(char) < 32 and char != "\t":
      return None

  # HTML escape for XSS prevention
  name = html.escape(name)

  return name


# Channel name format constant
USER_CHANNEL_FORMAT = "user:{}"


def count_user_connections(email: str) -> int:
  """
  Count the number of active connections for a specific user.

  Args:
    email: User's email address to count connections for

  Returns:
    Number of active connections for this user
  """
  return sum(1 for client in connected_clients.values() if client.get("email") == email)


async def cleanup_task() -> None:
  """
  Periodically clean up expired magic links.

  Runs every 5 minutes to prevent memory leaks from accumulating
  expired and used magic links.
  """
  while True:
    await asyncio.sleep(300)  # 5 minutes
    try:
      magic_link_manager.cleanup_expired()
      server.logger.debug("Completed periodic cleanup of expired magic links")
    except Exception as e:
      server.logger.error(f"Error during cleanup: {e}")


def extract_token_from_cookie(cookies: str) -> str | None:
  """
  Extract session token from cookie string.

  Args:
    cookies: HTTP cookie header string

  Returns:
    Session token if found, None otherwise
  """
  if not cookies:
    return None

  for cookie in cookies.split(";"):
    cookie = cookie.strip()
    if cookie.startswith("session_token="):
      return cookie.split("=", 1)[1]

  return None


# =============================================================================
# Authentication Endpoints
# =============================================================================


@server.route("/auth/request-magic-link", methods=["POST"])
async def request_magic_link() -> Any:
  """
  Request a magic link for authentication.

  Rate limited: 5 requests per email per hour
  Token lifetime: 15 minutes

  Returns:
    JSON response with status or error
  """
  try:
    data = await request.get_json()
    email = data.get("email", "").lower().strip()
    client_ip = request.remote_addr

    # Validate email
    if not is_valid_email(email):
      return jsonify(
        {
          "type": "https://roomz.local/errors/validation",
          "title": "Validation Error",
          "status": 400,
          "detail": "Invalid email format. Please enter a valid email address.",
          "instance": "/auth/request-magic-link",
        }
      ), 400

    # Check if email is allowed
    if not is_email_allowed(email):
      return jsonify(
        {
          "type": "https://roomz.local/errors/not-authorized",
          "title": "Not Authorized",
          "status": 403,
          "detail": "This email is not authorized to access this service.",
          "instance": "/auth/request-magic-link",
        }
      ), 403

    # Check rate limit
    if not magic_link_limiter.is_allowed(email, client_ip):
      return jsonify(
        {
          "type": "https://roomz.local/errors/rate-limit",
          "title": "Rate Limit Exceeded",
          "status": 429,
          "detail": "Too many requests. Please wait before requesting another magic link.",
          "instance": "/auth/request-magic-link",
        }
      ), 429

    # Generate magic link token
    token = magic_link_manager.create_magic_link(email)

    # Generate magic link URL
    magic_link_url = f"{request.host_url}auth/verify?token={token}"

    # Send magic link email
    email_sender = get_email_sender()
    email_sent = await email_sender.send_magic_link(email, magic_link_url)

    if not email_sent:
      return jsonify(
        {
          "type": "https://roomz.local/errors/email-failed",
          "title": "Email Delivery Failed",
          "status": 500,
          "detail": "Failed to send magic link email. Please try again.",
          "instance": "/auth/request-magic-link",
        }
      ), 500

    return jsonify({"status": "ok", "message": "Magic link sent. Check your email."})

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


@server.route("/auth/verify", methods=["GET"])
async def verify_magic_link() -> Any:
  """
  Verify magic link token and issue JWT.

  Tokens are single-use and expire after 15 minutes.

  Returns:
    Redirect to / on success, /?error=... on failure
  """
  token = request.args.get("token")

  if not token:
    return redirect("/?error=missing_token")

  # Validate token
  magic_link = magic_link_manager.validate_token(token)

  if not magic_link:
    return redirect("/?error=invalid_token")

  # Check if email is still allowed (double-check)
  if not is_email_allowed(magic_link.email):
    return redirect("/?error=unauthorized")

  # Generate JWT
  jwt_token = generate_jwt(magic_link.email)

  # Clean up magic link
  magic_link_manager.remove_token(magic_link.token_hash)

  # Set httpOnly cookie and redirect to chat
  # Note: secure=False for localhost development, should be True in production
  response = redirect("/")
  response.set_cookie(
    "session_token",
    jwt_token,
    httponly=True,
    secure=False,  # Set to True in production with HTTPS
    samesite="Strict",
    max_age=JWT_EXPIRY_DAYS * 24 * 3600,  # JWT_EXPIRY_DAYS in seconds
  )

  server.logger.info(f"User authenticated: {magic_link.email}")

  return response


@server.route("/auth/logout", methods=["POST"])
async def logout() -> Any:
  """
  Logout and clear JWT cookie.

  Note: JWT is stateless, so there's no server-side session to revoke.
  The client simply clears the cookie.

  Returns:
    JSON response with status
  """
  try:
    response = jsonify({"status": "ok"})
    response.delete_cookie("session_token")

    return response

  except Exception as e:
    server.logger.error(f"Error during logout: {e}")
    return jsonify(
      {
        "type": "https://roomz.local/errors/internal",
        "title": "Internal Server Error",
        "status": 500,
        "detail": "Logout failed. Please try again.",
        "instance": "/auth/logout",
      }
    ), 500


@server.route("/auth/me", methods=["GET"])
async def get_current_user() -> Any:
  """
  Get current user info from JWT.

  Returns:
    JSON response with user info or error
  """
  try:
    # Extract token from cookie
    cookies = request.headers.get("Cookie", "")
    token = extract_token_from_cookie(cookies)

    if not token:
      return jsonify(
        {
          "type": "https://roomz.local/errors/unauthorized",
          "title": "Unauthorized",
          "status": 401,
          "detail": "No session. Please authenticate.",
          "instance": "/auth/me",
        }
      ), 401

    # Validate JWT
    payload = validate_jwt(token)

    if not payload:
      return jsonify(
        {
          "type": "https://roomz.local/errors/unauthorized",
          "title": "Unauthorized",
          "status": 401,
          "detail": "Invalid or expired session. Please authenticate.",
          "instance": "/auth/me",
        }
      ), 401

    iat = payload.get("iat", 0)
    created_at_ts = iat if isinstance(iat, (int, float)) else 0
    return jsonify(
      {
        "status": "ok",
        "user": {
          "email": payload.get("email"),
          "created_at": datetime.fromtimestamp(created_at_ts, timezone.utc).isoformat(),
        },
      }
    )

  except Exception as e:
    server.logger.error(f"Error getting current user: {e}")
    return jsonify(
      {
        "type": "https://roomz.local/errors/internal",
        "title": "Internal Server Error",
        "status": 500,
        "detail": "Failed to get user info. Please try again.",
        "instance": "/auth/me",
      }
    ), 500


# =============================================================================
# WebSocket Authentication
# =============================================================================


@server.socketio.on("connect")  # type: ignore[untyped-decorator]
async def on_connect(sid: str, environ: dict[str, Any], auth_data: dict[str, Any] | None) -> bool:
  """
  Handle new client connection with JWT validation.

  JWT is extracted from httpOnly cookie and validated.

  Args:
    sid: Socket session ID (unique per connection)
    environ: WSGI environment dict
    auth_data: Optional authentication data

  Returns:
    True to accept connection, False to reject
  """
  # Extract token from cookie
  cookies = environ.get("HTTP_COOKIE", "")
  token = extract_token_from_cookie(cookies)

  if not token:
    server.logger.warning(f"Rejecting connection {sid}: no JWT token")
    return False

  # Validate JWT
  payload = validate_jwt(token)

  if not payload:
    server.logger.warning(f"Rejecting connection {sid}: invalid or expired JWT")
    return False

  # Extract user info from JWT
  email = str(payload.get("email", ""))
  if not email:
    server.logger.warning(f"Rejecting connection {sid}: JWT missing email claim")
    return False

  user_id = str(payload.get("sub", f"user:{email}"))

  # Connection limit check
  if len(connected_clients) >= MAX_CLIENTS:
    server.logger.warning(f"Rejecting connection {sid}: server at capacity")
    return False

  # Register authenticated connection
  connected_clients[sid] = {
    "email": email,
    "user_id": user_id,
    "ip": environ.get("REMOTE_ADDR"),
    "connected_at": datetime.now(timezone.utc),
    "display_name": None,  # Per-connection display name
    "connection_id": str(uuid.uuid4()),  # Unique identifier for this connection
  }

  server.logger.info(f"Client connected: {email} (total: {len(connected_clients)})")

  # Join user's private channel
  user_channel = USER_CHANNEL_FORMAT.format(email)
  await server.socketio.enter_room(sid, user_channel)

  # Send authenticated event to the connected client
  await server.socketio.emit(
    "authenticated",
    {
      "user": {"id": user_id, "email": email, "display_name": None},
      "channel": user_channel,
      "server_time": datetime.now(timezone.utc).isoformat(),
    },
    to=sid,
  )

  # Broadcast user joined event to user's private channel only
  total_connections = count_user_connections(email)
  await server.socketio.emit(
    "user_joined",
    {
      "user": {"id": user_id, "email": email, "display_name": None},
      "timestamp": datetime.now(timezone.utc).isoformat(),
      "total_connections": total_connections,
    },
    room=user_channel,
    skip_sid=sid,
  )

  return True


@server.socketio.on("disconnect")  # type: ignore[untyped-decorator]
async def on_disconnect(sid: str) -> None:
  """
  Handle client disconnection.

  Clean up in-memory tracking and notify remaining clients.

  Args:
    sid: Socket session ID of disconnected client
  """
  # Get user info before disconnecting
  client_info = connected_clients.pop(sid, None)

  if client_info:
    email = client_info.get("email")
    user_id = client_info.get("user_id")

    if email:
      server.logger.info(f"Client disconnected: {email} (total: {len(connected_clients)})")

      # Count remaining connections for this user after this disconnect
      remaining_connections = count_user_connections(email)
      user_channel = USER_CHANNEL_FORMAT.format(email)

      # Notify remaining connections in user's private channel only
      # Get display_name before removing from connected_clients
      display_name = client_info.get("display_name")
      await server.socketio.emit(
        "user_left",
        {
          "user": {"id": user_id, "email": email, "display_name": display_name},
          "timestamp": datetime.now(timezone.utc).isoformat(),
          "remaining_connections": remaining_connections,
        },
        room=user_channel,
      )


@server.socketio.on("message")  # type: ignore[untyped-decorator]
async def on_message(sid: str, data: dict[str, Any]) -> dict[str, Any]:
  """
  Receive message from client and broadcast to user's private channel.

  Args:
    sid: Socket session ID (unique per connection)
    data: Message payload {content: string}

  Returns:
    Acknowledgment with message ID and timestamp, or error dict
  """
  # Get user info from connection
  client_info = connected_clients.get(sid)
  if not client_info:
    return {"error": "Not authenticated", "code": 401}

  email = client_info.get("email")
  user_id = client_info.get("user_id")
  display_name = client_info.get("display_name")

  # Validate message structure
  if not isinstance(data, dict):
    return {"error": "Invalid message format", "code": 400}

  content = data.get("content")
  if not content or not isinstance(content, str):
    return {"error": "Missing or invalid 'content' field", "code": 400}

  # Sanitize content (basic XSS prevention)
  content = html.escape(content.strip())[:MAX_MESSAGE_LENGTH]

  # Create broadcast message with user info
  message = {
    "id": str(uuid.uuid4()),
    "user": {"id": user_id, "email": email, "display_name": display_name},
    "content": content,
    "timestamp": datetime.now(timezone.utc).isoformat(),
  }

  # Broadcast to user's private channel only
  user_channel = USER_CHANNEL_FORMAT.format(email)
  await server.socketio.emit("message", message, room=user_channel)

  # Return acknowledgment
  return {"status": "ok", "message_id": message["id"], "timestamp": message["timestamp"]}


@server.socketio.on("set_display_name")  # type: ignore[untyped-decorator]
async def on_set_display_name(sid: str, data: dict[str, Any]) -> dict[str, Any]:
  """
  Handle display name setting from client.

  Display names are per-connection and ephemeral - not stored server-side.
  Each device/session can have its own display name.

  Args:
    sid: Socket session ID
    data: {display_name: str | null}

  Returns:
    {"status": "ok", "display_name": str | null} on success
    {"error": str, "code": int} on failure
  """
  # Get client info
  client_info = connected_clients.get(sid)
  if not client_info:
    return {"error": "Not authenticated", "code": 401}

  # Validate display name
  display_name = data.get("display_name")
  validated = validate_display_name(display_name) if display_name else None

  # If name was provided but invalid, return error
  if display_name and validated is None:
    return {
      "error": f"Invalid display name: must be 1-{MAX_DISPLAY_NAME_LENGTH} characters, no newlines",
      "code": 400,
    }

  # Store display name on connection (in-memory only)
  client_info["display_name"] = validated

  # Broadcast to user's channel (same user's other connections)
  email = client_info.get("email")
  user_id = client_info.get("user_id")
  connection_id = client_info.get("connection_id")
  user_channel = USER_CHANNEL_FORMAT.format(email)

  await server.socketio.emit(
    "display_name_changed",
    {
      "user": {
        "id": user_id,
        "email": email,
        "display_name": validated,
      },
      "timestamp": datetime.now(timezone.utc).isoformat(),
      "connection_id": connection_id,
    },
    room=user_channel,
    skip_sid=sid,
  )

  return {"status": "ok", "display_name": validated}


# Import components (for side effects - registers Vue components)
from . import components as components  # noqa: E402

# Import pages (for side effects - registers routes)
from . import pages as pages  # noqa: E402


# Start cleanup task when server starts
@server.before_serving
async def startup() -> None:
  """Start background tasks when server starts."""
  asyncio.create_task(cleanup_task())


# ASGI entry point for uvicorn/gunicorn
asgi_app = server._asgi_app if server._asgi_app is not None else server

# Log configuration
server.log_config()  # type: ignore[no-untyped-call]
server.log_routes()  # type: ignore[no-untyped-call]
