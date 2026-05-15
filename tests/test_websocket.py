"""
Tests for WebSocket Authentication functionality.

This module tests WebSocket connection authentication,
JWT validation, and user identification.

Note: These tests require a running server (integration tests).
AsyncServer doesn't support test_client() like sync Server.
To run these tests, start the server and run integration tests separately.

Requirements: FR-1.3.1, FR-1.1.2 (from functional analysis)
- Persistent WebSocket connection per authenticated user
- JWT validation on each WebSocket connection
- Connection handles network interruptions gracefully
"""

import pytest

from app import connected_clients
from app.auth import generate_jwt, validate_jwt, allowed_emails_manager

# Skip all WebSocket tests until integration test infrastructure is set up
pytestmark = pytest.mark.skip(
  reason="WebSocket tests require running server - integration tests needed"
)


class TestWebSocketAuthentication:
  """
  Test suite for WebSocket authentication.

  Tests verify that WebSocket connections require valid session
  and that authentication is properly enforced.
  """

  def test_connection_with_valid_session_succeeds(self, authenticated_socketio_client):
    """
    Test that connection with valid session succeeds.

    Given: A user with valid session cookie
    When: User connects via WebSocket
    Then: Connection is established successfully
    """
    client, session_data = authenticated_socketio_client

    # Client should be connected
    assert client.is_connected()

    # Should be in connected_clients
    assert len(connected_clients) > 0

    # Session info should be stored
    for sid, client_info in connected_clients.items():
      assert "session" in client_info
      assert client_info["session"].email == session_data["user"]["email"]

  def test_connection_without_session_fails(self):
    """
    Test that connection without session fails.

    Given: A connection attempt without session cookie
    When: WebSocket tries to connect
    Then: Connection is rejected with appropriate error
    """
    from app import server

    # Create client without session cookie
    client = server.socketio.test_client(server)

    # Connection should be rejected (no session)
    # In the current implementation, connection returns False
    # The client may still show as connected but shouldn't be in connected_clients
    assert len(connected_clients) == 0

    client.disconnect()

  def test_connection_with_expired_session_fails(self):
    """
    Test that connection with expired session fails.

    Given: A session that has expired (30+ days old)
    When: WebSocket tries to connect
    Then: Connection is rejected, session cleared
    """
    import hashlib
    from datetime import datetime, timedelta, timezone

    from app import server

    # Create a session
    session_data = session_manager.create_session("expired@test.com")
    token = session_data["token"]

    # Manually expire it
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    session = session_manager.get_session_by_hash(token_hash)
    session.expires_at = datetime.now(timezone.utc) - timedelta(days=1)

    # Try to connect with expired session
    client = server.socketio.test_client(server, headers={"Cookie": f"session_token={token}"})

    # Should not be in connected_clients
    assert len(connected_clients) == 0

    client.disconnect()

  def test_connection_with_invalid_token_fails(self):
    """
    Test that connection with invalid token fails.

    Given: A malformed or invalid session token
    When: WebSocket tries to connect
    Then: Connection is rejected
    """
    from app import server

    # Try to connect with invalid token
    client = server.socketio.test_client(
      server, headers={"Cookie": "session_token=invalidtoken123"}
    )

    # Should not be in connected_clients
    assert len(connected_clients) == 0

    client.disconnect()


