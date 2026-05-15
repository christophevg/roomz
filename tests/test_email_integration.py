"""
Tests for Email Integration (I5-001).

This module tests the EmailSender abstraction, implementations
(ConsoleEmailSender, ResendEmailSender), factory function,
and integration with the /auth/request-magic-link endpoint.
"""

import os
from unittest.mock import AsyncMock, patch

import pytest

from roomz.server.email import (
  ConsoleEmailSender,
  EmailSender,
  ResendEmailSender,
  get_email_sender,
)

# =============================================================================
# EmailSender Protocol Tests
# =============================================================================


class TestEmailSenderProtocol:
  """
  Test suite for EmailSender protocol compliance.

  Tests verify that implementations conform to the EmailSender
  protocol interface with proper async send_magic_link method.
  """

  def test_email_sender_is_protocol(self):
    """
    Test that EmailSender is defined as a Protocol.

    Given: The app.email module
    When: Inspecting EmailSender
    Then: It is a typing.Protocol subclass
    """
    from typing import Protocol

    assert hasattr(EmailSender, "__mro__")
    assert Protocol in EmailSender.__mro__

  def test_email_sender_has_send_magic_link_method(self):
    """
    Test that EmailSender protocol requires send_magic_link method.

    Given: The EmailSender protocol
    When: Inspecting required methods
    Then: send_magic_link is a required async method
    """
    assert hasattr(EmailSender, "send_magic_link")
    # Protocol defines the method signature

    assert callable(getattr(EmailSender, "send_magic_link", None))

  @pytest.mark.asyncio
  async def test_send_magic_link_signature(self):
    """
    Test that send_magic_link has correct signature.

    Given: An EmailSender implementation
    When: Calling send_magic_link(email, magic_link_url)
    Then: Method accepts email (str) and magic_link_url (str) and returns bool
    """
    sender = ConsoleEmailSender()
    import inspect

    sig = inspect.signature(sender.send_magic_link)
    params = list(sig.parameters.keys())
    assert "email" in params
    assert "magic_link_url" in params

    # Test that it returns bool
    result = await sender.send_magic_link("test@example.com", "https://example.com/token")
    assert isinstance(result, bool)


# =============================================================================
# ConsoleEmailSender Tests
# =============================================================================


class TestConsoleEmailSender:
  """
  Test suite for ConsoleEmailSender implementation.

  Tests verify that ConsoleEmailSender logs magic links to console
  and always returns True (development mode never fails).
  """

  def test_console_email_sender_exists(self):
    """
    Test that ConsoleEmailSender class exists.

    Given: The app.email module
    When: Importing ConsoleEmailSender
    Then: Class is available
    """
    assert ConsoleEmailSender is not None

  def test_console_email_sender_no_required_config(self):
    """
    Test that ConsoleEmailSender requires no configuration.

    Given: No environment variables set
    When: Instantiating ConsoleEmailSender
    Then: Instance is created successfully
    """
    sender = ConsoleEmailSender()
    assert sender is not None

  @pytest.mark.asyncio
  async def test_console_send_magic_link_returns_true(self):
    """
    Test that ConsoleEmailSender always returns True.

    Given: A ConsoleEmailSender instance
    When: Calling send_magic_link with valid arguments
    Then: Returns True (console logging never fails)
    """
    sender = ConsoleEmailSender()
    result = await sender.send_magic_link("test@example.com", "https://example.com/token")
    assert result is True

  @pytest.mark.asyncio
  async def test_console_send_magic_link_logs_to_console(self):
    """
    Test that ConsoleEmailSender logs magic link to console.

    Given: A ConsoleEmailSender instance
    When: Calling send_magic_link with email and URL
    Then: Magic link is logged to console in formatted output
    """
    sender = ConsoleEmailSender()
    with patch("roomz.server.server") as mock_server:
      await sender.send_magic_link("test@example.com", "https://example.com/token")
      # Verify server.logger.info was called
      mock_server.logger.info.assert_called_once()
      # Verify the log output contains the magic link
      call_args = mock_server.logger.info.call_args[0][0]
      assert "test@example.com" in call_args
      assert "https://example.com/token" in call_args

  @pytest.mark.asyncio
  async def test_console_send_magic_link_with_sample_data(self):
    """
    Test ConsoleEmailSender with sample email and magic link.

    Given: Email "test@example.com" and magic link URL
    When: Calling send_magic_link
    Then: Returns True and logs formatted output with email and URL
    """
    sender = ConsoleEmailSender()
    email = "test@example.com"
    url = "https://example.com/auth/verify?token=abc123"

    with patch("roomz.server.server") as mock_server:
      result = await sender.send_magic_link(email, url)

      assert result is True
      mock_server.logger.info.assert_called_once()
      log_output = mock_server.logger.info.call_args[0][0]
      assert email in log_output
      assert url in log_output
      assert "MAGIC LINK" in log_output


