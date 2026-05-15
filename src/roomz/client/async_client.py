"""
Async Client

Primary async WebSocket client implementation for Roomz.
"""

import asyncio
import json
import logging
import random
from pathlib import Path

import aiohttp
import socketio
from yarl import URL

from roomz.client.events import EventEmitter, EventHandler
from roomz.client.exceptions import AuthenticationError, ConnectionError
from roomz.client.state import ConnectionState

logger = logging.getLogger(__name__)


class AsyncClient:
  """
  Async WebSocket client for Roomz real-time chat.

  Usage:
    async with AsyncClient(server_url, session_token) as client:
      client.on('message', handle_message)
      await client.send("Hello, world!")

  Authentication Flow:
    1. Shared aiohttp.ClientSession is used for HTTP and WebSocket
    2. Call /auth/verify?token=xxx to get session cookie
    3. Cookie is automatically passed to WebSocket connection
  """

  def __init__(
    self,
    server_url: str,
    session_token: str = "",
    *,
    reconnect: bool = True,
    reconnect_delay: float = 1.0,
    max_reconnect_attempts: int = 5,
    connection_timeout: float = 10.0,
    session_cache_file: str | Path | None = None,
  ):
    """
    Initialize async client.

    Args:
      server_url: WebSocket server URL (e.g., "http://localhost:5000")
      session_token: Magic link token for authentication (optional if session_cache_file is set)
      reconnect: Enable automatic reconnection (default: True)
      reconnect_delay: Initial delay between reconnection attempts in seconds (default: 1.0)
      max_reconnect_attempts: Maximum reconnection attempts (default: 5)
      connection_timeout: Timeout for connection in seconds (default: 10.0)
      session_cache_file: Path to cache session cookie (None to disable caching)
    """
    self._server_url = server_url
    self._session_token = session_token
    self._reconnect = reconnect
    self._reconnect_delay = reconnect_delay
    self._max_reconnect_attempts = max_reconnect_attempts
    self._connection_timeout = connection_timeout
    self._session_cache_file = Path(session_cache_file) if session_cache_file else None

    self._connection_state = ConnectionState.DISCONNECTED
    self._user: dict | None = None
    self._session: aiohttp.ClientSession | None = None
    self._sio: socketio.AsyncClient | None = None
    self._events = EventEmitter()
    self._reconnect_attempts = 0

  @property
  def connected(self) -> bool:
    """True if WebSocket is connected and authenticated."""
    return self._connection_state == ConnectionState.CONNECTED

  @property
  def user(self) -> dict | None:
    """Current user info: {'id': str, 'email': str} or None if not authenticated."""
    return self._user

  @property
  def connection_state(self) -> ConnectionState:
    """Current connection state."""
    return self._connection_state

  def on(self, event: str, handler: EventHandler) -> None:
    """
    Register event handler.

    Args:
      event: Event name ('authenticated', 'message', 'user_joined',
              'user_left', 'disconnect', 'error')
      handler: Callback function receiving event data (sync or async)
    """
    self._events.on(event, handler)

  def off(self, event: str, handler: EventHandler | None = None) -> None:
    """
    Unregister event handler.

    Args:
      event: Event name
      handler: Specific handler to remove, or None to remove all handlers for event
    """
    self._events.off(event, handler)

  async def login(self, email: str) -> bool:
    """
    Request a magic link for authentication.

    Args:
      email: User email address

    Returns:
      True if magic link was requested successfully

    Raises:
      ConnectionError: If request fails
    """
    if not self._session:
      self._session = aiohttp.ClientSession()

    url = f"{self._server_url}/auth/request-magic-link"
    try:
      async with self._session.post(url, json={"email": email}) as resp:
        if resp.status == 200:
          return True
        else:
          data = await resp.json()
          raise ConnectionError(f"Failed to request magic link: {data.get('detail', 'Unknown error')}")
    except Exception as e:
      raise ConnectionError(f"Failed to request magic link: {e}") from e

  def _save_session_cookie(self, cookie_value: str) -> None:
    """Save session cookie to cache file."""
    if not self._session_cache_file:
      return

    try:
      self._session_cache_file.parent.mkdir(parents=True, exist_ok=True)
      with open(self._session_cache_file, "w") as f:
        json.dump(
          {"session_cookie": cookie_value, "server": self._server_url}, f
        )
    except Exception as e:
      logger.warning(f"Failed to save session cookie: {e}")

  def _load_session_cookie(self) -> str | None:
    """Load session cookie from cache file."""
    if not self._session_cache_file or not self._session_cache_file.exists():
      return None

    try:
      with open(self._session_cache_file) as f:
        data = json.load(f)
        # Only use cookie if server matches
        if data.get("server") == self._server_url:
          cookie = data.get("session_cookie")
          return str(cookie) if cookie else None
    except Exception as e:
      logger.warning(f"Failed to load session cookie: {e}")

    return None

  def clear_cached_session(self) -> None:
    """Clear cached session cookie."""
    if self._session_cache_file and self._session_cache_file.exists():
      try:
        self._session_cache_file.unlink()
      except Exception:
        pass

  async def connect(self, session_token: str | None = None) -> None:
    """
    Establish WebSocket connection with authentication.

    Args:
      session_token: Optional magic link token. If not provided, attempts
                     to use cached session cookie for reconnection.

    Raises:
      ConnectionError: If connection fails
      AuthenticationError: If authentication fails
    """
    self._connection_state = ConnectionState.CONNECTING

    try:
      # Create shared aiohttp session for HTTP and WebSocket if not already set
      if not self._session:
        self._session = aiohttp.ClientSession()

      # Use provided token or constructor token
      token = session_token or self._session_token

      # Try to load cached session cookie if no token provided
      if not token:
        cached_cookie = self._load_session_cookie()
        if cached_cookie:
          # Set the cached session cookie
          self._session.cookie_jar.update_cookies(
            {"session_token": cached_cookie}
          )

      # Verify magic link token if provided (skip for session resumption)
      if token:
        verify_url = f"{self._server_url}/auth/verify?token={token}"
        async with self._session.get(verify_url) as resp:
          # Server redirects on success, but cookie is set
          # Check that we got a response (even if redirect)
          if resp.status not in (200, 302, 303):
            self._connection_state = ConnectionState.DISCONNECTED
            raise AuthenticationError(
              f"Authentication failed: server returned {resp.status}"
            )

          # Extract and save session cookie after successful verification
          cookies = self._session.cookie_jar.filter_cookies(URL(self._server_url))
          session_cookie = cookies.get("session_token")
          if session_cookie:
            self._save_session_cookie(session_cookie.value)

      # Create Socket.IO client with shared session
      self._sio = socketio.AsyncClient(
        http_session=self._session,
        reconnection=False,  # We handle reconnection ourselves
      )

      # Register Socket.IO event handlers
      self._sio.on("connect", self._on_socket_connect)
      self._sio.on("disconnect", self._on_socket_disconnect)
      self._sio.on("authenticated", self._on_authenticated)
      self._sio.on("message", self._on_message)
      self._sio.on("user_joined", self._on_user_joined)
      self._sio.on("user_left", self._on_user_left)

      # Connect to WebSocket
      await self._sio.connect(
        self._server_url,
        wait_timeout=self._connection_timeout,
      )

      # Reset reconnect attempts on successful connection
      self._reconnect_attempts = 0

    except socketio.exceptions.ConnectionError as e:
      self._connection_state = ConnectionState.DISCONNECTED
      # Clean up session on failure
      if self._session:
        await self._session.close()
        self._session = None
      raise ConnectionError(f"Failed to connect: {e}") from e
    except Exception as e:
      self._connection_state = ConnectionState.DISCONNECTED
      # Clean up session on failure
      if self._session:
        await self._session.close()
        self._session = None
      raise ConnectionError(f"Connection error: {e}") from e

  async def disconnect(self) -> None:
    """Close WebSocket connection."""
    # Prevent reconnection during explicit disconnect
    self._reconnect = False

    if self._sio and self._sio.connected:
      await self._sio.disconnect()

    if self._session:
      await self._session.close()
      self._session = None

    self._connection_state = ConnectionState.DISCONNECTED
    self._user = None

  async def __aenter__(self) -> "AsyncClient":
    """Async context manager entry. Calls connect()."""
    await self.connect()
    return self

  async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
    """Async context manager exit. Calls disconnect()."""
    await self.disconnect()

  async def send(self, content: str) -> dict:
    """
    Send a chat message.

    Args:
      content: Message content

    Returns:
      dict with 'status', 'message_id', 'timestamp' on success
      dict with 'error', 'code' on failure

    Raises:
      ConnectionError: If not connected
    """
    if not self._sio or not self._sio.connected:
      raise ConnectionError("Not connected")

    # Create a future to receive the acknowledgment
    ack_future: asyncio.Future[dict] = asyncio.get_running_loop().create_future()

    def ack_callback(response: dict) -> None:
      """Handle acknowledgment from server."""
      if not ack_future.done():
        ack_future.set_result(response)

    try:
      # Emit message with acknowledgment callback
      await self._sio.emit("message", {"content": content}, callback=ack_callback)

      # Wait for acknowledgment
      return await asyncio.wait_for(ack_future, timeout=5.0)
    except asyncio.TimeoutError:
      return {"error": "Message acknowledgment timeout", "code": 408}
    except Exception as e:
      logger.error(f"Error sending message: {e}")
      return {"error": str(e), "code": 500}

  # Socket.IO event handlers

  async def _on_socket_connect(self) -> None:
    """Handle Socket.IO connect event."""
    logger.debug("Socket.IO connected")

  async def _on_socket_disconnect(self) -> None:
    """Handle Socket.IO disconnect event."""
    logger.debug("Socket.IO disconnected")

    # Emit disconnect event
    await self._events.emit("disconnect", {})

    # Attempt reconnection if enabled
    if self._reconnect:
      await self._attempt_reconnection()

  async def _on_authenticated(self, data: dict) -> None:
    """Handle authenticated event from server."""
    logger.info(f"Authenticated as {data.get('user', {}).get('email', 'unknown')}")

    # Store user info
    self._user = data.get("user")

    # Update state
    self._connection_state = ConnectionState.CONNECTED

    # Emit authenticated event
    await self._events.emit("authenticated", data)

  async def _on_message(self, data: dict) -> None:
    """Handle message event from server."""
    await self._events.emit("message", data)

  async def _on_user_joined(self, data: dict) -> None:
    """Handle user_joined event from server."""
    await self._events.emit("user_joined", data)

  async def _on_user_left(self, data: dict) -> None:
    """Handle user_left event from server."""
    await self._events.emit("user_left", data)

  async def _attempt_reconnection(self) -> None:
    """Attempt to reconnect with exponential backoff."""
    self._connection_state = ConnectionState.RECONNECTING

    while (
      self._reconnect
      and self._reconnect_attempts < self._max_reconnect_attempts
    ):
      self._reconnect_attempts += 1

      # Calculate delay with exponential backoff and jitter
      delay = self._reconnect_delay * (2 ** (self._reconnect_attempts - 1))
      delay = delay + random.uniform(0, 0.5)  # Add jitter

      logger.info(
        f"Reconnection attempt {self._reconnect_attempts}/{self._max_reconnect_attempts} "
        f"in {delay:.1f}s"
      )

      await asyncio.sleep(delay)

      try:
        # Clean up old Socket.IO client (keep the same session!)
        if self._sio:
          try:
            await self._sio.disconnect()
          except Exception:
            pass

        # Create new Socket.IO client with the SAME session (cookie is preserved)
        self._sio = socketio.AsyncClient(
          http_session=self._session,  # Reuse session - cookie is still there
          reconnection=False,
        )

        # Re-register event handlers
        self._sio.on("connect", self._on_socket_connect)
        self._sio.on("disconnect", self._on_socket_disconnect)
        self._sio.on("authenticated", self._on_authenticated)
        self._sio.on("message", self._on_message)
        self._sio.on("user_joined", self._on_user_joined)
        self._sio.on("user_left", self._on_user_left)

        # Connect (session cookie from original auth is still in self._session)
        await self._sio.connect(
          self._server_url,
          wait_timeout=self._connection_timeout,
        )

        # Reset reconnect attempts on successful connection
        self._reconnect_attempts = 0
        return

      except Exception as e:
        logger.warning(f"Reconnection attempt failed: {e}")

    # Max attempts exceeded
    self._connection_state = ConnectionState.DISCONNECTED
    await self._events.emit(
      "error",
      {
        "error": "Max reconnection attempts exceeded",
        "code": 503,
      },
    )