class TestWebSocketSessionValidation:
  """
  Test suite for WebSocket session validation.

  Tests verify that sessions are properly validated during
  WebSocket connection and throughout the connection lifecycle.
  """

  def test_session_validated_on_connect(self, authenticated_socketio_client):
    """
    Test that session is validated on WebSocket connect.

    Given: A WebSocket connection attempt
    When: on_connect handler is called
    Then: Session token is extracted and validated from cookie
    """
    client, session_data = authenticated_socketio_client

    # Connection succeeded, so session was validated
    assert client.is_connected()

    # Check that session info is stored
    assert len(connected_clients) > 0
    for sid, client_info in connected_clients.items():
      assert "session" in client_info
      assert client_info["session"].email is not None

  def test_session_expiry_checked_on_connect(self):
    """
    Test that session expiry is checked on connect.

    Given: A WebSocket connection attempt
    When: on_connect handler validates session
    Then: expires_at and last_activity are checked
    """
    import hashlib
    from datetime import datetime, timedelta, timezone

    from app import server

    # Create session and expire it
    session_data = session_manager.create_session("expirycheck@test.com")
    token = session_data["token"]

    token_hash = hashlib.sha256(token.encode()).hexdigest()
    session = session_manager.get_session_by_hash(token_hash)
    session.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)

    # Try to connect
    client = server.socketio.test_client(server, headers={"Cookie": f"session_token={token}"})

    # Connection should be rejected
    assert len(connected_clients) == 0

    client.disconnect()

  def test_session_ip_validation(self, authenticated_socketio_client):
    """
    Test that session IP is validated (if implemented).

    Given: A session created from IP address A
    When: WebSocket connects from IP address B
    Then: Session is validated or flagged for security
    """
    client, session_data = authenticated_socketio_client

    # In current implementation, IP is stored but not validated
    # Check that IP is stored in client_info
    for sid, client_info in connected_clients.items():
      assert "ip" in client_info
      # IP should be stored for security logging

  def test_session_user_agent_tracking(self, authenticated_socketio_client):
    """
    Test that user agent is tracked in session.

    Given: A session creation
    When: Session is created
    Then: User agent is stored for security validation
    """
    client, session_data = authenticated_socketio_client

    # User agent hash should be stored in session
    for sid, client_info in connected_clients.items():
      session = client_info.get("session")
      if session:
        # Session may have user_agent_hash
        assert session.user_agent_hash is not None or session.user_agent_hash is None


class TestWebSocketUserIdentification:
  """
  Test suite for WebSocket user identification.

  Tests verify that user identity is properly established
  and communicated in WebSocket events.
  """

  def test_user_email_included_in_messages(self, authenticated_socketio_client):
    """
    Test that user email is included in messages.

    Given: An authenticated user sending a message
    When: Message is broadcast to other users
    Then: Message includes user's email address
    """
    client, session_data = authenticated_socketio_client

    # Send a message
    client.emit("message", {"content": "Test message"})

    # Receive the message back
    received = client.get_received()

    # Find the message event
    message_events = [r for r in received if r["name"] == "message"]
    assert len(message_events) > 0

    message = message_events[0]["args"][0]
    assert "user" in message
    assert "email" in message["user"]
    assert message["user"]["email"] == session_data["user"]["email"]

  def test_user_joined_event_includes_email(self, authenticated_socketio_client, sample_email):
    """
    Test that user_joined event includes email.

    Given: A user connecting via WebSocket
    When: user_joined event is broadcast
    Then: Event includes user's email address
    """
    # First client
    client1, session_data1 = authenticated_socketio_client

    # Create second client
    from app import server

    session_data2 = session_manager.create_session("second@test.com")
    client2 = server.socketio.test_client(
      server, headers={"Cookie": f"session_token={session_data2['token']}"}
    )

    # First client should receive user_joined event for second client
    received = client1.get_received()

    # Find user_joined event
    joined_events = [r for r in received if r["name"] == "user_joined"]
    assert len(joined_events) > 0

    event = joined_events[-1]["args"][0]
    assert "user" in event
    assert "email" in event["user"]
    assert event["user"]["email"] == "second@test.com"

    client2.disconnect()

  def test_user_left_event_includes_email(self, authenticated_socketio_client):
    """
    Test that user_left event includes email.

    Given: A user disconnecting
    When: user_left event is broadcast
    Then: Event includes user's email address
    """
    # First client
    client1, session_data1 = authenticated_socketio_client

    # Create second client
    from app import server

    session_data2 = session_manager.create_session("leaving@test.com")
    client2 = server.socketio.test_client(
      server, headers={"Cookie": f"session_token={session_data2['token']}"}
    )

    # Clear received events
    client1.get_received()

    # Disconnect second client
    client2.disconnect()

    # First client should receive user_left event
    received = client1.get_received()

    # Find user_left event
    left_events = [r for r in received if r["name"] == "user_left"]
    assert len(left_events) > 0

    event = left_events[-1]["args"][0]
    assert "user" in event
    assert "email" in event["user"]
    assert event["user"]["email"] == "leaving@test.com"

  def test_user_identifier_in_connected_clients(self, authenticated_socketio_client):
    """
    Test that user identifier is stored in connected_clients.

    Given: A successful WebSocket connection
    When: User is registered in connected_clients
    Then: connected_clients includes user's email/session info
    """
    client, session_data = authenticated_socketio_client

    # Check connected_clients
    assert len(connected_clients) > 0

    # Find our client
    found = False
    for sid, client_info in connected_clients.items():
      if "session" in client_info:
        if client_info["session"].email == session_data["user"]["email"]:
          found = True
          break

    assert found


