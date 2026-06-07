"""
Async Client

Primary async WebSocket client implementation for Roomz.
"""

import asyncio
import logging
import random
from pathlib import Path
from typing import Any

import aiohttp
import socketio  # type: ignore[import-untyped]
from clevis import SecurityAction, get_config
from yarl import URL

from roomz.client.config import RoomzConfig
from roomz.client.events import EventEmitter, EventHandler
from roomz.client.exceptions import AuthenticationError, ConfigurationError, ConnectionError
from roomz.client.session import load_session_cache, save_session_cache
from roomz.client.state import ConnectionState

logger = logging.getLogger(__name__)


class AsyncClient:
  """
  Async WebSocket client for Roomz real-time chat.

  Configuration Resolution Order (highest to lowest priority):
    1. Explicit `config` parameter
    2. ./roomz.toml (project config with ${VAR} interpolation)
    3. ~/.roomz.toml (user config with ${VAR} interpolation)
    4. Dataclass defaults

  Usage with explicit config:
    config = RoomzConfig(server_url="http://localhost:5000")
    async with AsyncClient(config=config) as client:
      client.on('message', handle_message)
      await client.send("Hello, world!")

  Usage with auto-discovery:
    async with AsyncClient() as client:
      await client.connect(session_token="magic-link-token")

  Environment Variables:
    Environment variables are supported via ${VAR} interpolation in TOML files,
    not directly. Use ${ROOMZ_SERVER_URL} and ${ROOMZ_DISPLAY_NAME} in TOML:

    TOML file example:
      [client]
      server_url = "${ROOMZ_SERVER_URL}"
      display_name = "${ROOMZ_DISPLAY_NAME}"

  Authentication Flow:
    1. Shared aiohttp.ClientSession is used for HTTP and WebSocket
    2. Call /auth/verify?token=xxx to get session cookie
    3. Cookie is automatically passed to WebSocket connection

  Security:
    - Config files with group/other read permissions are REJECTED
    - Config files in world-writable directories are REJECTED
    - Session cache files created with 0600 permissions
  """

  def __init__(
    self,
    config: RoomzConfig | None = None,
    args: list[str] | None = None,
    session_token: str = "",
    session_cache_file: str | Path | None = None,
    *,
    reconnect: bool = True,
    reconnect_delay: float = 1.0,
    max_reconnect_attempts: int = 5,
    connection_timeout: float = 10.0,
  ):
    """
    Initialize async client.

    Args:
      config: Configuration object (highest priority, overrides auto-discovery)
      args: CLI arguments to pass to clevis (optional, for testing)
      session_token: Magic link token for authentication (optional if session_cache_file is set)
      session_cache_file: Path to cache session cookie (None to disable caching)
      reconnect: Enable automatic reconnection (default: True)
      reconnect_delay: Initial delay between reconnection attempts in seconds (default: 1.0)
      max_reconnect_attempts: Maximum reconnection attempts (default: 5)
      connection_timeout: Timeout for connection in seconds (default: 10.0)

    Configuration Resolution Order (highest to lowest priority):
      1. Explicit `config` parameter
      2. ./roomz.toml (project config with ${VAR} interpolation)
      3. ~/.roomz.toml (user config with ${VAR} interpolation)
      4. Dataclass defaults

    Security:
      - Config files with group/other read permissions are REJECTED
      - Config files in world-writable directories are REJECTED
      - Home directory is trusted (no directory check)

    Example:
      >>> # Explicit config
      >>> config = RoomzConfig(client=ClientConfig(server_url="http://localhost:5000", display_name="Alice"))
      >>> client = AsyncClient(config=config)

      >>> # Auto-discovery
      >>> client = AsyncClient()
    """
    # Resolve configuration
    if config is not None:
      self._config = config
    else:
      self._config = get_config(
        RoomzConfig,
        name="roomz",
        cli=False,
        security={
          "file_permissions": SecurityAction.REJECT,
          "directory_permissions": SecurityAction.REJECT,
        },
      )

    self._session_token = session_token
    self._reconnect = reconnect
    self._reconnect_delay = reconnect_delay
    self._max_reconnect_attempts = max_reconnect_attempts
    self._connection_timeout = connection_timeout
    self._session_cache_file = Path(session_cache_file) if session_cache_file else None
    self._cached_cookie: str | None = None  # Cached JWT cookie for reconnection

    # Extract values from config
    self._display_name = (
      self._config.client.display_name.strip() if self._config.client.display_name else None
    )

    self._connection_state = ConnectionState.DISCONNECTED
    self._user: dict[str, Any] | None = None
    self._session: aiohttp.ClientSession | None = None
    self._sio: socketio.AsyncClient | None = None
    self._events: EventEmitter = EventEmitter()
    self._reconnect_attempts = 0

  @property
  def connected(self) -> bool:
    """True if WebSocket is connected and authenticated."""
    return self._connection_state == ConnectionState.CONNECTED

  @property
  def user(self) -> dict[str, Any] | None:
    """Current user info: {'id': str, 'email': str} or None if not authenticated."""
    return self._user

  @property
  def connection_state(self) -> ConnectionState:
    """Current connection state."""
    return self._connection_state

  @property
  def display_name(self) -> str | None:
    """Current display name (loaded from config/env, may be overridden by server)."""
    return self._display_name

  @property
  def server_url(self) -> str | None:
    """WebSocket server URL from configuration."""
    return self._config.client.server_url

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
      ConfigurationError: If server_url is not configured
      ConnectionError: If request fails
    """
    # Validate configuration
    if self._config.client.server_url is None:
      raise ConfigurationError(
        "server_url is not configured. "
        "Provide config with server_url, set ROOMZ_SERVER_URL, "
        "or create ./roomz.toml or ~/.roomz.toml"
      )

    if not self._session:
      self._session = aiohttp.ClientSession()

    url = f"{self._config.client.server_url}/auth/request-magic-link"
    try:
      async with self._session.post(url, json={"email": email}) as resp:
        if resp.status == 200:
          return True
        else:
          data = await resp.json()
          raise ConnectionError(
            f"Failed to request magic link: {data.get('detail', 'Unknown error')}"
          )
    except Exception as e:
      raise ConnectionError(f"Failed to request magic link: {e}") from e

  def clear_cached_session(self) -> None:
    """Clear cached session cookie."""
    from roomz.client.session import clear_session_cache

    cache_file = self._session_cache_file if self._session_cache_file else None
    clear_session_cache(cache_file=cache_file)

  def _save_session_cookie(self, cookie_value: str) -> None:
    """
    Save session cookie to cache file (internal method for testing).

    Args:
      cookie_value: Session cookie value to save

    Note:
      This method exists for backward compatibility with tests.
      New code should use session.save_session_cache() directly.
    """
    from roomz.client.session import save_session_cache

    cache_file = self._session_cache_file if self._session_cache_file else None
    if cache_file:
      save_session_cache(cookie_value, self._config.client.server_url, cache_file=cache_file)

  def _load_session_cookie(self) -> str | None:
    """
    Load session cookie from cache file (internal method for testing).

    Returns:
      Session cookie value or None if not found

    Note:
      This method exists for backward compatibility with tests.
      New code should use session.load_session_cache() directly.
    """
    from roomz.client.session import load_session_cache

    cache_file = self._session_cache_file if self._session_cache_file else None
    if not cache_file:
      return None

    cached_data = load_session_cache(cache_file=cache_file)
    if cached_data and cached_data.get("server") == self._config.client.server_url:
      cookie = cached_data.get("session_cookie")
      return str(cookie) if cookie else None
    return None

  async def connect(self, session_token: str | None = None) -> None:
    """
    Establish WebSocket connection with authentication.

    Args:
      session_token: Optional magic link token. If not provided, attempts
                     to use cached session cookie for reconnection.

    Raises:
      ConfigurationError: If server_url is not configured
      ConnectionError: If connection fails
      AuthenticationError: If authentication fails
    """
    # Validate configuration
    if self._config.client.server_url is None:
      raise ConfigurationError(
        "server_url is not configured. "
        "Provide config with server_url, set ROOMZ_SERVER_URL, "
        "or create ./roomz.toml or ~/.roomz.toml"
      )

    # Store as non-optional for type checker
    server_url = self._config.client.server_url

    self._connection_state = ConnectionState.CONNECTING

    try:
      # Create shared aiohttp session for HTTP and WebSocket if not already set
      if not self._session:
        self._session = aiohttp.ClientSession()

      # Use provided token or constructor token
      token = session_token or self._session_token

      # Try to load cached session cookie if no token provided
      if not token:
        cache_file = self._session_cache_file if self._session_cache_file else None
        cached_data = load_session_cache(cache_file=cache_file)
        if cached_data:
          # Only use cookie if server matches
          if cached_data.get("server") == self._config.client.server_url:
            cached_cookie = cached_data.get("session_cookie")
            if cached_cookie:
              # Set the cached session cookie in the cookie jar
              self._session.cookie_jar.update_cookies({"session_token": cached_cookie})
              # Also store for explicit header passing if needed
              self._cached_cookie = cached_cookie

      # Verify magic link token if provided (skip for session resumption)
      if token:
        verify_url = f"{server_url}/auth/verify?token={token}"
        async with self._session.get(verify_url) as resp:
          # Server redirects on success, but cookie is set
          # Check that we got a response (even if redirect)
          if resp.status not in (200, 302, 303):
            self._connection_state = ConnectionState.DISCONNECTED
            raise AuthenticationError(f"Authentication failed: server returned {resp.status}")

          # Extract and save session cookie after successful verification
          cookies = self._session.cookie_jar.filter_cookies(URL(server_url))
          session_cookie = cookies.get("session_token")
          if session_cookie:
            cache_file = self._session_cache_file if self._session_cache_file else None
            save_session_cache(
              session_cookie.value, self._config.client.server_url, cache_file=cache_file
            )
            self._cached_cookie = session_cookie.value

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
      self._sio.on("display_name_changed", self._on_display_name_changed)

      # Build headers with cookie for WebSocket handshake
      headers = {}
      if hasattr(self, "_cached_cookie") and self._cached_cookie:
        headers["Cookie"] = f"session_token={self._cached_cookie}"

      # Connect to WebSocket
      await self._sio.connect(
        server_url,
        headers=headers if headers else {},
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

  async def __aexit__(
    self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: object
  ) -> None:
    """Async context manager exit. Calls disconnect()."""
    await self.disconnect()

  async def send(self, content: str) -> dict[str, Any]:
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
    ack_future: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()

    def ack_callback(response: dict[str, Any]) -> None:
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

  async def set_display_name(self, display_name: str | None) -> dict[str, Any]:
    """
    Set display name for this connection.

    Display names are per-connection and ephemeral - not stored server-side.
    Each device/session can have its own display name.

    Args:
      display_name: Display name to set, or None/empty to clear

    Returns:
      dict with 'status', 'display_name' on success
      dict with 'error', 'code' on failure

    Raises:
      ConnectionError: If not connected
    """
    if not self._sio or not self._sio.connected:
      raise ConnectionError("Not connected")

    # Normalize: empty string becomes None
    if display_name is not None:
      display_name = display_name.strip() or None

    # Create a future to receive the acknowledgment
    ack_future: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()

    def ack_callback(response: dict[str, Any]) -> None:
      """Handle acknowledgment from server."""
      if not ack_future.done():
        ack_future.set_result(response)

    try:
      # Emit set_display_name event with acknowledgment callback
      await self._sio.emit(
        "set_display_name", {"display_name": display_name}, callback=ack_callback
      )

      # Wait for acknowledgment
      result = await asyncio.wait_for(ack_future, timeout=5.0)

      # Update local display name on success
      if result.get("status") == "ok":
        self._display_name = result.get("display_name")

      return result

    except asyncio.TimeoutError:
      return {"error": "Display name acknowledgment timeout", "code": 408}
    except Exception as e:
      logger.error(f"Error setting display name: {e}")
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

  async def _on_authenticated(self, data: dict[str, Any]) -> None:
    """Handle authenticated event from server."""
    logger.info(f"Authenticated as {data.get('user', {}).get('email', 'unknown')}")

    # Store user info
    self._user = data.get("user")

    # Update state
    self._connection_state = ConnectionState.CONNECTED

    # Send display name if configured
    if self._display_name:
      logger.debug(f"Sending display name: {self._display_name}")
      await self.set_display_name(self._display_name)

    # Emit authenticated event
    await self._events.emit("authenticated", data)

  async def _on_message(self, data: dict[str, Any]) -> None:
    """Handle message event from server."""
    # Only process if connected (prevent duplicate events during reconnection)
    if self._connection_state == ConnectionState.CONNECTED:
      await self._events.emit("message", data)

  async def _on_user_joined(self, data: dict[str, Any]) -> None:
    """Handle user_joined event from server."""
    if self._connection_state == ConnectionState.CONNECTED:
      await self._events.emit("user_joined", data)

  async def _on_user_left(self, data: dict[str, Any]) -> None:
    """Handle user_left event from server."""
    if self._connection_state == ConnectionState.CONNECTED:
      await self._events.emit("user_left", data)

  async def _on_display_name_changed(self, data: dict[str, Any]) -> None:
    """Handle display_name_changed event from server."""
    if self._connection_state == ConnectionState.CONNECTED:
      await self._events.emit("display_name_changed", data)

  async def _attempt_reconnection(self) -> None:
    """Attempt to reconnect with exponential backoff."""
    self._connection_state = ConnectionState.RECONNECTING

    # Validate server_url is configured (should be if connect() was called)
    if self._config.client.server_url is None:
      logger.error("Cannot reconnect: server_url not configured")
      self._connection_state = ConnectionState.DISCONNECTED
      return

    server_url = self._config.client.server_url

    while self._reconnect and self._reconnect_attempts < self._max_reconnect_attempts:
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
        self._sio.on("display_name_changed", self._on_display_name_changed)

        # Build headers with cookie for WebSocket handshake
        headers = {}
        if hasattr(self, "_cached_cookie") and self._cached_cookie:
          headers["Cookie"] = f"session_token={self._cached_cookie}"

        # Connect (session cookie from original auth is still in self._session)
        await self._sio.connect(
          server_url,
          headers=headers if headers else {},
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
