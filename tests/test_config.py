"""
Tests for Config class using clevis package.
"""

import os
import platform
from pathlib import Path
from unittest import mock

import pytest
from clevis import SecurityAction, get_config

from roomz.client.config import ClientConfig, RoomzConfig
from roomz.client.exceptions import ConfigurationError

# Windows detection
IS_WINDOWS = platform.system() == "Windows" or os.name == "nt"


class TestClientConfig:
  """Tests for ClientConfig dataclass."""

  def test_client_config_defaults(self) -> None:
    """Test ClientConfig default values."""
    config = ClientConfig()
    assert config.server_url is None
    assert config.display_name is None

  def test_client_config_with_values(self) -> None:
    """Test ClientConfig with explicit values."""
    config = ClientConfig(server_url="http://localhost:5000", display_name="Alice")
    assert config.server_url == "http://localhost:5000"
    assert config.display_name == "Alice"

  def test_client_config_validate_valid_url(self) -> None:
    """Test ClientConfig validation with valid URL."""
    # Validation happens in __post_init__, should not raise
    config = ClientConfig(server_url="http://localhost:5000")
    assert config.server_url == "http://localhost:5000"

  def test_client_config_validate_https_url(self) -> None:
    """Test ClientConfig validation with HTTPS URL."""
    config = ClientConfig(server_url="https://example.com")
    assert config.server_url == "https://example.com"

  def test_client_config_validate_invalid_url(self) -> None:
    """Test ClientConfig validation with invalid URL."""
    with pytest.raises(ValueError, match="must be http:// or https://"):
      ClientConfig(server_url="invalid-url")

  def test_client_config_validate_credentials_in_url(self) -> None:
    """Test ClientConfig validation with credentials in URL."""
    with pytest.raises(ValueError, match="should not contain credentials"):
      ClientConfig(server_url="http://user:pass@localhost:5000")


class TestRoomzConfig:
  """Tests for RoomzConfig dataclass."""

  def test_roomz_config_defaults(self) -> None:
    """Test RoomzConfig default values."""
    config = RoomzConfig()
    assert config.client is not None
    assert config.client.server_url is None
    assert config.client.display_name is None

  def test_roomz_config_with_client_config(self) -> None:
    """Test RoomzConfig with explicit ClientConfig."""
    client_config = ClientConfig(server_url="http://localhost:5000", display_name="Alice")
    config = RoomzConfig(client=client_config)
    assert config.client.server_url == "http://localhost:5000"
    assert config.client.display_name == "Alice"

  def test_roomz_config_nested_initialization(self) -> None:
    """Test RoomzConfig with nested initialization."""
    config = RoomzConfig(client=ClientConfig(server_url="http://localhost:8000"))
    assert config.client.server_url == "http://localhost:8000"


class TestClevisConfig:
  """Tests for clevis get_config function with RoomzConfig."""

  @pytest.mark.skipif(IS_WINDOWS, reason="Unix file permissions not supported on Windows")
  def test_get_config_from_file(self, tmp_path: Path) -> None:
    """Test get_config from TOML file with [client] section."""
    config_file = tmp_path / "roomz.toml"
    config_file.write_text(
      """
[client]
server_url = "http://localhost:5000"
display_name = "Alice"
"""
    )
    # Make file secure (0600 permissions)
    config_file.chmod(0o600)

    # Change to tmp directory
    with mock.patch.object(Path, "cwd", return_value=tmp_path):
      config = get_config(
        RoomzConfig,
        name="roomz",
        user=False,
        project=True,
        cli=False,
        security={
          "file_permissions": SecurityAction.REJECT,
          "directory_permissions": SecurityAction.REJECT,
        },
      )
      assert config.client.server_url == "http://localhost:5000"
      assert config.client.display_name == "Alice"

  @pytest.mark.skipif(IS_WINDOWS, reason="Unix file permissions not supported on Windows")
  def test_get_config_with_env_interpolation(self, tmp_path: Path) -> None:
    """Test get_config with environment variable interpolation in TOML."""
    config_file = tmp_path / "roomz.toml"
    config_file.write_text(
      """
[client]
server_url = "${ROOMZ_SERVER_URL}"
display_name = "${ROOMZ_DISPLAY_NAME}"
"""
    )
    config_file.chmod(0o600)

    with mock.patch.dict(
      os.environ,
      {"ROOMZ_SERVER_URL": "http://env.example.com", "ROOMZ_DISPLAY_NAME": "EnvUser"},
      clear=True,
    ):
      with mock.patch.object(Path, "cwd", return_value=tmp_path):
        config = get_config(
          RoomzConfig,
          name="roomz",
          user=False,
          project=True,
          cli=False,
          security={
            "file_permissions": SecurityAction.REJECT,
            "directory_permissions": SecurityAction.REJECT,
          },
        )
        assert config.client.server_url == "http://env.example.com"
        assert config.client.display_name == "EnvUser"

  def test_get_config_none(self) -> None:
    """Test get_config when no config available."""
    with mock.patch.dict(os.environ, {}, clear=True):
      with mock.patch.object(Path, "cwd", return_value=Path("/nonexistent")):
        with mock.patch.object(Path, "home", return_value=Path("/nonexistent")):
          config = get_config(
            RoomzConfig,
            name="roomz",
            user=False,
            project=False,
            cli=False,
          )
          assert config.client.server_url is None
          assert config.client.display_name is None


