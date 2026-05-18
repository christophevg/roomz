"""
Tests for Per-Device Display Names (I7-001).

This module tests display name functionality allowing users to set custom
names for each device/session, making it easier to identify which device
sent a message in multi-session scenarios.

Requirements from I7-001:
- /name <name> command to set display name at any time
- Web client stores in localStorage, persists across page reloads
- Python client stores in config/env, persists across restarts
- Display name broadcast in presence events
- Message display: "{display name} ({email})" when set, just email when not
- No server storage - fully stateless per connection

Security Requirements:
- Input sanitization (no newlines, max length 50)
- HTML escaping to prevent XSS
- Per-connection storage (ephemeral)
"""

import pytest

from roomz.server import validate_display_name


class TestValidateDisplayName:
  """
  Test suite for validate_display_name function.

  Tests verify that display names are properly validated and sanitized
  to prevent security issues and malformed input.
  """

  def test_valid_display_name_single_char(self):
    """
    Test that single character display name is accepted.

    Given: User sends display_name="A"
    When: Server validates the name
    Then: Name is accepted and returned as "A"
    """
    result = validate_display_name("A")
    assert result == "A"

  def test_valid_display_name_multiple_chars(self):
    """
    Test that multi-character display name is accepted.

    Given: User sends display_name="Laptop"
    When: Server validates the name
    Then: Name is accepted and returned as "Laptop"
    """
    result = validate_display_name("Laptop")
    assert result == "Laptop"

  def test_display_name_max_length_accepted(self):
    """
    Test that display names exactly 50 characters are accepted.

    Given: User sends set_display_name with exactly 50 characters
    When: Server validates the name
    Then: Server acknowledges with {status: "ok", display_name: <name>}
    """
    name_50_chars = "A" * 50
    result = validate_display_name(name_50_chars)
    assert result == name_50_chars

  def test_display_name_over_max_length_rejected(self):
    """
    Test that display names over 50 characters are rejected.

    Given: User sends set_display_name with 51 character name
    When: Server validates the name
    Then: Server returns None (invalid)
    """
    name_51_chars = "A" * 51
    result = validate_display_name(name_51_chars)
    assert result is None

  def test_display_name_empty_string_returns_none(self):
    """
    Test that empty string returns None.

    Given: User sends set_display_name with empty string ""
    When: Server processes the request
    Then: Display name returns None (cleared)
    """
    result = validate_display_name("")
    assert result is None

  def test_display_name_whitespace_only_returns_none(self):
    """
    Test that whitespace-only names return None.

    Given: User sends set_display_name with "   " (whitespace only)
    When: Server processes the request
    Then: Display name returns None (trimmed to empty)
    """
    result = validate_display_name("   ")
    assert result is None

  def test_display_name_newlines_rejected(self):
    """
    Test that display names with newlines are rejected.

    Given: User sends set_display_name with "Laptop\\nPhone"
    When: Server validates the name
    Then: Server returns None (invalid)
    """
    result = validate_display_name("Laptop\nPhone")
    assert result is None

  def test_display_name_newline_at_start_stripped(self):
    """
    Test that display names with newline at start are stripped and accepted.

    Given: User sends display_name="\\nLaptop"
    When: Server validates the name
    Then: Newline is stripped, result is "Laptop"
    """
    result = validate_display_name("\nLaptop")
    assert result == "Laptop"

  def test_display_name_newline_at_end_stripped(self):
    """
    Test that display names with newline at end are stripped and accepted.

    Given: User sends display_name="Laptop\\n"
    When: Server validates the name
    Then: Newline is stripped, result is "Laptop"
    """
    result = validate_display_name("Laptop\n")
    assert result == "Laptop"

  def test_display_name_carriage_return_rejected(self):
    """
    Test that display names with carriage returns are rejected.

    Given: User sends set_display_name with "Laptop\\rPhone"
    When: Server validates the name
    Then: Server returns None (invalid)
    """
    result = validate_display_name("Laptop\rPhone")
    assert result is None

  def test_display_name_carriage_return_at_start_stripped(self):
    """
    Test that display names with carriage return at start are stripped and accepted.

    Given: User sends display_name="\\rLaptop"
    When: Server validates the name
    Then: Carriage return is stripped, result is "Laptop"
    """
    result = validate_display_name("\rLaptop")
    assert result == "Laptop"

  def test_display_name_crlf_rejected(self):
    """
    Test that display names with CRLF are rejected.
    """
    result = validate_display_name("Laptop\r\nPhone")
    assert result is None

  def test_display_name_null_byte_rejected(self):
    """
    Test that display names with null byte are rejected.

    Given: User sends set_display_name with null byte
    When: Server validates the name
    Then: Server returns None (invalid)
    """
    result = validate_display_name("Laptop\x00Phone")
    assert result is None

  def test_display_name_control_characters_rejected(self):
    """
    Test that display names with control characters in the MIDDLE are rejected.

    Given: User sends set_display_name with control character in middle
    When: Server validates the name
    Then: Server returns None (invalid)

    Note: Python's .strip() removes certain control characters that are
    considered whitespace (0x09-0x0d, 0x1c-0x1f, 0x20). Other control
    characters (0x00-0x08, 0x0e-0x1b) are NOT stripped and will cause rejection.
    """
    # Control characters in the MIDDLE are rejected
    result = validate_display_name("Laptop\x01Phone")  # SOH in middle
    assert result is None
    result = validate_display_name("Laptop\x02Phone")  # STX in middle
    assert result is None
    result = validate_display_name("Laptop\x1fPhone")  # US in middle
    assert result is None

    # Control characters that ARE whitespace (stripped by .strip())
    result = validate_display_name("Laptop\x1f")  # US (0x1f) at end - whitespace
    assert result == "Laptop"  # After stripping, valid
    result = validate_display_name("\x1cLaptop")  # FS (0x1c) at start - whitespace
    assert result == "Laptop"  # After stripping, valid

    # Control characters that are NOT whitespace (rejected, not stripped)
    result = validate_display_name("Laptop\x02")  # STX (0x02) at end - not whitespace
    assert result is None  # Not stripped, so rejected
    result = validate_display_name("\x01Laptop")  # SOH (0x01) at start - not whitespace
    assert result is None  # Not stripped, so rejected

  def test_display_name_tab_allowed(self):
    """
    Test that display names can contain tabs.

    Given: User sends set_display_name with "My\\tLaptop"
    When: Server validates the name
    Then: Server accepts the name (tab is allowed)
    """
    result = validate_display_name("My\tLaptop")
    assert result == "My\tLaptop"

  def test_display_name_tab_at_start_allowed(self):
    """
    Test that display names with tab at start are allowed (but trimmed).
    """
    result = validate_display_name("\tLaptop")
    # After stripping and escaping
    assert result is not None

  def test_display_name_html_escaped(self):
    """
    Test that display names with HTML are escaped.

    Given: User sends set_display_name with "<script>alert('xss')</script>"
    When: Server processes the name
    Then: Display name is escaped with html.escape()

    Note: html.escape() also escapes single quotes as &#x27;
    """
    result = validate_display_name("<script>alert('xss')</script>")
    assert result == "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;"

  def test_display_name_html_ampersand_escaped(self):
    """
    Test that ampersand is escaped in display names.
    """
    result = validate_display_name("Tom & Jerry")
    assert result == "Tom &amp; Jerry"

  def test_display_name_html_quotes_escaped(self):
    """
    Test that quotes are escaped in display names.
    """
    result = validate_display_name('He said "Hello"')
    assert result == "He said &quot;Hello&quot;"

  def test_display_name_unicode_allowed(self):
    """
    Test that display names can contain unicode characters.

    Given: User sends set_display_name with "Laptop 💻" or "工作电脑"
    When: Server validates the name
    Then: Server accepts the name (unicode is allowed)
    """
    # Emoji
    result = validate_display_name("Laptop 💻")
    assert result == "Laptop 💻"

    # Chinese characters
    result = validate_display_name("工作电脑")
    assert result == "工作电脑"

    # Arabic
    result = validate_display_name("حاسوب")
    assert result == "حاسوب"

    # Japanese
    result = validate_display_name("ノートPC")
    assert result == "ノートPC"

  def test_display_name_trimmed(self):
    """
    Test that display names are trimmed.

    Given: User sends set_display_name with "  Laptop  "
    When: Server processes the name
    Then: Display name is stored as "Laptop" (trimmed)
    """
    result = validate_display_name("  Laptop  ")
    assert result == "Laptop"

  def test_display_name_none_returns_none(self):
    """
    Test that None input returns None.

    Given: User sends set_display_name with None
    When: Server validates the name
    Then: Server returns None
    """
    result = validate_display_name(None)
    assert result is None

  def test_display_name_only_spaces_after_trim_returns_none(self):
    """
    Test that name with only spaces returns None after trimming.
    """
    result = validate_display_name("     ")
    assert result is None

  def test_display_name_only_tabs_after_trim(self):
    """
    Test that name with only tabs returns None after trimming.
    """
    result = validate_display_name("\t\t\t")
    assert result is None

  def test_display_name_preserves_internal_spaces(self):
    """
    Test that internal spaces are preserved.
    """
    result = validate_display_name("My Laptop")
    assert result == "My Laptop"

  def test_display_name_special_chars_allowed(self):
    """
    Test that special characters are allowed (except newlines/control chars).
    """
    result = validate_display_name("Laptop-123_Test!")
    assert result == "Laptop-123_Test!"

  def test_display_name_at_sign_allowed(self):
    """
    Test that @ sign is allowed in display names.
    """
    result = validate_display_name("user@domain")
    assert result == "user@domain"

  def test_display_name_max_length_after_trim(self):
    """
    Test that length is checked after trimming.
    """
    # 50 chars with leading/trailing spaces should still be valid
    name = "A" * 50
    result = validate_display_name(f"  {name}  ")
    assert result == name

  def test_display_name_over_max_after_trim_still_rejected(self):
    """
    Test that length is checked after trimming.
    """
    # 51 chars with leading/trailing spaces - still too long
    name = "A" * 51
    result = validate_display_name(f"  {name}  ")
    assert result is None


