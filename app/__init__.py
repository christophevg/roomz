"""
Roomz - Real-time Chatroom Web Service

A minimal chat application with SocketIO support for real-time message broadcasting.
"""

import asyncio
import hashlib
import html
import uuid
from datetime import datetime, timezone
from pathlib import Path

from baseweb import Baseweb
from quart import jsonify, redirect, request

# Import authentication module (for side effects)
from . import auth as auth
from .auth import (
  SESSION_TIMEOUT_DAYS,
  is_valid_email,
  magic_link_limiter,
  magic_link_manager,
  session_manager,
)

# Create baseweb app with SocketIO support
server = Baseweb("roomz", settings={"main_template": "minimal.html"})

HERE = Path(__file__).resolve().parent
server.register_stylesheet("roomz.css", HERE / "static" / "css")

# In-memory connection tracking: {sid: {session: Session, ip: str, connected_at: datetime}}
connected_clients: dict = {}

# Message sanitization constants
MAX_MESSAGE_LENGTH = 1000
MAX_CLIENTS = 1000


async def cleanup_task():
  """
  Periodically clean up expired sessions and magic links.

  Runs every 5 minutes to prevent memory leaks from accumulating
  expired sessions and used magic links.
  """
  while True:
    await asyncio.sleep(300)  # 5 minutes
    try:
      session_manager.cleanup_expired()
      magic_link_manager.cleanup_expired()
      server.logger.debug("Completed periodic cleanup of expired sessions and magic links")
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
async def request_magic_link():
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

    # DEVELOPMENT: Log to console
    # PRODUCTION: Send email via email service
    server.logger.info(f"\n{'=' * 60}\nMAGIC LINK for {email}\n{magic_link_url}\n{'=' * 60}\n")

    return jsonify({"status": "ok", "message": "Magic link generated. Check server console."})

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
async def verify_magic_link():
  """
  Verify magic link token and create session.

  Tokens are single-use and expire after 15 minutes.

  Returns:
    Redirect to /chat on success, /?error=... on failure
  """
  token = request.args.get("token")

  if not token:
    return redirect("/?error=missing_token")

  # Validate token
  magic_link = magic_link_manager.validate_token(token)

  if not magic_link:
    return redirect("/?error=invalid_token")

  # Create session
  client_ip = request.remote_addr
  user_agent = request.headers.get("User-Agent", "")
  user_agent_hash = hashlib.sha256(user_agent.encode()).hexdigest()

  session_data = session_manager.create_session(
    email=magic_link.email, client_ip=client_ip, user_agent_hash=user_agent_hash
  )

  # Clean up magic link
  magic_link_manager.remove_token(magic_link.token_hash)

  # Set httpOnly cookie and redirect to chat
  # Note: secure=False for localhost development, should be True in production
  response = redirect("/")
  response.set_cookie(
    "session_token",
    session_data["token"],
    httponly=True,
    secure=False,  # Set to True in production with HTTPS
    samesite="Strict",
    max_age=SESSION_TIMEOUT_DAYS * 24 * 3600,  # SESSION_TIMEOUT_DAYS in seconds
  )

  server.logger.info(f"User authenticated: {magic_link.email}")

  return response


@server.route("/auth/logout", methods=["POST"])
async def logout():
  """
  Logout and clear session.

  Returns:
    JSON response with status
  """
  try:
    # Extract token from cookie
    cookies = request.headers.get("Cookie", "")
    token = extract_token_from_cookie(cookies)

    if token:
      session_manager.revoke_session(token)

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
async def get_current_user():
  """
  Get current user info.

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

    # Validate session
    session = session_manager.validate_token(token)

    if not session:
      return jsonify(
        {
          "type": "https://roomz.local/errors/unauthorized",
          "title": "Unauthorized",
          "status": 401,
          "detail": "Invalid or expired session. Please authenticate.",
          "instance": "/auth/me",
        }
      ), 401

    return jsonify(
      {
        "status": "ok",
        "user": {"email": session.email, "created_at": session.created_at.isoformat()},
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


@server.socketio.on("connect")
async def on_connect(sid: str, environ: dict, auth_data: dict | None) -> bool:
  """
  Handle new client connection with session validation.

  Session token is extracted from httpOnly cookie.

  Args:
    sid: Socket session ID (unique per connection)
    environ: WSGI environment dict
    auth: Optional authentication data

  Returns:
    True to accept connection, False to reject
  """
  # Extract token from cookie
  cookies = environ.get("HTTP_COOKIE", "")
  token = extract_token_from_cookie(cookies)

  if not token:
    server.logger.warning(f"Rejecting connection {sid}: no session token")
    return False

  # Validate session
  session = session_manager.validate_token(token)

  if not session:
    server.logger.warning(f"Rejecting connection {sid}: invalid or expired token")
    return False

  # Check session expiration
  if datetime.now(timezone.utc) > session.expires_at:
    server.logger.warning(f"Rejecting connection {sid}: session expired")
    return False

  # Connection limit check
  if len(connected_clients) >= MAX_CLIENTS:
    server.logger.warning(f"Rejecting connection {sid}: server at capacity")
    return False

  # Register authenticated connection
  connected_clients[sid] = {
    "session": session,
    "ip": environ.get("REMOTE_ADDR"),
    "connected_at": datetime.now(timezone.utc),
  }

  server.logger.info(f"Client connected: {session.email} (total: {len(connected_clients)})")

  # Send authenticated event to the connected client
  await server.socketio.emit(
    "authenticated",
    {
      "user": {"id": session.token_hash[:8], "email": session.email},
      "server_time": datetime.now(timezone.utc).isoformat(),
    },
    to=sid,
  )

  # Broadcast with user info
  await server.socketio.emit(
    "user_joined",
    {
      "user": {"id": session.token_hash[:8], "email": session.email},
      "timestamp": datetime.now(timezone.utc).isoformat(),
    },
    skip_sid=sid,
  )

  return True


@server.socketio.on("disconnect")
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
    session = client_info.get("session")
    if session:
      server.logger.info(f"Client disconnected: {session.email} (total: {len(connected_clients)})")
      # Notify remaining clients with user email
      await server.socketio.emit(
        "user_left",
        {
          "user": {"id": session.token_hash[:8], "email": session.email},
          "timestamp": datetime.now(timezone.utc).isoformat(),
        },
      )


@server.socketio.on("message")
async def on_message(sid: str, data: dict) -> dict:
  """
  Receive message from client and broadcast to all connected clients.

  Args:
    sid: Socket session ID (unique per connection)
    data: Message payload {content: string}

  Returns:
    Acknowledgment with message ID and timestamp, or error dict
  """
  # Get user info from session
  client_info = connected_clients.get(sid)
  if not client_info:
    return {"error": "Not authenticated", "code": 401}

  session = client_info.get("session")

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
    "user": {"id": session.token_hash[:8], "email": session.email},
    "content": content,
    "timestamp": datetime.now(timezone.utc).isoformat(),
  }

  # Broadcast to all clients
  await server.socketio.emit("message", message)

  # Return acknowledgment
  return {"status": "ok", "message_id": message["id"], "timestamp": message["timestamp"]}


# Import components (for side effects - registers Vue components)
from . import components as components  # noqa: E402

# Import pages (for side effects - registers routes)
from . import pages as pages  # noqa: E402


# Start cleanup task when server starts
@server.before_serving
async def startup():
  """Start background tasks when server starts."""
  asyncio.create_task(cleanup_task())


# ASGI entry point for uvicorn/gunicorn
asgi_app = server._asgi_app if server._asgi_app is not None else server

# Log configuration
server.log_config()
server.log_routes()