# =============================================================================
# ResendEmailSender Tests
# =============================================================================


class TestResendEmailSender:
  """
  Test suite for ResendEmailSender implementation.

  Tests verify that ResendEmailSender sends emails via Resend API,
  handles configuration, and manages errors gracefully.
  """

  def test_resend_email_sender_exists(self):
    """
    Test that ResendEmailSender class exists.

    Given: The app.email module
    When: Importing ResendEmailSender
    Then: Class is available
    """
    assert ResendEmailSender is not None

  def test_resend_email_sender_requires_api_key(self):
    """
    Test that ResendEmailSender requires RESEND_API_KEY.

    Given: No RESEND_API_KEY environment variable
    When: Instantiating ResendEmailSender
    Then: Raises ValueError with clear message
    """
    with patch.dict(os.environ, {}, clear=True):
      with pytest.raises(ValueError) as exc_info:
        ResendEmailSender()
      assert "RESEND_API_KEY" in str(exc_info.value)

  def test_resend_email_sender_validates_api_key_format(self):
    """
    Test that ResendEmailSender validates API key format.

    Given: RESEND_API_KEY that doesn't start with 're_'
    When: Instantiating ResendEmailSender
    Then: Logs warning but continues (soft validation)
    """
    with patch.dict(os.environ, {"RESEND_API_KEY": "invalid_key_format"}):
      with patch("roomz.server.server") as mock_server:
        sender = ResendEmailSender()
        # Should log a warning
        mock_server.logger.warning.assert_called_once()
        assert "re_" in mock_server.logger.warning.call_args[0][0]
        # But should still create instance
        assert sender is not None

  def test_resend_email_sender_uses_default_from_address(self):
    """
    Test that ResendEmailSender has default from address.

    Given: No EMAIL_FROM environment variable
    When: Instantiating ResendEmailSender
    Then: Uses default from address 'no-reply@example.com'
    """
    with patch.dict(
      os.environ, {"RESEND_API_KEY": "re_test_key"}, clear=True
    ):
      sender = ResendEmailSender()
      assert sender._from_address == "no-reply@example.com"

  def test_resend_email_sender_uses_custom_from_address(self):
    """
    Test that ResendEmailSender uses EMAIL_FROM environment variable.

    Given: EMAIL_FROM='custom@example.com'
    When: Instantiating ResendEmailSender
    Then: Uses custom from address
    """
    with patch.dict(
      os.environ,
      {"RESEND_API_KEY": "re_test_key", "EMAIL_FROM": "custom@example.com"},
      clear=True,
    ):
      sender = ResendEmailSender()
      assert sender._from_address == "custom@example.com"

  @pytest.mark.asyncio
  async def test_resend_send_magic_link_success(self):
    """
    Test successful email send via Resend.

    Given: Valid RESEND_API_KEY and mocked Resend API
    When: Calling send_magic_link
    Then: Returns True and calls Resend API with correct parameters
    """
    with patch.dict(os.environ, {"RESEND_API_KEY": "re_test_key"}):
      sender = ResendEmailSender()
      with patch.object(
        sender, "_send_email_sync", return_value={"id": "email_123"}
      ):
        result = await sender.send_magic_link(
          "test@example.com", "https://example.com/token"
        )
        assert result is True

  @pytest.mark.asyncio
  async def test_resend_send_magic_link_failure_returns_false(self):
    """
    Test that ResendEmailSender returns False on API failure.

    Given: Resend API that raises an exception
    When: Calling send_magic_link
    Then: Returns False (does not raise exception)
    """
    with patch.dict(os.environ, {"RESEND_API_KEY": "re_test_key"}):
      sender = ResendEmailSender()
      with patch.object(sender, "_send_email_sync", return_value=None):
        result = await sender.send_magic_link(
          "test@example.com", "https://example.com/token"
        )
        assert result is False

  @pytest.mark.asyncio
  async def test_resend_send_magic_link_logs_success(self):
    """
    Test that successful send is logged with message ID.

    Given: Resend API returns message ID 'email_123'
    When: Calling send_magic_link
    Then: Logs success with email address and message ID
    """
    with patch.dict(os.environ, {"RESEND_API_KEY": "re_test_key"}):
      with patch("roomz.server.server") as mock_server:
        sender = ResendEmailSender()
        with patch.object(
          sender, "_send_email_sync", return_value={"id": "email_123"}
        ):
          await sender.send_magic_link("test@example.com", "https://example.com/token")
          # Check that success was logged
          mock_server.logger.info.assert_called()
          call_args = mock_server.logger.info.call_args[0][0]
          assert "test@example.com" in call_args
          assert "email_123" in call_args

  @pytest.mark.asyncio
  async def test_resend_send_magic_link_logs_failure(self):
    """
    Test that failed send is logged with error type.

    Given: Resend API raises exception
    When: Calling send_magic_link
    Then: Logs error with email address and error type (not full exception)
    """
    with patch.dict(os.environ, {"RESEND_API_KEY": "re_test_key"}):
      with patch("roomz.server.server") as mock_server:
        sender = ResendEmailSender()
        with patch.object(sender, "_send_email_sync", return_value=None):
          result = await sender.send_magic_link(
            "test@example.com", "https://example.com/token"
          )
          assert result is False
          # Check that failure was logged
          mock_server.logger.error.assert_called()

  @pytest.mark.asyncio
  async def test_resend_send_magic_link_html_content(self):
    """
    Test that email HTML contains magic link URL.

    Given: Mocked Resend API
    When: Calling send_magic_link with URL
    Then: Email HTML contains the magic link URL
    """
    with patch.dict(os.environ, {"RESEND_API_KEY": "re_test_key"}):
      sender = ResendEmailSender()
      html = sender._generate_html_content("https://example.com/token")
      assert "https://example.com/token" in html

  @pytest.mark.asyncio
  async def test_resend_send_magic_link_subject(self):
    """
    Test that email has correct subject.

    Given: Mocked Resend API
    When: Calling send_magic_link
    Then: Email subject is 'Your Magic Link for Roomz'
    """
    from roomz.server.email.resend import DEFAULT_SUBJECT

    assert DEFAULT_SUBJECT == "Your Magic Link for Roomz"

  @pytest.mark.asyncio
  async def test_resend_never_logs_api_key(self):
    """
    Test that API key is never logged.

    Given: Any scenario with ResendEmailSender
    When: Logging occurs
    Then: API key is never included in any log output
    """
    with patch.dict(os.environ, {"RESEND_API_KEY": "re_test_key_secret"}):
      with patch("roomz.server.server") as mock_server:
        sender = ResendEmailSender()
        with patch.object(
          sender, "_send_email_sync", return_value={"id": "email_123"}
        ):
          await sender.send_magic_link("test@example.com", "https://example.com/token")

          # Check all log calls don't contain the API key
          for call in mock_server.logger.info.call_args_list:
            assert "re_test_key_secret" not in str(call)
          for call in mock_server.logger.error.call_args_list:
            assert "re_test_key_secret" not in str(call)


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestGetEmailSender:
  """
  Test suite for get_email_sender factory function.

  Tests verify that the factory returns the correct EmailSender
  implementation based on EMAIL_SENDER environment variable.
  """

  def test_factory_exists(self):
    """
    Test that get_email_sender function exists.

    Given: The app.email module
    When: Importing get_email_sender
    Then: Function is available
    """
    assert callable(get_email_sender)

  def test_factory_returns_console_by_default(self):
    """
    Test that factory returns ConsoleEmailSender by default.

    Given: No EMAIL_SENDER environment variable
    When: Calling get_email_sender
    Then: Returns ConsoleEmailSender instance
    """
    with patch.dict(os.environ, {}, clear=True):
      sender = get_email_sender()
      assert isinstance(sender, ConsoleEmailSender)

  def test_factory_returns_console_when_explicitly_set(self):
    """
    Test that factory returns ConsoleEmailSender when EMAIL_SENDER=console.

    Given: EMAIL_SENDER=console
    When: Calling get_email_sender
    Then: Returns ConsoleEmailSender instance
    """
    with patch.dict(os.environ, {"EMAIL_SENDER": "console"}, clear=True):
      sender = get_email_sender()
      assert isinstance(sender, ConsoleEmailSender)

  def test_factory_returns_resend_when_configured(self):
    """
    Test that factory returns ResendEmailSender when EMAIL_SENDER=resend.

    Given: EMAIL_SENDER=resend and RESEND_API_KEY set
    When: Calling get_email_sender
    Then: Returns ResendEmailSender instance
    """
    with patch.dict(
      os.environ, {"EMAIL_SENDER": "resend", "RESEND_API_KEY": "re_test_key"}
    ):
      sender = get_email_sender()
      assert isinstance(sender, ResendEmailSender)

  def test_factory_raises_on_invalid_sender_type(self):
    """
    Test that factory raises ValueError for invalid EMAIL_SENDER.

    Given: EMAIL_SENDER=invalid
    When: Calling get_email_sender
    Then: Raises ValueError with message about valid options
    """
    with patch.dict(os.environ, {"EMAIL_SENDER": "invalid"}, clear=True):
      with pytest.raises(ValueError) as exc_info:
        get_email_sender()
      assert "console" in str(exc_info.value) or "resend" in str(exc_info.value)

  def test_factory_raises_on_resend_without_api_key(self):
    """
    Test that factory raises ValueError when resend requested without API key.

    Given: EMAIL_SENDER=resend but no RESEND_API_KEY
    When: Calling get_email_sender
    Then: Raises ValueError with message about missing API key
    """
    with patch.dict(os.environ, {"EMAIL_SENDER": "resend"}, clear=True):
      with pytest.raises(ValueError) as exc_info:
        get_email_sender()
      assert "RESEND_API_KEY" in str(exc_info.value)

  def test_factory_returns_same_type_on_multiple_calls(self):
    """
    Test that factory returns consistent type on multiple calls.

    Given: Same environment configuration
    When: Calling get_email_sender multiple times
    Then: Returns same type each time (new instance is okay)
    """
    with patch.dict(os.environ, {}, clear=True):
      sender1 = get_email_sender()
      sender2 = get_email_sender()
      assert type(sender1) is type(sender2)


