"""
Roomz - Real-time Chatroom Web Service

A minimal chat application with SocketIO support for real-time message broadcasting.
"""

from baseweb import Baseweb
import uuid
import html
from datetime import datetime

# Create baseweb app with SocketIO support
server = Baseweb(
  "roomz",
  settings={
    "main_template": "minimal.html"
  }
)

# In-memory connection tracking
connected_clients: set[str] = set()

# Message sanitization constants
MAX_MESSAGE_LENGTH = 1000
MAX_CLIENTS = 1000


@server.socketio.on("connect")
async def on_connect(sid: str, environ: dict, auth: dict | None) -> bool:
  """
  Handle new client connection.

  No authentication in I1-001 - all connections accepted.
  Future iterations will add auth validation here.

  Args:
    sid: Socket session ID (unique per connection)
    environ: WSGI environment dict
    auth: Optional authentication data

  Returns:
    True to accept connection, False to reject
  """
  # Connection limit check
  if len(connected_clients) >= MAX_CLIENTS:
    server.logger.warning(f"Rejecting connection {sid}: server at capacity")
    return False

  connected_clients.add(sid)
  server.logger.info(f"Client connected: {sid} (total: {len(connected_clients)})")

  # Notify other clients of new connection
  await server.socketio.emit("user_joined", {
    "sid": sid,
    "timestamp": datetime.utcnow().isoformat()
  }, skip_sid=sid)

  return True


@server.socketio.on("disconnect")
async def on_disconnect(sid: str) -> None:
  """
  Handle client disconnection.

  Clean up in-memory tracking and notify remaining clients.

  Args:
    sid: Socket session ID of disconnected client
  """
  connected_clients.discard(sid)
  server.logger.info(f"Client disconnected: {sid} (total: {len(connected_clients)})")

  # Notify remaining clients
  await server.socketio.emit("user_left", {
    "sid": sid,
    "timestamp": datetime.utcnow().isoformat()
  })


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
  # Validate message structure
  if not isinstance(data, dict):
    return {"error": "Invalid message format", "code": 400}

  content = data.get("content")
  if not content or not isinstance(content, str):
    return {"error": "Missing or invalid 'content' field", "code": 400}

  # Sanitize content (basic XSS prevention)
  content = html.escape(content.strip())[:MAX_MESSAGE_LENGTH]

  # Create broadcast message
  message = {
    "id": str(uuid.uuid4()),
    "sid": sid,
    "content": content,
    "timestamp": datetime.utcnow().isoformat()
  }

  # Broadcast to all clients
  await server.socketio.emit("message", message)

  server.logger.debug(f"Broadcast message {message['id']} from {sid}")

  # Return acknowledgment
  return {
    "status": "ok",
    "message_id": message["id"],
    "timestamp": message["timestamp"]
  }


# Import pages to register routes
from . import pages  # noqa: E402, I001

# ASGI entry point for uvicorn/gunicorn
asgi_app = server._asgi_app if server._asgi_app is not None else server

# Log configuration
server.log_config()
server.log_routes()