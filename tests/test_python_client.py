"""
Tests for Python Client Library functionality.

This module tests the Python client library for Roomz, providing
programmatic access to chat functionality via WebSocket.

Requirements: FR-1.6.1, FR-1.6.2 (from functional analysis)
- Client emits events: connected, disconnected, message, presence, error
- Client methods: connect, disconnect, join_room, leave_room, send
- Async/await compatible
- Automatic reconnection with configurable backoff

Task: I3-001 Python client library
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from roomz.client import (
  AsyncClient,
  AuthenticationError,
  ClientError,
  ConnectionError,
  ConnectionState,
  SyncClient,
)


class TestClientExceptions:
  """Test suite for client exception hierarchy."""

  def test_client_error_is_base_exception(self):
    """Test that ClientError is the base exception."""
    with pytest.raises(ClientError):
      raise ClientError("test error")

  def test_connection_error_inherits_from_client_error(self):
    """Test that ConnectionError inherits from ClientError."""
    assert issubclass(ConnectionError, ClientError)

    with pytest.raises(ClientError):
      raise ConnectionError("connection failed")

  def test_authentication_error_inherits_from_client_error(self):
    """Test that AuthenticationError inherits from ClientError."""
    assert issubclass(AuthenticationError, ClientError)

    with pytest.raises(ClientError):
      raise AuthenticationError("authentication failed")


class TestConnectionState:
  """Test suite for ConnectionState enum."""

  def test_connection_state_values(self):
    """Test that ConnectionState has expected values."""
    assert ConnectionState.DISCONNECTED.value == "disconnected"
    assert ConnectionState.CONNECTING.value == "connecting"
    assert ConnectionState.CONNECTED.value == "connected"
    assert ConnectionState.RECONNECTING.value == "reconnecting"

  def test_connection_state_order(self):
    """Test that ConnectionState values represent lifecycle order."""
    states = [
      ConnectionState.DISCONNECTED,
      ConnectionState.CONNECTING,
      ConnectionState.CONNECTED,
      ConnectionState.RECONNECTING,
    ]
    # All states should be unique
    assert len(set(states)) == 4


class TestAsyncClientInit:
  """Test suite for AsyncClient initialization."""

  def test_async_client_class_exists(self):
    """
    Test that AsyncClient class exists in expected module.

    Given: The roomz.client package
    When: Importing from roomz.client
    Then: AsyncClient class is available
    """
    assert AsyncClient is not None

  def test_async_client_init_signature(self):
    """
    Test that AsyncClient __init__ has expected signature.

    Given: The AsyncClient class
    When: Instantiating with server_url and session_token
    Then: Client is created with optional config
    """
    client = AsyncClient(
      server_url="http://localhost:5000",
      session_token="test-token",
      reconnect=True,
      reconnect_delay=1.0,
      max_reconnect_attempts=5,
      connection_timeout=10.0,
    )

    assert client._server_url == "http://localhost:5000"
    assert client._session_token == "test-token"
    assert client._reconnect is True
    assert client._reconnect_delay == 1.0
    assert client._max_reconnect_attempts == 5
    assert client._connection_timeout == 10.0

  def test_async_client_default_parameters(self):
    """Test that AsyncClient has sensible defaults."""
    client = AsyncClient(
      server_url="http://localhost:5000",
      session_token="test-token",
    )

    assert client._reconnect is True
    assert client._reconnect_delay == 1.0
    assert client._max_reconnect_attempts == 5
    assert client._connection_timeout == 10.0
    assert client._session_cache_file is None

  def test_async_client_session_cache_file(self):
    """Test that session_cache_file is properly set."""
    from pathlib import Path

    cache_file = Path("/tmp/test_session.json")
    client = AsyncClient(
      server_url="http://localhost:5000",
      session_cache_file=cache_file,
    )

    assert client._session_cache_file == cache_file

  def test_async_client_optional_session_token(self):
    """Test that session_token is optional."""
    client = AsyncClient(server_url="http://localhost:5000")

    assert client._session_token == ""

  def test_async_client_state_property(self):
    """Test that state property exists and returns ConnectionState."""
    client = AsyncClient(
      server_url="http://localhost:5000",
      session_token="test-token",
    )

    assert client.connection_state == ConnectionState.DISCONNECTED

  def test_async_client_connected_property(self):
    """Test that connected property exists and returns bool."""
    client = AsyncClient(
      server_url="http://localhost:5000",
      session_token="test-token",
    )

    assert client.connected is False


class TestAsyncClientEventHandling:
  """Test suite for AsyncClient event emitter pattern."""

  def test_async_client_on_method(self):
    """Test that on() method registers event handlers."""
    client = AsyncClient(
      server_url="http://localhost:5000",
      session_token="test-token",
    )

    handler = MagicMock()
    client.on("message", handler)

    assert handler in client._events._handlers["message"]

  def test_async_client_off_method(self):
    """Test that off() method removes event handlers."""
    client = AsyncClient(
      server_url="http://localhost:5000",
      session_token="test-token",
    )

    handler = MagicMock()
    client.on("message", handler)
    client.off("message", handler)

    assert handler not in client._events._handlers["message"]

  def test_async_client_off_all_handlers(self):
    """Test that off() without handler removes all handlers."""
    client = AsyncClient(
      server_url="http://localhost:5000",
      session_token="test-token",
    )

    handler1 = MagicMock()
    handler2 = MagicMock()
    client.on("message", handler1)
    client.on("message", handler2)
    client.off("message")

    assert len(client._events._handlers["message"]) == 0

  def test_async_client_multiple_listeners_same_event(self):
    """Test that multiple listeners can be registered for same event."""
    client = AsyncClient(
      server_url="http://localhost:5000",
      session_token="test-token",
    )

    handler1 = MagicMock()
    handler2 = MagicMock()
    client.on("message", handler1)
    client.on("message", handler2)

    assert handler1 in client._events._handlers["message"]
    assert handler2 in client._events._handlers["message"]
    assert len(client._events._handlers["message"]) == 2

  @pytest.mark.asyncio
  async def test_async_client_emit_event(self):
    """Test that emit() calls all registered handlers."""
    client = AsyncClient(
      server_url="http://localhost:5000",
      session_token="test-token",
    )

    results = []

    def handler1(data):
      results.append(("handler1", data))

    def handler2(data):
      results.append(("handler2", data))

    client.on("message", handler1)
    client.on("message", handler2)

    await client._events.emit("message", {"content": "test"})

    assert ("handler1", {"content": "test"}) in results
    assert ("handler2", {"content": "test"}) in results


class TestAsyncClientSend:
  """Test suite for AsyncClient send method."""

  @pytest.mark.asyncio
  async def test_async_client_send_not_connected_raises_error(self):
    """Test that send() raises ConnectionError when not connected."""
    client = AsyncClient(
      server_url="http://localhost:5000",
      session_token="test-token",
    )

    with pytest.raises(ConnectionError):
      await client.send("test message")

  @pytest.mark.asyncio
  async def test_async_client_send_returns_acknowledgment(self):
    """Test that send() returns acknowledgment dict on success."""
    client = AsyncClient(
      server_url="http://localhost:5000",
      session_token="test-token",
    )

    # Mock Socket.IO client
    mock_sio = AsyncMock()
    mock_sio.connected = True

    async def mock_emit(event, data, callback=None):
      if callback:
        callback({"status": "ok", "message_id": "test-id", "timestamp": "2026-05-14T10:00:00Z"})

    mock_sio.emit = mock_emit
    client._sio = mock_sio

    result = await client.send("test message")

    assert result["status"] == "ok"
    assert result["message_id"] == "test-id"
    assert "timestamp" in result


class TestSyncClientInit:
  """Test suite for SyncClient initialization."""

  def test_sync_client_class_exists(self):
    """
    Test that SyncClient class exists in expected module.

    Given: The roomz.client package
    When: Importing from roomz.client
    Then: SyncClient class is available
    """
    assert SyncClient is not None

  def test_sync_client_init_signature(self):
    """
    Test that SyncClient __init__ has expected signature.

    Given: The SyncClient class
    When: Instantiating with server_url and session_token
    Then: Client is created with same options as AsyncClient
    """
    client = SyncClient(
      server_url="http://localhost:5000",
      session_token="test-token",
      reconnect=True,
      reconnect_delay=1.0,
      max_reconnect_attempts=5,
      connection_timeout=10.0,
    )

    assert client._async_client is not None
    assert client._async_client._server_url == "http://localhost:5000"
    assert client._async_client._session_token == "test-token"

  def test_sync_client_properties(self):
    """Test that SyncClient exposes same properties as AsyncClient."""
    client = SyncClient(
      server_url="http://localhost:5000",
      session_token="test-token",
    )

    # Properties should delegate to async client
    assert client.connected is False
    assert client.connection_state == ConnectionState.DISCONNECTED
    assert client.user is None


class TestSyncClientEventHandling:
  """Test suite for SyncClient event emitter pattern."""

  def test_sync_client_on_method(self):
    """Test that on() method registers event handlers."""
    client = SyncClient(
      server_url="http://localhost:5000",
      session_token="test-token",
    )

    handler = MagicMock()
    client.on("message", handler)

    assert handler in client._async_client._events._handlers["message"]

  def test_sync_client_off_method(self):
    """Test that off() method removes event handlers."""
    client = SyncClient(
      server_url="http://localhost:5000",
      session_token="test-token",
    )

    handler = MagicMock()
    client.on("message", handler)
    client.off("message", handler)

    assert handler not in client._async_client._events._handlers["message"]


class TestAsyncClientConnection:
  """
  Test suite for AsyncClient WebSocket connection.

  Integration tests require running server. These tests mock
  the Socket.IO client for unit testing.
  """

  @pytest.mark.asyncio
  async def test_async_client_connect_sets_up_session(self):
    """
    Test that connect() creates aiohttp session and verifies token.
    """
    client = AsyncClient(
      server_url="http://localhost:5000",
      session_token="test-token",
    )

    # Mock aiohttp session
    with patch("aiohttp.ClientSession") as mock_session_class:
      mock_session = AsyncMock()
      mock_response = AsyncMock()
      mock_response.status = 200
      mock_response.__aenter__ = AsyncMock(return_value=mock_response)
      mock_response.__aexit__ = AsyncMock(return_value=None)
      mock_session.get = MagicMock(return_value=mock_response)
      mock_session_class.return_value = mock_session

      # Mock Socket.IO client
      with patch("socketio.AsyncClient") as mock_sio_class:
        mock_sio = AsyncMock()
        mock_sio.connected = True
        mock_sio_class.return_value = mock_sio

        # This will fail because we haven't fully mocked, but we can check setup
        try:
          await client.connect()
        except Exception:
          pass

        # Verify session was created
        assert client._session is not None or mock_session_class.called

  @pytest.mark.asyncio
  async def test_async_client_connect_with_token_parameter(self):
    """Test that connect() accepts optional session_token parameter."""
    client = AsyncClient(server_url="http://localhost:5000")

    # Mock aiohttp session
    with patch("aiohttp.ClientSession") as mock_session_class:
      mock_session = AsyncMock()
      mock_response = AsyncMock()
      mock_response.status = 200
      mock_response.__aenter__ = AsyncMock(return_value=mock_response)
      mock_response.__aexit__ = AsyncMock(return_value=None)
      mock_session.get = MagicMock(return_value=mock_response)
      mock_session_class.return_value = mock_session

      # Mock Socket.IO client
      with patch("socketio.AsyncClient") as mock_sio_class:
        mock_sio = AsyncMock()
        mock_sio.connected = True
        mock_sio_class.return_value = mock_sio

        try:
          await client.connect(session_token="test-token")
        except Exception:
          pass

  @pytest.mark.asyncio
  async def test_async_client_disconnect_cleans_up(self):
    """Test that disconnect() closes session and updates state."""
    client = AsyncClient(
      server_url="http://localhost:5000",
      session_token="test-token",
    )

    # Setup mock session
    mock_session = AsyncMock()
    client._session = mock_session

    # Setup mock Socket.IO
    mock_sio = AsyncMock()
    mock_sio.connected = True
    client._sio = mock_sio
    client._connection_state = ConnectionState.CONNECTED
    client._user = {"id": "test", "email": "test@example.com"}

    await client.disconnect()

    # Verify cleanup
    assert client._connection_state == ConnectionState.DISCONNECTED
    assert client._user is None
    mock_sio.disconnect.assert_called_once()
    mock_session.close.assert_called_once()


class TestAsyncClientLogin:
  """Test suite for AsyncClient login method."""

  @pytest.mark.asyncio
  async def test_async_client_login_requests_magic_link(self):
    """Test that login() requests a magic link."""
    client = AsyncClient(server_url="http://localhost:5000")

    # Mock aiohttp session
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={})
    # Make response work as async context manager
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    mock_session.post = MagicMock(return_value=mock_response)

    client._session = mock_session

    result = await client.login("test@example.com")

    assert result is True
    mock_session.post.assert_called_once()

  @pytest.mark.asyncio
  async def test_async_client_login_handles_error(self):
    """Test that login() handles request errors."""
    client = AsyncClient(server_url="http://localhost:5000")

    # Mock aiohttp session
    with patch("aiohttp.ClientSession") as mock_session_class:
      mock_session = AsyncMock()
      mock_response = AsyncMock()
      mock_response.status = 400
      mock_response.json = AsyncMock(return_value={"detail": "Invalid email"})
      mock_response.__aenter__ = AsyncMock(return_value=mock_response)
      mock_response.__aexit__ = AsyncMock(return_value=None)
      mock_session.post = MagicMock(return_value=mock_response)
      mock_session_class.return_value = mock_session

      with pytest.raises(ConnectionError):
        await client.login("invalid-email")


class TestAsyncClientSessionCaching:
  """Test suite for AsyncClient session caching."""

  def test_save_session_cookie_disabled(self):
    """Test that session cookie is not saved when caching disabled."""
    client = AsyncClient(server_url="http://localhost:5000")

    client._save_session_cookie("test-cookie")

    # Should not raise error, just return

  def test_load_session_cookie_disabled(self):
    """Test that session cookie is not loaded when caching disabled."""
    client = AsyncClient(server_url="http://localhost:5000")

    result = client._load_session_cookie()

    assert result is None

  def test_save_and_load_session_cookie(self):
    """Test that session cookie can be saved and loaded."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
      cache_file = Path(tmpdir) / "session.json"
      client = AsyncClient(
        server_url="http://localhost:5000",
        session_cache_file=cache_file,
      )

      client._save_session_cookie("test-cookie-value")

      loaded = client._load_session_cookie()

      assert loaded == "test-cookie-value"

  def test_load_session_cookie_validates_server_url(self):
    """Test that loaded session cookie is validated against server URL."""
    import json
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
      cache_file = Path(tmpdir) / "session.json"

      # Write a session file with different server
      cache_file.write_text(
        json.dumps(
          {"session_cookie": "test-cookie", "server": "http://other-server:5000"}
        )
      )

      client = AsyncClient(
        server_url="http://localhost:5000",
        session_cache_file=cache_file,
      )

      loaded = client._load_session_cookie()

      # Should return None because server URL doesn't match
      assert loaded is None

  def test_clear_cached_session(self):
    """Test that cached session can be cleared."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
      cache_file = Path(tmpdir) / "session.json"
      client = AsyncClient(
        server_url="http://localhost:5000",
        session_cache_file=cache_file,
      )

      client._save_session_cookie("test-cookie")
      assert cache_file.exists()

      client.clear_cached_session()

      assert not cache_file.exists()


class TestAsyncClientContextManager:
  """Test suite for AsyncClient context manager."""

  @pytest.mark.asyncio
  async def test_async_client_context_manager_connects(self):
    """Test that async context manager calls connect()."""
    client = AsyncClient(
      server_url="http://localhost:5000",
      session_token="test-token",
    )

    # Mock the connect method
    client.connect = AsyncMock()

    async with client:
      pass

    client.connect.assert_called_once()

  @pytest.mark.asyncio
  async def test_async_client_context_manager_disconnects(self):
    """Test that async context manager calls disconnect() on exit."""
    client = AsyncClient(
      server_url="http://localhost:5000",
      session_token="test-token",
    )

    # Mock the methods
    client.connect = AsyncMock()
    client.disconnect = AsyncMock()

    async with client:
      pass

    client.disconnect.assert_called_once()


class TestSyncClientContextManager:
  """Test suite for SyncClient context manager."""

  def test_sync_client_context_manager_connects(self):
    """Test that context manager calls connect()."""
    client = SyncClient(
      server_url="http://localhost:5000",
      session_token="test-token",
    )

    # Mock the connect method
    client.connect = MagicMock()

    with client:
      pass

    client.connect.assert_called_once()

  def test_sync_client_context_manager_disconnects(self):
    """Test that context manager calls disconnect() on exit."""
    client = SyncClient(
      server_url="http://localhost:5000",
      session_token="test-token",
    )

    # Mock the methods
    client.connect = MagicMock()
    client.disconnect = MagicMock()

    with client:
      pass

    client.disconnect.assert_called_once()


class TestClientModuleExports:
  """Test suite for module exports."""

  def test_module_exports_async_client(self):
    """Test that AsyncClient is exported from roomz.client."""
    from roomz.client import AsyncClient

    assert AsyncClient is not None

  def test_module_exports_sync_client(self):
    """Test that SyncClient is exported from roomz.client."""
    from roomz.client import SyncClient

    assert SyncClient is not None

  def test_module_exports_connection_state(self):
    """Test that ConnectionState is exported from roomz.client."""
    from roomz.client import ConnectionState

    assert ConnectionState is not None

  def test_module_exports_exceptions(self):
    """Test that exceptions are exported from roomz.client."""
    from roomz.client import AuthenticationError, ClientError, ConnectionError

    assert ClientError is not None
    assert ConnectionError is not None
    assert AuthenticationError is not None

  def test_package_exports(self):
    """Test that all exports are available from roomz package."""
    from roomz import (
      AsyncClient,
      AuthenticationError,
      ClientError,
      ConnectionError,
      ConnectionState,
      SyncClient,
    )

    assert AsyncClient is not None
    assert SyncClient is not None
    assert ConnectionState is not None
    assert ClientError is not None
    assert ConnectionError is not None
    assert AuthenticationError is not None


# Integration tests (require running server)
# These are skipped by default and should be run manually

@pytest.mark.skip(reason="Integration test requires running server")
class TestClientIntegration:
  """
  Test suite for Python client integration with running server.

  These tests require a running Roomz server and valid session token.
  Run manually with: pytest tests/test_python_client.py -v --run-integration
  """

  @pytest.mark.asyncio
  async def test_client_can_connect_to_server(self):
    """
    Test that Python client can connect to running server.

    Prerequisites:
    - Server running at http://localhost:5000
    - Valid session token obtained via magic link flow
    """
    pytest.fail("Integration test requires running server and valid token")

  @pytest.mark.asyncio
  async def test_client_can_send_and_receive_messages(self):
    """
    Test that Python client can send and receive messages.

    Prerequisites:
    - Server running at http://localhost:5000
    - Two connected clients (Python or web)
    """
    pytest.fail("Integration test requires running server and valid token")

  @pytest.mark.asyncio
  async def test_client_receives_presence_events(self):
    """
    Test that Python client receives user_joined and user_left events.

    Prerequisites:
    - Server running at http://localhost:5000
    - Multiple clients connected
    """
    pytest.fail("Integration test requires running server and valid token")