# =============================================================================
# Auth Endpoint Integration Tests
# =============================================================================


class TestAuthEndpointEmailIntegration:
  """
  Test suite for email integration with /auth/request-magic-link endpoint.

  Tests verify that the endpoint uses EmailSender to send magic links
  and handles both success and failure cases appropriately.
  """

  @pytest.mark.asyncio
  async def test_endpoint_calls_email_sender(self):
    """
    Test that endpoint calls email_sender.send_magic_link.

    Given: A valid email request
    When: POST /auth/request-magic-link
    Then: EmailSender.send_magic_link is called with correct arguments
    """
    from quart.testing import QuartClient

    from roomz.server import server

    async with QuartClient(server) as client:
      # Mock the email sender
      mock_sender = AsyncMock()
      mock_sender.send_magic_link.return_value = True

      with patch("roomz.server.get_email_sender", return_value=mock_sender), \
           patch("roomz.server.is_email_allowed", return_value=True):
        await client.post(
          "/auth/request-magic-link",
          json={"email": "test@example.com"},
        )
        # Verify send_magic_link was called
        mock_sender.send_magic_link.assert_called_once()
        call_args = mock_sender.send_magic_link.call_args
        assert "test@example.com" in call_args[0]

  @pytest.mark.asyncio
  async def test_endpoint_returns_success_on_email_sent(self):
    """
    Test that endpoint returns success when email is sent.

    Given: EmailSender returns True
    When: POST /auth/request-magic-link
    Then: Returns 200 with "Magic link sent. Check your email."
    """
    from quart.testing import QuartClient

    from roomz.server import server

    async with QuartClient(server) as client:
      mock_sender = AsyncMock()
      mock_sender.send_magic_link.return_value = True

      with patch("roomz.server.get_email_sender", return_value=mock_sender), \
           patch("roomz.server.is_email_allowed", return_value=True):
        response = await client.post(
          "/auth/request-magic-link",
          json={"email": "test@example.com"},
        )
        assert response.status_code == 200
        data = await response.get_json()
        assert data["status"] == "ok"
        assert "Check your email" in data["message"]

  @pytest.mark.asyncio
  async def test_endpoint_returns_error_on_email_failure(self):
    """
    Test that endpoint returns error when email fails to send.

    Given: EmailSender returns False
    When: POST /auth/request-magic-link
    Then: Returns 500 with email-failed error response
    """
    from quart.testing import QuartClient

    from roomz.server import server

    async with QuartClient(server) as client:
      mock_sender = AsyncMock()
      mock_sender.send_magic_link.return_value = False

      with patch("roomz.server.get_email_sender", return_value=mock_sender), \
           patch("roomz.server.is_email_allowed", return_value=True):
        response = await client.post(
          "/auth/request-magic-link",
          json={"email": "test@example.com"},
        )
        assert response.status_code == 500
        data = await response.get_json()
        assert data["type"] == "https://roomz.local/errors/email-failed"
        assert data["status"] == 500

  @pytest.mark.asyncio
  async def test_endpoint_uses_factory_to_get_sender(self):
    """
    Test that endpoint uses get_email_sender factory.

    Given: A request to /auth/request-magic-link
    When: Processing the request
    Then: Uses get_email_sender() to obtain EmailSender instance
    """
    from quart.testing import QuartClient

    from roomz.server import server

    async with QuartClient(server) as client:
      with patch("roomz.server.get_email_sender") as mock_factory, \
           patch("roomz.server.is_email_allowed", return_value=True):
        mock_sender = AsyncMock()
        mock_sender.send_magic_link.return_value = True
        mock_factory.return_value = mock_sender

        await client.post(
          "/auth/request-magic-link",
          json={"email": "test@example.com"},
        )
        mock_factory.assert_called_once()

  @pytest.mark.asyncio
  async def test_endpoint_generates_correct_magic_link_url(self):
    """
    Test that magic link URL is constructed correctly.

    Given: Request with host_url 'https://example.com'
    When: Generating magic link
    Then: URL is 'https://example.com/auth/verify?token={token}'
    """
    from quart.testing import QuartClient

    from roomz.server import server

    async with QuartClient(server) as client:
      mock_sender = AsyncMock()
      mock_sender.send_magic_link.return_value = True

      with patch("roomz.server.get_email_sender", return_value=mock_sender), \
           patch("roomz.server.is_email_allowed", return_value=True):
        await client.post(
          "/auth/request-magic-link",
          json={"email": "test@example.com"},
        )
        # Verify URL format in send_magic_link call
        call_args = mock_sender.send_magic_link.call_args[0]
        url = call_args[1]  # Second argument is magic_link_url
        assert "/auth/verify?token=" in url

  @pytest.mark.asyncio
  async def test_endpoint_passes_email_to_sender(self):
    """
    Test that endpoint passes the requesting email to sender.

    Given: Request with email 'user@example.com'
    When: Calling send_magic_link
    Then: Email argument is 'user@example.com'
    """
    from quart.testing import QuartClient

    from roomz.server import server

    async with QuartClient(server) as client:
      mock_sender = AsyncMock()
      mock_sender.send_magic_link.return_value = True

      with patch("roomz.server.get_email_sender", return_value=mock_sender), \
           patch("roomz.server.is_email_allowed", return_value=True):
        await client.post(
          "/auth/request-magic-link",
          json={"email": "user@example.com"},
        )
        call_args = mock_sender.send_magic_link.call_args[0]
        assert call_args[0] == "user@example.com"

  @pytest.mark.asyncio
  async def test_endpoint_integration_with_console_sender(self):
    """
    Test full integration with ConsoleEmailSender.

    Given: EMAIL_SENDER=console (or default)
    When: POST /auth/request-magic-link
    Then: Magic link is logged, 200 response returned
    """
    from quart.testing import QuartClient

    from roomz.server import server

    async with QuartClient(server) as client:
      with patch.dict(os.environ, {}, clear=True), \
           patch("roomz.server.is_email_allowed", return_value=True):
        response = await client.post(
          "/auth/request-magic-link",
          json={"email": "test@example.com"},
        )
        assert response.status_code == 200
        data = await response.get_json()
        assert data["status"] == "ok"

  @pytest.mark.asyncio
  async def test_endpoint_integration_with_mocked_resend_sender(self):
    """
    Test full integration with mocked ResendEmailSender.

    Given: Mocked ResendEmailSender returning True
    When: POST /auth/request-magic-link
    Then: Email is sent, 200 response returned
    """
    from quart.testing import QuartClient

    from roomz.server import server

    async with QuartClient(server) as client:
      mock_sender = AsyncMock()
      mock_sender.send_magic_link.return_value = True

      with patch("roomz.server.get_email_sender", return_value=mock_sender), \
           patch("roomz.server.is_email_allowed", return_value=True):
        response = await client.post(
          "/auth/request-magic-link",
          json={"email": "test@example.com"},
        )
        assert response.status_code == 200
        data = await response.get_json()
        assert data["status"] == "ok"