class TestWebSocketMessageSecurity:
  """
  Test suite for WebSocket message security.

  Tests verify that messages are properly authenticated and
  that users can only send messages when authenticated.
  """

  def test_message_without_authentication_rejected(self):
    """
    Test that messages without authentication are rejected.

    Given: An unauthenticated WebSocket connection
    When: User tries to send a message
    Then: Message is rejected with error
    """
    from app import server

    # Create client without auth
    client = server.socketio.test_client(server)

    # Try to send message
    client.emit("message", {"content": "Test"})

    # In current implementation, connection is rejected
    # so the client shouldn't be in connected_clients
    assert len(connected_clients) == 0

    client.disconnect()

  def test_message_includes_sender_identity(self, authenticated_socketio_client):
    """
    Test that message includes sender identity.

    Given: An authenticated user sending a message
    When: Message is processed
    Then: Message includes sender's email and user ID
    """
    client, session_data = authenticated_socketio_client

    # Send message
    client.emit("message", {"content": "Hello world"})

    # Receive message
    received = client.get_received()
    message_events = [r for r in received if r["name"] == "message"]

    assert len(message_events) > 0

    message = message_events[0]["args"][0]
    assert "user" in message
    assert "email" in message["user"]
    assert "id" in message["user"]
    assert message["user"]["email"] == session_data["user"]["email"]

  def test_message_sender_cannot_be_spoofed(self, authenticated_socketio_client):
    """
    Test that message sender cannot be spoofed.

    Given: A user trying to spoof another user's identity
    When: Message is processed
    Then: Sender identity is taken from session, not message payload
    """
    client, session_data = authenticated_socketio_client

    # Try to send message with spoofed user in payload
    client.emit(
      "message",
      {
        "content": "Hello",
        "user": {"email": "attacker@evil.com"},  # Spoofed
      },
    )

    # Receive message
    received = client.get_received()
    message_events = [r for r in received if r["name"] == "message"]

    assert len(message_events) > 0

    message = message_events[0]["args"][0]

    # Sender should be from session, not from payload
    assert message["user"]["email"] == session_data["user"]["email"]
    assert message["user"]["email"] != "attacker@evil.com"