class TestValidateDisplayNameEdgeCases:
  """
  Test suite for display name edge cases.
  """

  def test_display_name_with_backslash(self):
    """
    Test that backslash is allowed in display names.
    """
    result = validate_display_name("Laptop\\Desktop")
    assert result == "Laptop\\Desktop"

  def test_display_name_with_forward_slash(self):
    """
    Test that forward slash is allowed in display names.
    """
    result = validate_display_name("Laptop/Desktop")
    assert result == "Laptop/Desktop"

  def test_display_name_with_parentheses(self):
    """
    Test that parentheses are allowed in display names.
    """
    result = validate_display_name("Laptop (Primary)")
    assert result == "Laptop (Primary)"

  def test_display_name_with_brackets(self):
    """
    Test that brackets are allowed in display names.
    """
    result = validate_display_name("Laptop [Work]")
    assert result == "Laptop [Work]"

  def test_display_name_with_curly_braces(self):
    """
    Test that curly braces are allowed in display names.
    """
    result = validate_display_name("Device {1}")
    assert result == "Device {1}"

  def test_display_name_with_pipe(self):
    """
    Test that pipe character is allowed in display names.
    """
    result = validate_display_name("Home | Work")
    assert result == "Home | Work"

  def test_display_name_with_dollar_sign(self):
    """
    Test that dollar sign is allowed in display names.
    """
    result = validate_display_name("Device $1")
    assert result == "Device $1"

  def test_display_name_with_percent(self):
    """
    Test that percent sign is allowed in display names.
    """
    result = validate_display_name("100% Charged")
    assert result == "100% Charged"

  def test_display_name_with_hashtag(self):
    """
    Test that hashtag is allowed in display names.
    """
    result = validate_display_name("#1 Device")
    assert result == "#1 Device"

  def test_display_name_with_asterisk(self):
    """
    Test that asterisk is allowed in display names.
    """
    result = validate_display_name("Device *2")
    assert result == "Device *2"

  def test_display_name_with_plus_sign(self):
    """
    Test that plus sign is allowed in display names.
    """
    result = validate_display_name("Device+")
    assert result == "Device+"

  def test_display_name_with_equals_sign(self):
    """
    Test that equals sign is allowed in display names.
    """
    result = validate_display_name("A=B")
    assert result == "A=B"

  def test_display_name_with_tilde(self):
    """
    Test that tilde is allowed in display names.
    """
    result = validate_display_name("Device ~")
    assert result == "Device ~"

  def test_display_name_with_grave_accent(self):
    """
    Test that grave accent is allowed in display names.
    """
    result = validate_display_name("`code`")
    assert result == "`code`"

  def test_display_name_with_caret(self):
    """
    Test that caret is allowed in display names.
    """
    result = validate_display_name("Device^1")
    assert result == "Device^1"

  def test_display_name_with_exclamation(self):
    """
    Test that exclamation is allowed in display names.
    """
    result = validate_display_name("Hello!")
    assert result == "Hello!"

  def test_display_name_with_question_mark(self):
    """
    Test that question mark is allowed in display names.
    """
    result = validate_display_name("Device?")
    assert result == "Device?"

  def test_display_name_with_colon(self):
    """
    Test that colon is allowed in display names.
    """
    result = validate_display_name("Note: Primary")
    assert result == "Note: Primary"

  def test_display_name_with_semicolon(self):
    """
    Test that semicolon is allowed in display names.
    """
    result = validate_display_name("Device;1")
    assert result == "Device;1"

  def test_display_name_with_comma(self):
    """
    Test that comma is allowed in display names.
    """
    result = validate_display_name("Laptop, Phone")
    assert result == "Laptop, Phone"

  def test_display_name_with_period(self):
    """
    Test that period is allowed in display names.
    """
    result = validate_display_name("Device 2.0")
    assert result == "Device 2.0"

  def test_display_name_with_underscore(self):
    """
    Test that underscore is allowed in display names.
    """
    result = validate_display_name("My_Device")
    assert result == "My_Device"

  def test_display_name_with_hyphen(self):
    """
    Test that hyphen is allowed in display names.
    """
    result = validate_display_name("My-Device")
    assert result == "My-Device"

  def test_display_name_multiple_spaces_collapsed(self):
    """
    Test that multiple internal spaces are preserved (not collapsed).
    """
    result = validate_display_name("My   Laptop")
    assert result == "My   Laptop"


