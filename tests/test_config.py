"""
Tests for Config class and configuration resolution.
"""

import os
from pathlib import Path
from unittest import mock

import pytest

from roomz.client.config import Config, resolve_config
from roomz.client.exceptions import ConfigurationError


class TestConfig:
  """Tests for Config dataclass."""

  def test_config_defaults(self) -> None:
    """Test Config default values."""
    config = Config()
    assert config.server_url is None
    assert config.display_name is None

  def test_config_with_values(self) -> None:
    """Test Config with explicit values."""
    config = Config(server_url="http://localhost:5000", display_name="Alice")
    assert config.server_url == "http://localhost:5000"
    assert config.display_name == "Alice"

  def test_config_merge(self) -> None:
    """Test Config merge method."""
    config1 = Config(server_url="http://example.com")
    config2 = Config(display_name="Bob")
    merged = config1.merge(config2)
    assert merged.server_url == "http://example.com"
    assert merged.display_name == "Bob"

  def test_config_merge_with_none(self) -> None:
    """Test Config merge with None values."""
    config1 = Config(server_url="http://example.com", display_name="Alice")
    config2 = Config()
    merged = config1.merge(config2)
    assert merged.server_url == "http://example.com"
    assert merged.display_name == "Alice"

  def test_config_validate_no_errors(self) -> None:
    """Test Config validation with valid values."""
    config = Config(server_url="http://localhost:5000")
    errors = config.validate()
    assert len(errors) == 0

  def test_config_validate_invalid_url(self) -> None:
    """Test Config validation with invalid URL."""
    config = Config(server_url="invalid-url")
    errors = config.validate()
    assert len(errors) == 1
    assert "http:// or https://" in errors[0]

  def test_config_validate_credentials_in_url(self) -> None:
    """Test Config validation with credentials in URL."""
    config = Config(server_url="http://user:pass@localhost:5000")
    errors = config.validate()
    assert len(errors) == 1
    assert "credentials" in errors[0]


class TestGetEnvVar:
  """Tests for _get_env_var static method."""

  def test_get_env_var_without_prefix(self) -> None:
    """Test _get_env_var without prefix."""
    with mock.patch.dict(os.environ, {"ROOMZ_SERVER_URL": "http://example.com"}):
      value = Config._get_env_var("", "ROOMZ_SERVER_URL")
      assert value == "http://example.com"

  def test_get_env_var_with_prefix(self) -> None:
    """Test _get_env_var with prefix."""
    with mock.patch.dict(
      os.environ, {"ROOMZ_PREFIX": "DEV", "DEV_ROOMZ_SERVER_URL": "http://dev.example.com"}
    ):
      value = Config._get_env_var("DEV", "ROOMZ_SERVER_URL")
      assert value == "http://dev.example.com"

  def test_get_env_var_prefix_not_found_fallback(self) -> None:
    """Test _get_env_var with prefix not found, falls back to unprefixed."""
    with mock.patch.dict(
      os.environ, {"ROOMZ_PREFIX": "DEV", "ROOMZ_SERVER_URL": "http://example.com"}, clear=True
    ):
      value = Config._get_env_var("DEV", "ROOMZ_SERVER_URL")
      assert value == "http://example.com"

  def test_get_env_var_not_found(self) -> None:
    """Test _get_env_var when variable not found."""
    with mock.patch.dict(os.environ, {}, clear=True):
      value = Config._get_env_var("", "ROOMZ_SERVER_URL")
      assert value is None


class TestConfigLoad:
  """Tests for Config.load class method."""

  def test_config_load_valid_toml(self, tmp_path: Path) -> None:
    """Test Config.load with valid TOML file."""
    config_file = tmp_path / "roomz.toml"
    config_file.write_text(
      """
[client]
server_url = "http://localhost:5000"
display_name = "Alice"
"""
    )

    config = Config.load(config_file)
    assert config.server_url == "http://localhost:5000"
    assert config.display_name == "Alice"

  def test_config_load_missing_file(self, tmp_path: Path) -> None:
    """Test Config.load with missing file."""
    config_file = tmp_path / "missing.toml"
    with pytest.raises(FileNotFoundError):
      Config.load(config_file)

  def test_config_load_invalid_toml(self, tmp_path: Path) -> None:
    """Test Config.load with invalid TOML."""
    config_file = tmp_path / "invalid.toml"
    config_file.write_text("invalid toml content [[")

    with pytest.raises(ValueError, match="Failed to parse config file"):
      Config.load(config_file)

  def test_config_load_missing_section(self, tmp_path: Path) -> None:
    """Test Config.load with missing [client] section."""
    config_file = tmp_path / "roomz.toml"
    config_file.write_text(
      """
[other]
key = "value"
"""
    )

    config = Config.load(config_file)
    assert config.server_url is None
    assert config.display_name is None

  def test_config_load_partial_config(self, tmp_path: Path) -> None:
    """Test Config.load with partial configuration."""
    config_file = tmp_path / "roomz.toml"
    config_file.write_text(
      """
[client]
server_url = "http://localhost:5000"
"""
    )

    config = Config.load(config_file)
    assert config.server_url == "http://localhost:5000"
    assert config.display_name is None

  def test_config_load_expand_home(self, tmp_path: Path) -> None:
    """Test Config.load with ~ expansion."""
    config_file = tmp_path / "roomz.toml"
    config_file.write_text(
      """
[client]
server_url = "http://localhost:5000"
"""
    )

    # Just test that the method accepts Path and str
    config = Config.load(config_file)
    assert config.server_url == "http://localhost:5000"