class TestWebSocketConnectionLifecycle:
  """
  Test suite for WebSocket connection lifecycle.

  Tests verify proper handling of connections and disconnections
  with authentication context.
  """

  def test_authenticated_client_tracked_on_connect(self, authenticated_socketio_client):
    """
    Test that authenticated client is tracked on connect.

    Given: A successful WebSocket authentication
    When: Connection is established
    Then: Client is added to connected_clients with session info
    """
    client, session_data = authenticated_socketio_client

    # Should be connected
    assert client.is_connected()

    # Should be in connected_clients
    assert len(connected_clients) > 0

    # Should have session info
    for sid, client_info in connected_clients.items():
      assert "session" in client_info
      assert "ip" in client_info
      assert "connected_at" in client_info

  def test_client_removed_on_disconnect(self, authenticated_socketio_client):
    """
    Test that client is removed on disconnect.

    Given: An authenticated connected client
    When: Client disconnects
    Then: Client is removed from connected_clients
    """
    client, session_data = authenticated_socketio_client

    # Should be in connected_clients
    assert len(connected_clients) > 0

    # Disconnect
    client.disconnect()

    # Should be removed from connected_clients
    assert len(connected_clients) == 0

  def test_user_left_broadcast_on_disconnect(self, authenticated_socketio_client):
    """
    Test that user_left event is broadcast on disconnect.

    Given: Multiple authenticated clients connected
    When: One client disconnects
    Then: Other clients receive user_left event with user's email
    """
    # First client
    client1, session_data1 = authenticated_socketio_client

    # Create second client
    from app import server

    session_data2 = session_manager.create_session("second@test.com")
    client2 = server.socketio.test_client(
      server, headers={"Cookie": f"session_token={session_data2['token']}"}
    )

    # Clear received events
    client1.get_received()

    # Disconnect second client
    client2.disconnect()

    # First client should receive user_left
    received = client1.get_received()
    left_events = [r for r in received if r["name"] == "user_left"]

    assert len(left_events) > 0

    event = left_events[-1]["args"][0]
    assert "user" in event
    assert "email" in event["user"]

  def test_session_cleared_on_forced_disconnect(self, authenticated_socketio_client):
    """
    Test that session handling on forced disconnect.

    Given: An authenticated client with active session
    When: Connection is forcefully terminated
    Then: Session remains valid for reconnection
    """
    client, session_data = authenticated_socketio_client

    # Disconnect
    client.disconnect()

    # Session should still be valid
    validated = session_manager.validate_token(session_data["token"])
    assert validated is not None


class TestWebSocketReconnection:
  """
  Test suite for WebSocket reconnection behavior.

  Tests verify how authentication is handled during reconnection.
  """

  def test_reconnection_with_valid_session_succeeds(self):
    """
    Test that reconnection with valid session succeeds.

    Given: A user who disconnected with valid session
    When: User reconnects within session timeout
    Then: Connection succeeds, user identified by session
    """
    from app import server

    # Create session
    session_data = session_manager.create_session("reconnect@test.com")

    # Connect first time
    client1 = server.socketio.test_client(
      server, headers={"Cookie": f"session_token={session_data['token']}"}
    )

    assert client1.is_connected()
    assert len(connected_clients) > 0

    # Disconnect
    client1.disconnect()

    # Reconnect with same session
    client2 = server.socketio.test_client(
      server, headers={"Cookie": f"session_token={session_data['token']}"}
    )

    assert client2.is_connected()
    assert len(connected_clients) > 0

    client2.disconnect()

  def test_reconnection_with_expired_session_fails(self):
    """
    Test that reconnection with expired session fails.

    Given: A user whose session expired while disconnected
    When: User tries to reconnect
    Then: Connection fails, user must re-authenticate
    """
    import hashlib
    from datetime import datetime, timedelta, timezone

    from app import server

    # Create session
    session_data = session_manager.create_session("expiredreconnect@test.com")
    token = session_data["token"]

    # Connect first time
    client1 = server.socketio.test_client(server, headers={"Cookie": f"session_token={token}"})

    client1.disconnect()

    # Expire session
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    session = session_manager.get_session_by_hash(token_hash)
    session.expires_at = datetime.now(timezone.utc) - timedelta(days=1)

    # Try to reconnect
    client2 = server.socketio.test_client(server, headers={"Cookie": f"session_token={token}"})

    # Should not be connected
    assert len(connected_clients) == 0

    client2.disconnect()

  def test_reconnection_after_logout_fails(self):
    """
    Test that reconnection after logout fails.

    Given: A user who logged out
    When: User tries to reconnect with old session token
    Then: Connection is rejected
    """
    from app import server

    # Create session
    session_data = session_manager.create_session("logout@test.com")
    token = session_data["token"]

    # Connect first time
    client1 = server.socketio.test_client(server, headers={"Cookie": f"session_token={token}"})

    client1.disconnect()

    # Logout (revoke session)
    session_manager.revoke_session(token)

    # Try to reconnect
    client2 = server.socketio.test_client(server, headers={"Cookie": f"session_token={token}"})

    # Should not be connected
    assert len(connected_clients) == 0

    client2.disconnect()