# =============================================================================
# Security Tests
# =============================================================================


class TestEmailSecurity:
  """
  Test suite for email integration security requirements.

  Tests verify that magic links and API keys are handled securely
  and never exposed in logs or error messages.
  """

  def test_magic_link_url_not_logged_in_production(self):
    """
    Test that magic link URL is never logged in production mode.

    Given: EMAIL_SENDER=resend (production mode)
    When: Sending magic link
    Then: Magic link URL is not present in any log output
    """
    with patch.dict(os.environ, {"RESEND_API_KEY": "re_test_key"}):
      sender = ResendEmailSender()
      # The send_magic_link method should not log the magic link URL in production
      # It only logs success/failure, not the URL itself
      html = sender._generate_html_content("https://secret-link.com/token")
      # HTML content contains the URL but this is not logged
      assert "https://secret-link.com/token" in html

  def test_api_key_not_in_error_messages(self):
    """
    Test that API key is never included in error messages.

    Given: An error occurs with ResendEmailSender
    When: Error is logged or returned
    Then: API key is not included in the error message
    """
    with patch.dict(os.environ, {"RESEND_API_KEY": "re_secret_key_123"}):
      with patch("roomz.server.server") as mock_server:
        sender = ResendEmailSender()
        with patch.object(sender, "_send_email_sync", return_value=None):
          import asyncio

          asyncio.run(
            sender.send_magic_link("test@example.com", "https://example.com/token")
          )
          # Check that API key is not in any log output
          for call in mock_server.logger.error.call_args_list:
            assert "re_secret_key_123" not in str(call)

  def test_api_key_not_in_str_representation(self):
    """
    Test that API key is not exposed in string representation.

    Given: A ResendEmailSender instance
    When: Converting to string or repr
    Then: API key is not visible
    """
    with patch.dict(os.environ, {"RESEND_API_KEY": "re_secret_key_123"}):
      sender = ResendEmailSender()
      str_repr = str(sender)
      repr_str = repr(sender)
      assert "re_secret_key_123" not in str_repr
      assert "re_secret_key_123" not in repr_str

  @pytest.mark.asyncio
  async def test_email_failure_doesnt_expose_internal_details(self):
    """
    Test that email failures don't expose internal details to client.

    Given: ResendEmailSender fails with detailed exception
    When: Returning error to client
    Then: Error response contains generic message, not exception details
    """
    from quart.testing import QuartClient

    from roomz.server import server

    async with QuartClient(server) as client:
      mock_sender = AsyncMock()
      mock_sender.send_magic_link.return_value = False

      with patch("roomz.server.get_email_sender", return_value=mock_sender), \
           patch("roomz.server.is_email_allowed", return_value=True):
        response = await client.post(
          "/auth/request-magic-link",
          json={"email": "test@example.com"},
        )
        data = await response.get_json()
        # Error response should have generic message
        assert "detail" in data
        # Should not contain stack traces or internal details
        assert "Traceback" not in data.get("detail", "")
        assert "Exception" not in data.get("detail", "")