class TestValidateDisplayNameSecurity:
  """
  Test suite for display name security considerations.

  Tests verify that display names don't introduce security vulnerabilities.
  """

  def test_xss_prevention_script_tag(self):
    """
    Test that XSS is prevented in display names with script tag.
    """
    result = validate_display_name("<script>alert('xss')</script>")
    assert "<script>" not in result
    assert "&lt;script&gt;" in result

  def test_xss_prevention_img_tag(self):
    """
    Test that XSS is prevented with img tag.
    """
    result = validate_display_name('<img src="x" onerror="alert(1)">')
    assert "<img" not in result
    assert "&lt;img" in result

  def test_xss_prevention_event_handler(self):
    """
    Test that XSS is prevented with event handlers.
    """
    result = validate_display_name('<div onclick="alert(1)">')
    assert "<div" not in result
    assert "&lt;div" in result

  def test_xss_prevention_javascript_url(self):
    """
    Test that XSS is prevented with javascript: URL.
    """
    result = validate_display_name('<a href="javascript:alert(1)">')
    assert "&lt;a" in result
    assert "javascript:" not in result or "&quot;" in result

  def test_log_injection_newline_prevented(self):
    """
    Test that display names don't allow log injection with newline.

    Given: User sends set_display_name with "Admin\\n[ERROR] Fake log entry"
    When: Server validates the name
    Then: Name is rejected (None returned)
    """
    result = validate_display_name("Admin\n[ERROR] Fake log entry")
    assert result is None

  def test_log_injection_carriage_return_prevented(self):
    """
    Test that display names don't allow log injection with carriage return.
    """
    result = validate_display_name("Admin\r[ERROR] Fake log entry")
    assert result is None

  def test_log_injection_crlf_prevented(self):
    """
    Test that display names don't allow log injection with CRLF.
    """
    result = validate_display_name("Admin\r\n[ERROR] Fake log entry")
    assert result is None