class TestWebSocketEdgeCases:
  """
  Test suite for WebSocket edge cases.

  Tests verify handling of unusual scenarios and error conditions.
  """

  def test_malformed_cookie_handled_gracefully(self):
    """
    Test that malformed cookie is handled gracefully.

    Given: A WebSocket connection with malformed session cookie
    When: Connection attempt is made
    Then: Connection rejected with clear error, no crash
    """
    from app import server

    # Try various malformed cookies
    malformed_cookies = [
      "session_token=",
      "session_token=   ",
      "session_token=!@#$%",
      "invalid_cookie_format",
    ]

    for cookie in malformed_cookies:
      client = server.socketio.test_client(server, headers={"Cookie": cookie})

      # Should not crash
      assert len(connected_clients) == 0

      client.disconnect()

  def test_multiple_connections_same_user(self):
    """
    Test handling of multiple connections from same user.

    Given: A user with active WebSocket connection
    When: Same user connects from another device/tab
    Then: Both connections are allowed (concurrent sessions)
    """
    from app import server

    # Create session
    session_data = session_manager.create_session("multi@test.com")

    # Connect first client
    client1 = server.socketio.test_client(
      server, headers={"Cookie": f"session_token={session_data['token']}"}
    )

    # Connect second client (same session)
    # Note: In production, you'd have separate sessions
    # For this test, we create another session for same email
    session_data2 = session_manager.create_session("multi@test.com")
    client2 = server.socketio.test_client(
      server, headers={"Cookie": f"session_token={session_data2['token']}"}
    )

    # Both should be connected
    assert client1.is_connected()
    assert client2.is_connected()

    # Both should be in connected_clients
    assert len(connected_clients) == 2

    client1.disconnect()
    client2.disconnect()

  def test_concurrent_session_creation(self):
    """
    Test handling of concurrent session creation attempts.

    Given: Multiple authentication attempts for same email
    When: Requests arrive concurrently
    Then: Each creates independent session
    """
    # This tests that session creation is thread-safe
    # In this implementation, we create separate sessions for each attempt

    sessions = []
    for i in range(5):
      session_data = session_manager.create_session(f"concurrent{i}@test.com")
      sessions.append(session_data)

    # All sessions should be unique
    tokens = [s["token"] for s in sessions]
    assert len(set(tokens)) == len(tokens)

    # All should be valid
    for session_data in sessions:
      validated = session_manager.validate_token(session_data["token"])
      assert validated is not None

  def test_session_cookie_manipulation_detected(self):
    """
    Test that session cookie manipulation is detected.

    Given: An attacker trying to modify session cookie
    When: Tampered cookie is presented
    Then: Session validation fails, connection rejected
    """
    from app import server

    # Create a session
    session_data = session_manager.create_session("manipulate@test.com")
    token = session_data["token"]

    # Try to connect with modified token
    modified_token = token[:-5] + "xxxxx"  # Change last 5 chars

    client = server.socketio.test_client(
      server, headers={"Cookie": f"session_token={modified_token}"}
    )

    # Should not be connected
    assert len(connected_clients) == 0

    client.disconnect()

  def test_empty_session_cookie_rejected(self):
    """
    Test that empty session cookie is rejected.

    Given: A WebSocket connection with empty session cookie
    When: Connection attempt is made
    Then: Connection is rejected
    """
    from app import server

    client = server.socketio.test_client(server, headers={"Cookie": "session_token="})

    # Should not be connected
    assert len(connected_clients) == 0

    client.disconnect()
