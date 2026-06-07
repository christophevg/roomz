"""Roomz CLI - Run and manage roomz applications.

This module provides the command-line interface for roomz applications.

Commands:
    init      Create default roomz.toml configuration file
    check     Validate configuration without running
    config    Display current configuration
    serve     Run roomz application with Gunicorn
    cli       Run the TUI chat client
    version   Display roomz version

Usage:
    roomz init                    Create default roomz.toml
    roomz init --force            Overwrite existing file
    roomz check                   Validate configuration
    roomz check --app-uri app:app Override app-uri for validation
    roomz config                  Show current configuration
    roomz config --format toml    Show configuration as TOML
    roomz serve                   Run app from roomz.toml
    roomz serve --reload           Run with auto-reload (development)
    roomz serve --server-workers 4 Override server config
    roomz cli                     Run the TUI chat client
    roomz cli --server-url URL    Override server URL
    roomz version                 Show version
"""

import importlib
import sys
from dataclasses import asdict
from pathlib import Path

import tomli_w
from clevis import configclass, get_cmd, get_config
from gunicorn.app.wsgiapp import WSGIApplication  # type: ignore[import-untyped]

from roomz import __version__
from roomz.config import ClientConfig, RoomzConfig

# Command Configuration Classes


@configclass(cmd="serve", help="Run roomz application")  # type: ignore[arg-type]
class ServeConfig(RoomzConfig):
  """Serve inherits all RoomzConfig fields for CLI overrides.

  Users can override ANY config field via CLI:
      --app-uri, --name, --server-bind, --server-workers, etc.

  The config parameter already has: defaults < user TOML < project TOML < CLI args
  Clevis handles all merging automatically.
  """

  pass


@configclass(cmd="check", help="Validate configuration")  # type: ignore[arg-type]
class CheckConfig(ServeConfig):
  """Check inherits all ServeConfig=RoomzConfig fields.

  Validates the EXACT config that would be used by serve.
  Users can override fields to test specific configurations.
  """

  pass


@configclass(cmd="init", help="Create default configuration file")  # type: ignore[arg-type]
class InitConfig:
  """Configuration for init command.

  Attributes:
      config: Path to configuration file
      force: Overwrite existing file if True
  """

  config: str = "roomz.toml"
  force: bool = False


@configclass(cmd="config", help="Display current configuration")  # type: ignore[arg-type]
class ConfigConfig(RoomzConfig):
  """Configuration for config command.

  Attributes:
      format: Output format ('table' or 'toml')
  """

  format: str = "table"  # or "toml"


@configclass(cmd="cli", help="Run TUI chat client")  # type: ignore[arg-type]
class CliConfig(ClientConfig):
  """Configuration for cli command.

  Inherits ClientConfig fields for CLI overrides.
  CLI args will be: --server-url, --display-name
  """

  pass


@configclass(cmd="version", help="Display roomz version")  # type: ignore[arg-type]
class VersionConfig:
  """Configuration for version command.

  This command has no additional configuration options.
  """

  pass


# Helper Functions


def import_app(app_uri: str):
  """Import ASGI application from module:variable URI.

  Args:
      app_uri: Module path and variable name (e.g., "app:asgi_app")

  Returns:
      ASGI application object

  Raises:
      ImportError: If module cannot be imported
      AttributeError: If variable not found in module
      TypeError: If app initialization fails (e.g., wrong argument types)
  """
  # Add current directory to path for finding local modules
  sys.path.insert(0, str(Path.cwd()))

  try:
    # Split module path and app name
    if ":" not in app_uri:
      raise ImportError(
        f"Invalid app_uri format: '{app_uri}'. Expected 'module:variable' (e.g., 'app:asgi_app')"
      )

    module_path, app_name = app_uri.rsplit(":", 1)

    # Import module
    module = importlib.import_module(module_path)

    # Get app variable
    if not hasattr(module, app_name):
      raise AttributeError(
        f"Module '{module_path}' has no attribute '{app_name}'. Available attributes: {dir(module)}"
      )

    return getattr(module, app_name)

  except ImportError as e:
    # Provide helpful error message
    if "No module named" in str(e):
      raise ImportError(
        f"Cannot find module '{module_path}'. "
        f"Make sure you're in the correct directory and the module exists.\n"
        f"Current directory: {Path.cwd()}\n"
        f"Python path: {sys.path[:3]}..."
      ) from None
    raise
  except TypeError as e:
    # Provide helpful error message for type errors (e.g., wrong arguments)
    if "'str' object has no attribute" in str(e) or "unexpected keyword argument" in str(e):
      raise TypeError(
        f"Application initialization failed: {e}\n"
        f"This usually means the app is using an old Baseweb API.\n"
        f"Make sure the app is compatible with the current baseweb version.\n"
        f"App URI: {app_uri}"
      ) from None
    raise
  except Exception as e:
    # Catch all other exceptions and provide context
    raise RuntimeError(
      f"Failed to import application '{app_uri}': {e}\n"
      f"Make sure the module exists and the app variable is correctly defined.\n"
      f"Current directory: {Path.cwd()}"
    ) from None


def config_to_toml(config: RoomzConfig, omit=None) -> str:
  """Convert RoomzConfig to TOML format using introspection.

  Uses dataclasses.asdict() to avoid hardcoding field names.
  This automatically adapts when RoomzConfig structure changes.

  Args:
      config: RoomzConfig instance

  Returns:
      TOML-formatted string
  """
  # Convert to dict
  data = asdict(config)
  if omit:
    for key in omit:
      data.pop(key, None)

  # Filter out None values (TOML doesn't support null)
  def filter_none(obj):
    """Recursively filter out None values from nested dicts."""
    if isinstance(obj, dict):
      return {k: filter_none(v) for k, v in obj.items() if v is not None}
    return obj

  filtered_data = filter_none(data)

  # Use tomli_w to write TOML
  return tomli_w.dumps(filtered_data)


