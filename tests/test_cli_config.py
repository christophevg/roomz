"""
Tests for CLI configuration parsing with clevis.

This tests the specific issue where nested dataclasses with
'from __future__ import annotations' fail to parse CLI arguments.
"""

import os
import platform
from pathlib import Path
from unittest import mock

import pytest
from clevis import get_config

from roomz.config import RoomzConfig

# Windows detection
IS_WINDOWS = platform.system() == "Windows" or os.name == "nt"


class TestCLIConfig:
  """Tests for CLI argument parsing with nested dataclass config."""

  def test_get_config_with_cli_true_no_args(self) -> None:
    """Test get_config with cli=True and no arguments works.

    This tests the bug where clevis fails to handle nested dataclasses
    when 'from __future__ import annotations' is used.
    """
    with mock.patch.dict("os.environ", {}, clear=True):
      with mock.patch.object(Path, "cwd", return_value=Path("/nonexistent")):
        with mock.patch.object(Path, "home", return_value=Path("/nonexistent")):
          # This should not raise ValueError: 'ClientConfig' is not callable
          config = get_config(
            RoomzConfig,
            name="roomz",
            user=False,
            project=False,
            cli=True,
            args=[],  # No CLI args
          )
          assert config.client.server_url is None
          assert config.client.display_name is None

  def test_get_config_with_cli_args(self) -> None:
    """Test get_config with CLI arguments for nested fields.

    CLI args should use dashed notation for nested fields.
    """
    with mock.patch.dict("os.environ", {}, clear=True):
      with mock.patch.object(Path, "cwd", return_value=Path("/nonexistent")):
        with mock.patch.object(Path, "home", return_value=Path("/nonexistent")):
          config = get_config(
            RoomzConfig,
            name="roomz",
            user=False,
            project=False,
            cli=True,
            args=["--client-server-url", "http://localhost:8000", "--client-display-name", "Alice"],
          )
          assert config.client.server_url == "http://localhost:8000"
          assert config.client.display_name == "Alice"

  @pytest.mark.skipif(IS_WINDOWS, reason="Unix file permissions not supported on Windows")
  def test_get_config_cli_overrides_file(self, tmp_path: Path) -> None:
    """Test that CLI args override file config for nested fields."""
    config_file = tmp_path / "roomz.toml"
    config_file.write_text(
      """
[client]
server_url = "http://file.example.com"
display_name = "FileUser"
"""
    )
    config_file.chmod(0o600)

    with mock.patch.object(Path, "cwd", return_value=tmp_path):
      config = get_config(
        RoomzConfig,
        name="roomz",
        user=False,
        project=True,
        cli=True,
        args=["--client-server-url", "http://cli.example.com"],
      )
      # CLI overrides file
      assert config.client.server_url == "http://cli.example.com"
      # File value preserved
      assert config.client.display_name == "FileUser"
