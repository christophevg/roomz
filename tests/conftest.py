"""
Pytest fixtures for Roomz testing.

This module provides test fixtures for SocketIO testing, Quart test client,
and mock configurations.
"""

import pytest
from app import server, connected_clients


@pytest.fixture
def test_client():
  """
  Quart test client fixture for HTTP endpoint testing.

  Provides a test client that can make HTTP requests to the application
  without starting a real server.

  Returns:
    Quart test client instance
  """
  return server.test_client()


@pytest.fixture
def socketio_client():
  """
  SocketIO test client fixture for WebSocket testing.

  Provides a SocketIO test client that can connect to the server
  and send/receive SocketIO events.

  Returns:
    SocketIO test client instance
  """
  # Clear connected clients before each test
  connected_clients.clear()

  # Create SocketIO test client
  client = server.socketio.test_client(server)

  yield client

  # Cleanup after test
  client.disconnect()
  connected_clients.clear()


@pytest.fixture
def multiple_socketio_clients():
  """
  Multiple SocketIO clients for broadcast testing.

  Creates multiple connected clients to test message broadcasting
  across multiple connections.

  Returns:
    List of connected SocketIO test clients
  """
  # Clear connected clients before each test
  connected_clients.clear()

  clients = []
  for _ in range(3):
    client = server.socketio.test_client(server)
    clients.append(client)

  yield clients

  # Cleanup after test
  for client in clients:
    client.disconnect()
  connected_clients.clear()


@pytest.fixture
def connected_clients_tracker():
  """
  In-memory tracker for connected clients.

  Provides access to the connected_clients set used by the server
  to track active connections.

  Returns:
    Set of connected client session IDs
  """
  # Clear before test
  connected_clients.clear()

  yield connected_clients

  # Clear after test
  connected_clients.clear()