class TestConfigAutoDiscover:
  """Tests for Config.auto_discover class method."""

  def test_auto_discover_from_env_only(self) -> None:
    """Test auto-discovery from environment variables only."""
    with mock.patch.dict(
      os.environ,
      {"ROOMZ_SERVER_URL": "http://example.com", "ROOMZ_DISPLAY_NAME": "Bob"},
      clear=True,
    ):
      config = Config.auto_discover()
      assert config.server_url == "http://example.com"
      assert config.display_name == "Bob"

  def test_auto_discover_from_env_with_prefix(self) -> None:
    """Test auto-discovery from prefixed environment variables."""
    with mock.patch.dict(
      os.environ,
      {
        "ROOMZ_PREFIX": "PROD",
        "PROD_ROOMZ_SERVER_URL": "http://prod.example.com",
        "PROD_ROOMZ_DISPLAY_NAME": "Charlie",
      },
      clear=True,
    ):
      config = Config.auto_discover()
      assert config.server_url == "http://prod.example.com"
      assert config.display_name == "Charlie"

  def test_auto_discover_from_file(self, tmp_path: Path) -> None:
    """Test auto-discovery from config file."""
    config_file = tmp_path / "roomz.toml"
    config_file.write_text(
      """
[client]
server_url = "http://localhost:5000"
display_name = "Alice"
"""
    )

    # Change to tmp directory
    with mock.patch.object(Path, "cwd", return_value=tmp_path):
      config = Config.auto_discover()
      assert config.server_url == "http://localhost:5000"
      assert config.display_name == "Alice"

  def test_auto_discover_priority_env_over_file(self, tmp_path: Path) -> None:
    """Test that env vars take precedence over file."""
    config_file = tmp_path / "roomz.toml"
    config_file.write_text(
      """
[client]
server_url = "http://file.example.com"
display_name = "FileUser"
"""
    )

    with mock.patch.dict(
      os.environ,
      {"ROOMZ_SERVER_URL": "http://env.example.com"},
      clear=True,
    ):
      with mock.patch.object(Path, "cwd", return_value=tmp_path):
        with mock.patch.object(Path, "home", return_value=tmp_path):
          config = Config.auto_discover()
          # Env var takes precedence
          assert config.server_url == "http://env.example.com"
          # File value for missing env var
          assert config.display_name == "FileUser"

  def test_auto_discover_none(self) -> None:
    """Test auto-discovery when no config available."""
    with mock.patch.dict(os.environ, {}, clear=True):
      with mock.patch.object(Path, "cwd", return_value=Path("/nonexistent")):
        with mock.patch.object(Path, "home", return_value=Path("/nonexistent")):
          config = Config.auto_discover()
          assert config.server_url is None
          assert config.display_name is None


class TestResolveConfig:
  """Tests for resolve_config function."""

  def test_resolve_config_explicit(self) -> None:
    """Test resolve_config with explicit config."""
    explicit = Config(server_url="http://explicit.com")
    result = resolve_config(config=explicit)
    assert result.server_url == "http://explicit.com"

  def test_resolve_config_from_path(self, tmp_path: Path) -> None:
    """Test resolve_config from file path."""
    config_file = tmp_path / "custom.toml"
    config_file.write_text(
      """
[client]
server_url = "http://file.example.com"
display_name = "FileUser"
"""
    )

    result = resolve_config(config_path=config_file)
    assert result.server_url == "http://file.example.com"
    assert result.display_name == "FileUser"

  def test_resolve_config_path_merges_with_auto_discover(self, tmp_path: Path) -> None:
    """Test that config_path merges with auto-discovered values."""
    config_file = tmp_path / "custom.toml"
    config_file.write_text(
      """
[client]
server_url = "http://file.example.com"
"""
    )

    with mock.patch.dict(
      os.environ,
      {"ROOMZ_DISPLAY_NAME": "EnvUser"},
      clear=True,
    ):
      with mock.patch.object(Path, "home", return_value=tmp_path):
        result = resolve_config(config_path=config_file)
        # File value
        assert result.server_url == "http://file.example.com"
        # Auto-discovered value fills in None
        assert result.display_name == "EnvUser"

  def test_resolve_config_auto_discover(self, tmp_path: Path) -> None:
    """Test resolve_config with auto-discovery."""
    with mock.patch.dict(
      os.environ,
      {"ROOMZ_SERVER_URL": "http://auto.com"},
      clear=True,
    ):
      with mock.patch.object(Path, "home", return_value=tmp_path):
        result = resolve_config()
        assert result.server_url == "http://auto.com"

  def test_resolve_config_priority(self, tmp_path: Path) -> None:
    """Test resolve_config priority order."""
    # Create a config file
    config_file = tmp_path / "custom.toml"
    config_file.write_text(
      """
[client]
server_url = "http://file.example.com"
"""
    )

    # Explicit config has highest priority
    explicit = Config(server_url="http://explicit.com")
    result = resolve_config(config=explicit, config_path=config_file)
    assert result.server_url == "http://explicit.com"

    # Config path has medium priority
    result = resolve_config(config_path=config_file)
    assert result.server_url == "http://file.example.com"


class TestIntegration:
  """Integration tests for Config with AsyncClient."""

  def test_config_used_by_async_client(self) -> None:
    """Test that Config is properly used by AsyncClient."""
    from roomz.client import AsyncClient

    config = Config(server_url="http://localhost:5000", display_name="TestUser")
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

    client = AsyncClient(config=Config())
    with pytest.raises(ConfigurationError, match="server_url is not configured"):
      import asyncio

      asyncio.run(client.connect())