# =============================================================================
# Integration Tests (require running server)
# =============================================================================


@pytest.mark.skip(
  reason="Integration test requires running SocketIO server with test_client support"
)
class TestSetDisplayNameEvent:
  """
  Test suite for the set_display_name WebSocket event.

  Tests verify that display names can be set, changed, and cleared
  via the WebSocket API. These tests require integration test setup.
  """

  def test_set_display_name_success(self):
    """
    Test setting display name successfully.

    Given: An authenticated user connected via WebSocket
    When: User sends set_display_name event with display_name="Laptop"
    Then: Server acknowledges with {status: "ok", display_name: "Laptop"}
    And: Display name is stored in connected_clients[sid]["display_name"]
    """
    pytest.fail("Integration test not implemented: Requires running server")

  def test_set_display_name_stored_on_connection(self):
    """
    Test that display name is stored in connection info.

    Given: User sets display name to "Laptop"
    When: Display name is acknowledged
    Then: connected_clients[sid]["display_name"] equals "Laptop"
    """
    pytest.fail("Integration test not implemented: Requires running server")

  def test_change_display_name(self):
    """
    Test changing display name.

    Given: User has display name "Laptop"
    When: User sends set_display_name with display_name="Phone"
    Then: Server acknowledges with {status: "ok", display_name: "Phone"}
    And: connected_clients[sid]["display_name"] updated to "Phone"
    """
    pytest.fail("Integration test not implemented: Requires running server")

  def test_clear_display_name(self):
    """
    Test clearing display name.

    Given: User has display name "Laptop"
    When: User sends set_display_name with display_name=null
    Then: Server acknowledges with {status: "ok", display_name: null}
    And: connected_clients[sid]["display_name"] is None
    """
    pytest.fail("Integration test not implemented: Requires running server")

  def test_set_display_name_on_connect(self):
    """
    Test that client can set display name immediately after authentication.

    Given: Authenticated client with display name stored locally
    When: Client connects and receives authenticated event
    Then: Client sends set_display_name with stored value
    And: Server acknowledges and stores display name
    """
    pytest.fail("Integration test not implemented: Requires running server")