def print_config_table(config: RoomzConfig, omit=None):
  """Print configuration as formatted table using introspection.

  Uses dataclasses.asdict() to avoid hardcoding field names.

  Args:
      config: RoomzConfig instance
  """
  data = asdict(config)
  if omit:
    for key in omit:
      data.pop(key, None)

  print("Roomz Configuration")
  print("=" * 60)
  print()

  # Print top-level scalar fields
  print("Application:")
  for key, value in data.items():
    if key.startswith("_"):
      continue
    if isinstance(value, dict):
      continue
    if value is not None:
      print(f"  {key.replace('_', ' ').title()}: {value}")
  print()

  # Print nested sections
  for key, value in data.items():
    if key.startswith("_"):
      continue
    if isinstance(value, dict):
      print(f"{key.title()}:")
      for subkey, subvalue in value.items():
        print(f"  {subkey.replace('_', ' ').title()}: {subvalue}")
      print()


# Command Implementation Functions


def serve(config: ServeConfig):
  """Run roomz application with Gunicorn.

  Args:
      config: ServeConfig instance with merged configuration
              (defaults < user TOML < project TOML < CLI args)
  """
  StandaloneApplication(config.app_uri, asdict(config.server)).run()


def init(config: InitConfig):
  """Create default configuration file.

  Args:
      config: InitConfig instance with command configuration
  """
  config_path = Path(config.config)

  if config_path.exists() and not config.force:
    print(f"Configuration file already exists: {config_path}")
    print("Use --force to overwrite")
    sys.exit(1)

  # Create from defaults
  default_config = RoomzConfig()

  # Write TOML using introspection
  try:
    config_path.write_text(config_to_toml(default_config))
    # Set secure permissions (owner read/write only)
    config_path.chmod(0o600)
    print(f"Created {config_path} (permissions: 600)")
    print("Edit this file to customize your roomz application")
  except OSError as e:
    print(f"Failed to create configuration file: {e}", file=sys.stderr)
    sys.exit(1)


def check(config: CheckConfig):
  """Validate configuration without running.

  Checks:
      - Configuration can be loaded
      - Required fields are present
      - Application can be imported

  Args:
      config: CheckConfig instance with merged configuration
              (defaults < user TOML < project TOML < CLI args)
  """
  errors = []

  # Validate required fields
  if not config.app_uri:
    errors.append("app_uri is required")

  # Check app_uri can be imported
  try:
    sys.path.insert(0, str(Path.cwd()))
    import_app(config.app_uri)
  except Exception as e:
    errors.append(f"Cannot import app_uri '{config.app_uri}': {e}")

  if errors:
    for error in errors:
      print(f"ERROR: {error}", file=sys.stderr)
    sys.exit(1)

  print(
    f"""Configuration is valid
  App: {config.name}
  Title: {config.title}
  Entry: {config.app_uri}
  Bind: {config.server.bind}
  Workers: {config.server.workers}""",
    file=sys.stdout,
  )
  sys.exit(0)


def show_config(config: ConfigConfig):
  """Display current configuration.

  Args:
      config: ConfigConfig instance with output format
  """
  if config.format == "toml":
    print(config_to_toml(config, omit=["format"]))
  else:
    print_config_table(config, omit=["format"])


def version():
  """Display roomz version."""
  print(__version__)


def cli(config: CliConfig):
  """Run the TUI chat client.

  Args:
      config: CliConfig instance with merged configuration
              (defaults < user TOML < project TOML < CLI args)
  """
  from roomz.cli.app_tui import run_tui

  run_tui(config=config)


# Gunicorn Application Wrapper


class StandaloneApplication(WSGIApplication):
  """Custom Gunicorn application for running ASGI apps.

  Imports the application AFTER Gunicorn starts, ensuring
  that gunicorn.error logger is available for Baseweb logging.

  Based on: https://stackoverflow.com/a/73895674
  """

  def __init__(self, app_uri: str, options: dict | None = None):
    """Initialize standalone application.

    Args:
        app_uri: Application URI in format 'module:variable' (e.g., 'app:asgi_app')
        options: Gunicorn configuration options
    """
    self.options = options or {}
    self.app_uri = app_uri
    super().__init__()

  def load_config(self):
    """Load Gunicorn configuration from options."""
    config = {
      key: value
      for key, value in self.options.items()
      if key in self.cfg.settings and value is not None
    }
    for key, value in config.items():
      self.cfg.set(key.lower(), value)

  def load(self):
    """Import and return the ASGI application.

    This is called AFTER Gunicorn starts, ensuring the gunicorn.error
    logger is available for Baseweb's logging setup.
    """
    return import_app(self.app_uri)


# Main Entry Points


def run():
  """Main CLI entry point using Clevis command dispatch."""
  cmd = get_cmd()

  match cmd:
    case "serve":
      serve(get_config(ServeConfig, name="roomz"))
    case "check":
      check(get_config(CheckConfig, name="roomz"))
    case "init":
      init(get_config(InitConfig, name="roomz"))
    case "config":
      show_config(get_config(ConfigConfig, name="roomz"))
    case "cli":
      cli(get_config(CliConfig, name="roomz"))
    case "version":
      version()
    case _:
      print("Commands: init, check, config, serve, cli, version")
      sys.exit(1)


if __name__ == "__main__":
  run()