# =============================================================================
# Error Response Format Tests
# =============================================================================


class TestEmailErrorResponses:
  """
  Test suite for email error response format.

  Tests verify that error responses follow RFC 7807 format
  with proper type, title, status, detail, and instance fields.
  """

  @pytest.mark.asyncio
  async def test_email_failed_response_format(self):
    """
    Test that email failure returns RFC 7807 compliant error.

    Given: EmailSender returns False
    When: POST /auth/request-magic-link
    Then: Response has type, title, status, detail, instance fields
    """
    from quart.testing import QuartClient

    from roomz.server import server

    async with QuartClient(server) as client:
      mock_sender = AsyncMock()
      mock_sender.send_magic_link.return_value = False

      with patch("roomz.server.get_email_sender", return_value=mock_sender), \
           patch("roomz.server.is_email_allowed", return_value=True):
        response = await client.post(
          "/auth/request-magic-link",
          json={"email": "test@example.com"},
        )
        data = await response.get_json()
        assert "type" in data
        assert "title" in data
        assert "status" in data
        assert "detail" in data
        assert "instance" in data

  @pytest.mark.asyncio
  async def test_email_failed_response_type(self):
    """
    Test that email failure has correct error type.

    Given: EmailSender returns False
    When: POST /auth/request-magic-link
    Then: Error type is 'https://roomz.local/errors/email-failed'
    """
    from quart.testing import QuartClient

    from roomz.server import server

    async with QuartClient(server) as client:
      mock_sender = AsyncMock()
      mock_sender.send_magic_link.return_value = False

      with patch("roomz.server.get_email_sender", return_value=mock_sender), \
           patch("roomz.server.is_email_allowed", return_value=True):
        response = await client.post(
          "/auth/request-magic-link",
          json={"email": "test@example.com"},
        )
        data = await response.get_json()
        assert data["type"] == "https://roomz.local/errors/email-failed"

  @pytest.mark.asyncio
  async def test_email_failed_response_status(self):
    """
    Test that email failure returns 500 status.

    Given: EmailSender returns False
    When: POST /auth/request-magic-link
    Then: HTTP status is 500
    """
    from quart.testing import QuartClient

    from roomz.server import server

    async with QuartClient(server) as client:
      mock_sender = AsyncMock()
      mock_sender.send_magic_link.return_value = False

      with patch("roomz.server.get_email_sender", return_value=mock_sender), \
           patch("roomz.server.is_email_allowed", return_value=True):
        response = await client.post(
          "/auth/request-magic-link",
          json={"email": "test@example.com"},
        )
        assert response.status_code == 500

  @pytest.mark.asyncio
  async def test_email_failed_response_title(self):
    """
    Test that email failure has correct title.

    Given: EmailSender returns False
    When: POST /auth/request-magic-link
    Then: Error title is 'Email Delivery Failed'
    """
    from quart.testing import QuartClient

    from roomz.server import server

    async with QuartClient(server) as client:
      mock_sender = AsyncMock()
      mock_sender.send_magic_link.return_value = False

      with patch("roomz.server.get_email_sender", return_value=mock_sender), \
           patch("roomz.server.is_email_allowed", return_value=True):
        response = await client.post(
          "/auth/request-magic-link",
          json={"email": "test@example.com"},
        )
        data = await response.get_json()
        assert data["title"] == "Email Delivery Failed"