class TestSecurity:
  """Tests for security validation."""

  def test_rejects_insecure_file_permissions(self, tmp_path: Path) -> None:
    """Test that clevis rejects config with group/other read."""
    config_file = tmp_path / "roomz.toml"
    config_file.write_text(
      """
[client]
server_url = "http://test.com"
"""
    )

    # Make insecure (group/other readable)
    config_file.chmod(0o644)

    with mock.patch.object(Path, "cwd", return_value=tmp_path):
      with pytest.raises(Exception, match="readable by group/other"):  # clevis raises SecurityError
        get_config(
          RoomzConfig,
          name="roomz",
          user=False,
          project=True,
          cli=False,
          security={
            "file_permissions": SecurityAction.REJECT,
            "directory_permissions": SecurityAction.REJECT,
          },
        )

  @pytest.mark.skipif(IS_WINDOWS, reason="Unix file permissions not supported on Windows")
  def test_accepts_secure_config(self, tmp_path: Path) -> None:
    """Test that clevis accepts config with 0600 permissions."""
    config_file = tmp_path / "roomz.toml"
    config_file.write_text(
      """
[client]
server_url = "http://test.com"
"""
    )
    config_file.chmod(0o600)

    with mock.patch.object(Path, "cwd", return_value=tmp_path):
      config = get_config(
        RoomzConfig,
        name="roomz",
        user=False,
        project=True,
        cli=False,
        security={
          "file_permissions": SecurityAction.REJECT,
          "directory_permissions": SecurityAction.REJECT,
        },
      )
      assert config.client.server_url == "http://test.com"


class TestIntegration:
  """Integration tests for RoomzConfig with AsyncClient."""

  def test_config_used_by_async_client(self) -> None:
    """Test that RoomzConfig is properly used by AsyncClient."""
    from roomz.client import AsyncClient

    config = RoomzConfig(client=ClientConfig(server_url="http://localhost:5000", display_name="TestUser"))
    client = AsyncClient(config=config)

    assert client.server_url == "http://localhost:5000"
    assert client.display_name == "TestUser"

  def test_config_none_raises_on_connect(self) -> None:
    """Test that connecting without server_url raises ConfigurationError."""
    from roomz.client import AsyncClient

    client = AsyncClient(config=RoomzConfig())
    with pytest.raises(ConfigurationError, match="server_url is not configured"):
      import asyncio

      asyncio.run(client.connect())

  def test_config_backward_compat_alias(self) -> None:
    """Test that Config is an alias for RoomzConfig."""
    from roomz.client import Config, RoomzConfig

    # Config should be an alias
    assert Config is RoomzConfig

    # Both should work
    client_config1 = ClientConfig(server_url="http://example.com")
    config1 = Config(client=client_config1)
    client_config2 = ClientConfig(server_url="http://example.com")
    config2 = RoomzConfig(client=client_config2)
    assert type(config1) is type(config2)

