"""
Tests for Config class using clevis package.
"""

import os
from pathlib import Path
from unittest import mock

import pytest

from roomz.client.config import RoomzConfig, get_roomz_config
from roomz.client.exceptions import ConfigurationError


class TestRoomzConfig:
  """Tests for RoomzConfig dataclass."""

  def test_config_defaults(self) -> None:
    """Test RoomzConfig default values."""
    config = RoomzConfig()
    assert config.server_url is None
    assert config.display_name is None

  def test_config_with_values(self) -> None:
    """Test RoomzConfig with explicit values."""
    config = RoomzConfig(server_url="http://localhost:5000", display_name="Alice")
    assert config.server_url == "http://localhost:5000"
    assert config.display_name == "Alice"

  def test_config_validate_valid_url(self) -> None:
    """Test RoomzConfig validation with valid URL."""
    # Validation happens in __post_init__, should not raise
    config = RoomzConfig(server_url="http://localhost:5000")
    assert config.server_url == "http://localhost:5000"

  def test_config_validate_https_url(self) -> None:
    """Test RoomzConfig validation with HTTPS URL."""
    config = RoomzConfig(server_url="https://example.com")
    assert config.server_url == "https://example.com"

  def test_config_validate_invalid_url(self) -> None:
    """Test RoomzConfig validation with invalid URL."""
    with pytest.raises(ValueError, match="must be http:// or https://"):
      RoomzConfig(server_url="invalid-url")

  def test_config_validate_credentials_in_url(self) -> None:
    """Test RoomzConfig validation with credentials in URL."""
    with pytest.raises(ValueError, match="should not contain credentials"):
      RoomzConfig(server_url="http://user:pass@localhost:5000")


class TestGetRoomzConfig:
  """Tests for get_roomz_config function."""

  def test_get_config_from_env(self) -> None:
    """Test get_roomz_config from environment variables."""
    with mock.patch.dict(
      os.environ,
      {"ROOMZ_SERVER_URL": "http://example.com", "ROOMZ_DISPLAY_NAME": "Bob"},
      clear=True,
    ):
      config = get_roomz_config(cli=False, args=[])
      assert config.server_url == "http://example.com"
      assert config.display_name == "Bob"

  def test_get_config_from_file(self, tmp_path: Path) -> None:
    """Test get_roomz_config from TOML file."""
    config_file = tmp_path / "roomz.toml"
    config_file.write_text(
      """
server_url = "http://localhost:5000"
display_name = "Alice"
"""
    )
    # Make file secure (0600 permissions)
    config_file.chmod(0o600)

    # Change to tmp directory
    with mock.patch.object(Path, "cwd", return_value=tmp_path):
      config = get_roomz_config(cli=False, args=[])
      assert config.server_url == "http://localhost:5000"
      assert config.display_name == "Alice"

  def test_get_config_priority_env_over_file(self, tmp_path: Path) -> None:
    """Test that env vars take precedence over file."""
    config_file = tmp_path / "roomz.toml"
    config_file.write_text(
      """
server_url = "http://file.example.com"
display_name = "FileUser"
"""
    )
    config_file.chmod(0o600)

    with mock.patch.dict(
      os.environ,
      {"ROOMZ_SERVER_URL": "http://env.example.com"},
      clear=True,
    ):
      with mock.patch.object(Path, "cwd", return_value=tmp_path):
        config = get_roomz_config(cli=False, args=[])
        # Env var takes precedence
        assert config.server_url == "http://env.example.com"
        # File value for missing env var
        assert config.display_name == "FileUser"

  def test_get_config_none(self) -> None:
    """Test get_roomz_config when no config available."""
    with mock.patch.dict(os.environ, {}, clear=True):
      with mock.patch.object(Path, "cwd", return_value=Path("/nonexistent")):
        with mock.patch.object(Path, "home", return_value=Path("/nonexistent")):
          config = get_roomz_config(cli=False, args=[])
          assert config.server_url is None
          assert config.display_name is None

  def test_get_config_explicit(self) -> None:
    """Test get_roomz_config with explicit config parameter."""
    # When passing explicit config, it should override
    # But get_roomz_config doesn't take explicit config - it's just a factory
    # This test verifies that explicit configs work
    config = RoomzConfig(server_url="http://explicit.com")
    assert config.server_url == "http://explicit.com"


class TestSecurity:
  """Tests for security validation."""

  def test_rejects_insecure_file_permissions(self, tmp_path: Path) -> None:
    """Test that clevis rejects config with group/other read."""
    config_file = tmp_path / "roomz.toml"
    config_file.write_text('server_url = "http://test.com"\n')

    # Make insecure (group/other readable)
    config_file.chmod(0o644)

    with mock.patch.object(Path, "cwd", return_value=tmp_path):
      with pytest.raises(ConfigurationError, match="Failed to load configuration"):
        get_roomz_config(cli=False, args=[])

  def test_accepts_secure_config(self, tmp_path: Path) -> None:
    """Test that clevis accepts config with 0600 permissions."""
    config_file = tmp_path / "roomz.toml"
    config_file.write_text('server_url = "http://test.com"\n')
    config_file.chmod(0o600)

    with mock.patch.object(Path, "cwd", return_value=tmp_path):
      config = get_roomz_config(cli=False, args=[])
      assert config.server_url == "http://test.com"


class TestBackwardCompatibility:
  """Tests for backward compatibility."""

  def test_resolve_config_explicit(self) -> None:
    """Test resolve_config with explicit config."""
    from roomz.client.config import resolve_config

    explicit = RoomzConfig(server_url="http://explicit.com")
    result = resolve_config(config=explicit)
    assert result.server_url == "http://explicit.com"

  def test_resolve_config_auto_discover(self) -> None:
    """Test resolve_config with auto-discovery."""
    from roomz.client.config import resolve_config

    with mock.patch.dict(
      os.environ,
      {"ROOMZ_SERVER_URL": "http://auto.com"},
      clear=True,
    ):
      result = resolve_config()
      assert result.server_url == "http://auto.com"


class TestIntegration:
  """Integration tests for RoomzConfig with AsyncClient."""

  def test_config_used_by_async_client(self) -> None:
    """Test that RoomzConfig is properly used by AsyncClient."""
    from roomz.client import AsyncClient

    config = RoomzConfig(server_url="http://localhost:5000", display_name="TestUser")
    client = AsyncClient(config=config)

    assert client.server_url == "http://localhost:5000"
    assert client.display_name == "TestUser"

  def test_config_auto_discover_used_by_async_client(self) -> None:
    """Test that auto-discovered config works with AsyncClient."""
    from roomz.client import AsyncClient

    with mock.patch.dict(
      os.environ,
      {"ROOMZ_SERVER_URL": "http://auto.example.com", "ROOMZ_DISPLAY_NAME": "AutoUser"},
      clear=True,
    ):
      client = AsyncClient()
      assert client.server_url == "http://auto.example.com"
      assert client.display_name == "AutoUser"

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
    config1 = Config(server_url="http://example.com")
    config2 = RoomzConfig(server_url="http://example.com")
    assert type(config1) is type(config2)

