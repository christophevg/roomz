"""
Unit tests for app helper functions.

Tests for:
- count_user_connections: Count active connections per user
- extract_token_from_cookie: Extract session token from HTTP cookie header
"""


from roomz.server import count_user_connections, extract_token_from_cookie


class TestCountUserConnections:
  """Tests for count_user_connections function."""

  def test_count_zero_connections(self, monkeypatch):
    """Count should return 0 when user has no connections."""
    monkeypatch.setattr("roomz.server.connected_clients", {})
    result = count_user_connections("user@example.com")
    assert result == 0

  def test_count_one_connection(self, monkeypatch):
    """Count should return 1 when user has one connection."""
    monkeypatch.setattr(
      "roomz.server.connected_clients",
      {
        "sid1": {"email": "user@example.com"},
        "sid2": {"email": "other@example.com"},
      },
    )
    result = count_user_connections("user@example.com")
    assert result == 1

  def test_count_multiple_connections(self, monkeypatch):
    """Count should return correct number when user has multiple connections."""
    monkeypatch.setattr(
      "roomz.server.connected_clients",
      {
        "sid1": {"email": "user@example.com"},
        "sid2": {"email": "user@example.com"},
        "sid3": {"email": "other@example.com"},
        "sid4": {"email": "user@example.com"},
      },
    )
    result = count_user_connections("user@example.com")
    assert result == 3

  def test_count_after_connection_added(self, monkeypatch):
    """Count should reflect new connections."""
    clients = {}
    monkeypatch.setattr("roomz.server.connected_clients", clients)

    # Initially 0
    assert count_user_connections("user@example.com") == 0

    # Add a connection
    clients["sid1"] = {"email": "user@example.com"}
    assert count_user_connections("user@example.com") == 1

    # Add another connection
    clients["sid2"] = {"email": "user@example.com"}
    assert count_user_connections("user@example.com") == 2

  def test_count_after_connection_removed(self, monkeypatch):
    """Count should reflect disconnections."""
    clients = {
      "sid1": {"email": "user@example.com"},
      "sid2": {"email": "user@example.com"},
    }
    monkeypatch.setattr("roomz.server.connected_clients", clients)

    # Initially 2
    assert count_user_connections("user@example.com") == 2

    # Remove one connection
    del clients["sid1"]
    assert count_user_connections("user@example.com") == 1

    # Remove last connection
    del clients["sid2"]
    assert count_user_connections("user@example.com") == 0

  def test_count_case_sensitive(self, monkeypatch):
    """Email comparison should be case-sensitive (emails are normalized at entry)."""
    monkeypatch.setattr(
      "roomz.server.connected_clients",
      {"sid1": {"email": "user@example.com"}},
    )
    # Exact match
    assert count_user_connections("user@example.com") == 1
    # Different case
    assert count_user_connections("User@example.com") == 0


class TestExtractTokenFromCookie:
  """Tests for extract_token_from_cookie function."""

  def test_extract_valid_token(self):
    """Should extract session_token from valid cookie string."""
    cookies = "session_token=abc123; other=value"
    result = extract_token_from_cookie(cookies)
    assert result == "abc123"

  def test_extract_token_only_cookie(self):
    """Should extract token when it's the only cookie."""
    cookies = "session_token=xyz789"
    result = extract_token_from_cookie(cookies)
    assert result == "xyz789"

  def test_extract_token_with_equals_in_value(self):
    """Should handle tokens containing equals signs."""
    cookies = "session_token=jwt.header.payload"
    result = extract_token_from_cookie(cookies)
    assert result == "jwt.header.payload"

  def test_missing_session_token(self):
    """Should return None when session_token is not in cookies."""
    cookies = "other=value; another=cookie"
    result = extract_token_from_cookie(cookies)
    assert result is None

  def test_empty_cookies(self):
    """Should return None when cookies string is empty."""
    result = extract_token_from_cookie("")
    assert result is None

  def test_none_cookies(self):
    """Should return None when cookies is None."""
    result = extract_token_from_cookie(None)
    assert result is None

  def test_whitespace_around_cookies(self):
    """Should handle whitespace around cookie values."""
    cookies = "  session_token=abc123  ;  other=value  "
    result = extract_token_from_cookie(cookies)
    assert result == "abc123"

  def test_session_token_at_end(self):
    """Should find session_token when it's the last cookie."""
    cookies = "first=value; session_token=lasttoken"
    result = extract_token_from_cookie(cookies)
    assert result == "lasttoken"