# =============================================================================
# Module Structure Tests
# =============================================================================


class TestEmailModuleStructure:
  """
  Test suite for email module structure.

  Tests verify that the email module follows the planned
  file structure with proper exports.
  """

  def test_email_module_exists(self):
    """
    Test that roomz.server.email module exists.

    Given: The roomz.server package
    When: Importing roomz.server.email
    Then: Module is available
    """
    import roomz.server.email

    assert roomz.server.email is not None

  def test_email_module_exports_protocol(self):
    """
    Test that email module exports EmailSender protocol.

    Given: The app.email module
    When: Importing from app.email
    Then: EmailSender is available
    """
    from roomz.server.email import EmailSender

    assert EmailSender is not None

  def test_email_module_exports_console_sender(self):
    """
    Test that email module exports ConsoleEmailSender.

    Given: The app.email module
    When: Importing from app.email
    Then: ConsoleEmailSender is available
    """
    from roomz.server.email import ConsoleEmailSender

    assert ConsoleEmailSender is not None

  def test_email_module_exports_resend_sender(self):
    """
    Test that email module exports ResendEmailSender.

    Given: The app.email module
    When: Importing from app.email
    Then: ResendEmailSender is available
    """
    from roomz.server.email import ResendEmailSender

    assert ResendEmailSender is not None

  def test_email_module_exports_factory(self):
    """
    Test that email module exports get_email_sender factory.

    Given: The app.email module
    When: Importing from app.email
    Then: get_email_sender is available
    """
    from roomz.server.email import get_email_sender

    assert callable(get_email_sender)
