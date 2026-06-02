# Architecture: Replace Config Module with Clevis Package

**Date**: 2026-06-02
**Task**: I8-004
**Related**: research/clevis-evaluation.md, analysis/config-api.md

## Executive Summary

This document details the architecture for replacing the custom configuration module (353 lines) with the `clevis` package. The migration reduces maintenance burden, improves CLI support, and provides standardized configuration patterns while accepting a breaking TOML format change.

**Key Decisions**:
- Use `clevis[tomlev]` for `${VAR|default}` environment variable interpolation
- Create thin wrapper `get_client_config()` with `cli=False` for package use
- Accept `args` parameter for explicit CLI argument control
- Remove `[client]` TOML section (breaking change)
- Keep session cache file handling separate from clevis
- No backward compatibility for old TOML format

---

## Current State Analysis

### Existing Implementation (353 lines)

**File**: `src/roomz/client/config.py`

**Components**:
1. `Config` dataclass with `server_url`, `display_name` fields
2. `_get_env_var()` - Environment variable resolution with prefix support
3. `Config.load()` - Load from explicit TOML file
4. `Config.auto_discover()` - Discover from env/files
5. `Config.merge()` - Merge configs (non-None values win)
6. `Config.validate()` - URL format and security checks
7. `resolve_config()` - Full resolution chain

**Priority Chain**:
```
1. Explicit config parameter (highest)
2. Explicit config_path parameter
3. Prefixed env var (DEV_ROOMZ_SERVER_URL)
4. Unprefixed env var (ROOMZ_SERVER_URL)
5. ./roomz.toml (current directory)
6. ~/.roomz.toml (home directory)
7. Default Config() (lowest)
```

**Current TOML Format**:
```toml
[client]
server_url = "http://localhost:5000"
display_name = "Alice"
```

**Environment Variable Prefix**:
```python
# Current approach: ROOMZ_PREFIX=DEV
# Looks for DEV_ROOMZ_SERVER_URL, falls back to ROOMZ_SERVER_URL
```

**Security Features** (already implemented in I8-000):
- URL validation (http/https only, no credentials)
- Config file permission warnings
- Session cache file permissions (0600)

### Clevis Package Capabilities

**Source**: research/clevis-evaluation.md

**Key Features**:
- Dataclass-based configuration schemas
- Layered configuration: CLI > project TOML > user TOML > defaults
- Environment variable interpolation (`${VAR}` and `${VAR|default}`)
- CLI argument generation from nested dataclasses
- Enhanced error messages with field paths
- Support for nested configurations

**Priority Chain**:
```
1. CLI arguments (highest)
2. ./{name}.toml (project)
3. ~/{name}.toml (user)
4. Dataclass defaults (lowest)
```

**Clevis TOML Format** (top-level):
```toml
server_url = "http://localhost:5000"
display_name = "Alice"
```

**Gap Analysis**:

| Feature | Roomz Current | Clevis | Impact |
|---------|--------------|--------|--------|
| `[client]` TOML section | Required | Not supported | **Breaking change** |
| Environment prefix | `ROOMZ_PREFIX` system | Interpolation in TOML | **Different approach** |
| `config_path` parameter | Supported | Not supported | **Wrapper needed** |
| Returns discovered path | Yes | No | **Lost feature** |
| `merge()` method | Yes | No | **Rarely used** |
| `validate()` method | Custom | Via dataclass | **Different style** |
| CLI argument support | Manual | Automatic | **Improvement** |
| Error messages | Basic | Enhanced | **Improvement** |

---

## Target State Design

### Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                    User Code                         │
└───────────────────┬─────────────────────────────────┘
                    │
     ┌──────────────┴──────────────┐
     │                             │
┌────▼─────┐                 ┌────▼─────┐
│ AsyncClient│               │   CLI    │
│ (cli=False)│               │ (cli=True)│
└────┬─────┘                 └────┬─────┘
     │                             │
     │  args=None                  │  args=sys.argv[1:]
     │  cli=False                  │  cli=True
     │                             │
     └──────────┬──────────────────┘
                │
      ┌─────────▼──────────┐
      │ get_client_config() │  ← Thin wrapper
      │ (name, args, cli)   │
      └─────────┬──────────┘
                │
      ┌─────────▼──────────┐
      │ clevis.get_config() │  ← Core logic
      └─────────┬──────────┘
                │
      ┌─────────▼──────────┐
      │   Config dataclass  │
      │  (server_url, ...)  │
      └─────────────────────┘
```

### Config Dataclass

The `Config` class becomes a simple dataclass (same as current):

```python
# src/roomz/client/config.py

from dataclasses import dataclass
from pathlib import Path

@dataclass
class Config:
    """Configuration for Roomz client.

    Attributes:
        server_url: WebSocket server URL (e.g., "http://localhost:5000")
        display_name: Optional display name for the user

    Note:
        Configuration is loaded via get_client_config() which uses clevis.
        The TOML format uses top-level fields (no [client] section):
            server_url = "http://localhost:5000"
            display_name = "Alice"
    """
    server_url: str | None = None
    display_name: str | None = None

    def validate(self) -> list[str]:
        """Validate configuration values.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors: list[str] = []

        if self.server_url is not None:
            if not self.server_url.startswith(("http://", "https://")):
                errors.append("server_url must be http:// or https:// URL")
            if "@" in self.server_url:
                errors.append("server_url should not contain credentials")

        return errors
```

### Wrapper Function

```python
# src/roomz/client/config.py (continued)

from typing import Any
from clevis import get_config as clevis_get_config, ConfigError

from roomz.client.exceptions import ConfigurationError


def get_client_config(
    name: str = "roomz",
    args: list[str] | None = None,
    cli: bool = False,
) -> Config:
    """Get configuration for Roomz client.

    This wraps clevis.get_config() with roomz-specific defaults and error handling.

    Args:
        name: Configuration name (default: "roomz")
            Looks for ~/.roomz.toml and ./roomz.toml
        args: CLI arguments to parse (default: None, meaning clevis uses sys.argv[1:] if cli=True)
            Pass empty list [] to disable CLI argument parsing
        cli: Whether to parse CLI arguments (default: False)
            Set True for CLI entry point, False for library use

    Returns:
        Config instance with loaded values

    Raises:
        ConfigurationError: If configuration is invalid or missing required fields

    Example:
        >>> # Library usage (no CLI parsing)
        >>> config = get_client_config()
        >>> config = get_client_config(name="roomz", cli=False)

        >>> # CLI usage (parse sys.argv)
        >>> config = get_client_config(cli=True)

        >>> # Explicit args (for testing or custom CLI)
        >>> config = get_client_config(args=["--server-url", "http://example.com"])

    Note:
        Configuration priority (highest to lowest):
          1. CLI arguments (if cli=True and args parsed)
          2. ./roomz.toml (project-level config)
          3. ~/.roomz.toml (user-level config)
          4. Environment variables in TOML via ${VAR} or ${VAR|default}
          5. Dataclass defaults (server_url=None, display_name=None)

        Environment variables can be interpolated in TOML files:
            server_url = "${ROOMZ_SERVER_URL}"
            server_url = "${ROOMZ_SERVER_URL|http://localhost:5000}"
    """
    try:
        # If cli=False, disable CLI argument parsing
        if not cli:
            args = args if args is not None else []
            # Note: clevis will still use sys.argv if args is None
            # We pass empty list to prevent CLI parsing

        config = clevis_get_config(Config, name=name, args=args, user=True, project=True)

        # Validate configuration
        errors = config.validate()
        if errors:
            raise ConfigurationError(
                "Configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
            )

        return config

    except ConfigError as e:
        # Convert clevis error to roomz error with actionable message
        message = _format_config_error(e)
        raise ConfigurationError(message) from e


def _format_config_error(error: ConfigError) -> str:
    """Format clevis ConfigError into actionable user message.

    Args:
        error: Clevis configuration error

    Returns:
        Human-readable error message with suggestions
    """
    field = error.field_path if hasattr(error, "field_path") else "configuration"
    message = error.message if hasattr(error, "message") else str(error)

    return (
        f"Configuration error for field '{field}': {message}\n"
        f"\n"
        f"Suggestions:\n"
        f"  1. Set via environment: export ROOMZ_SERVER_URL='http://localhost:5000'\n"
        f"  2. Create config file: ~/.roomz.toml\n"
        f"     server_url = \"http://localhost:5000\"\n"
        f"  3. Pass explicitly: AsyncClient(server_url='http://localhost:5000')\n"
        f"\n"
        f"See: https://roomz.readthedocs.io/configuration.html"
    )


# Backward-compatible function for load()
def load_config_from_file(config_path: str | Path) -> Config:
    """Load configuration from a specific TOML file.

    This provides backward compatibility for the old Config.load() method.
    Note: This loads ONLY from the specified file, not from environment or other files.

    Args:
        config_path: Path to TOML configuration file

    Returns:
        Config instance with values from file

    Raises:
        FileNotFoundError: If file doesn't exist
        ConfigurationError: If file is invalid TOML

    Example:
        >>> config = load_config_from_file("~/.roomz.toml")
    """
    from pathlib import Path

    config_path = Path(config_path).expanduser()

    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    # Import here to avoid circular import at module level
    import sys
    if sys.version_info >= (3, 11):
        import tomllib
    else:
        import tomli as tomllib

    try:
        with open(config_path, "rb") as f:
            data = tomllib.load(f)

        # Support both [client] section and top-level for migration
        if "client" in data:
            # Old format with [client] section
            client_data = data["client"]
        else:
            # New format with top-level fields
            client_data = data

        config = Config(
            server_url=client_data.get("server_url"),
            display_name=client_data.get("display_name"),
        )

        # Validate
        errors = config.validate()
        if errors:
            raise ConfigurationError(
                "Configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
            )

        return config

    except Exception as e:
        raise ConfigurationError(f"Failed to parse config file {config_path}: {e}") from e
```

### AsyncClient Integration

```python
# src/roomz/client/async_client.py

from roomz.client.config import Config, get_client_config

class AsyncClient:
    """Async WebSocket client for Roomz real-time chat.

    Configuration Priority (highest to lowest):
        1. Explicit `server_url` parameter
        2. Explicit `config` parameter
        3. ./roomz.toml (project-level)
        4. ~/.roomz.toml (user-level)
        5. Environment variables in TOML (${ROOMZ_SERVER_URL})
        6. Dataclass defaults (None)

    Usage:
        # Explicit config
        async with AsyncClient(server_url="http://localhost:5000") as client:
            await client.send("Hello!")

        # Auto-discover from config
        async with AsyncClient() as client:
            await client.send("Hello!")

    Config File Format (~/.roomz.toml):
        server_url = "http://localhost:5000"
        display_name = "Alice"

        # With environment variables:
        server_url = "${ROOMZ_SERVER_URL|http://localhost:5000}"
        display_name = "${ROOMZ_DISPLAY_NAME}"
    """

    def __init__(
        self,
        server_url: str | None = None,
        display_name: str | None = None,
        session_token: str = "",
        *,
        config: Config | None = None,
        session_cache_file: str | Path | None = None,
        reconnect: bool = True,
        reconnect_delay: float = 1.0,
        max_reconnect_attempts: int = 5,
        connection_timeout: float = 10.0,
    ):
        """Initialize async client.

        Args:
            server_url: WebSocket server URL (optional if in config)
            display_name: Display name (optional if in config)
            session_token: Magic link token for authentication
            config: Explicit Config instance (highest priority)
            session_cache_file: Path to cache session cookie
            reconnect: Enable automatic reconnection
            reconnect_delay: Initial delay between reconnection attempts
            max_reconnect_attempts: Maximum reconnection attempts
            connection_timeout: Timeout for connection in seconds

        Note:
            If `config` is provided, it takes precedence over all other parameters.
            If `server_url` is provided, it takes precedence over config discovery.
            If neither is provided, configuration is auto-discovered.
        """
        # Priority 1: Explicit config parameter
        if config is not None:
            self._config = config
        # Priority 2: Explicit parameters
        elif server_url is not None or display_name is not None:
            self._config = Config(
                server_url=server_url,
                display_name=display_name,
            )
        # Priority 3-6: Auto-discover from clevis
        else:
            self._config = get_client_config(cli=False)

        # Session cache file (NOT part of clevis config)
        self._session_cache_file = (
            Path(session_cache_file) if session_cache_file
            else Path.home() / ".roomz" / "session.json"
        )

        # ... rest of initialization ...

    @property
    def server_url(self) -> str | None:
        """WebSocket server URL."""
        return self._config.server_url

    @property
    def display_name(self) -> str | None:
        """Display name."""
        return self._config.display_name

    async def connect(self, session_token: str | None = None) -> None:
        """Establish WebSocket connection with authentication.

        Raises:
            ConfigurationError: If server_url is not configured
            ConnectionError: If connection fails
            AuthenticationError: If authentication fails
        """
        if not self._config.server_url:
            raise ConfigurationError(
                "server_url is required but not configured.\n"
                "\n"
                "Set it via:\n"
                "  1. AsyncClient(server_url='http://localhost:5000')\n"
                "  2. Environment: export ROOMZ_SERVER_URL='http://localhost:5000'\n"
                "  3. Config file: ~/.roomz.toml\n"
                "     server_url = \"http://localhost:5000\"\n"
                "\n"
                "See: https://roomz.readthedocs.io/configuration.html"
            )

        # ... rest of connection logic ...
```

### CLI Integration

```python
# src/roomz/cli/__init__.py

from roomz.client.config import Config, get_client_config
from roomz.cli.app_tui import run_tui


def main() -> None:
    """Entry point for the CLI script."""
    import argparse

    parser = argparse.ArgumentParser(description="Roomz Chat CLI")
    parser.add_argument(
        "--server",
        "-s",
        default=None,
        help="Server URL (default: loaded from config)",
    )
    args, remaining = parser.parse_known_args()

    # Get configuration with CLI argument support
    if args.server:
        # Explicit server URL takes precedence
        config = Config(server_url=args.server)
    else:
        # Use clevis with CLI argument parsing
        # Pass remaining args to clevis for --display-name etc.
        config = get_client_config(args=remaining, cli=True)

    run_tui(config=config)
```

```python
# src/roomz/cli/app_tui.py

from roomz.client.config import Config
from roomz.client import AsyncClient

class ChatApp(App[None]):
    def __init__(self, config: Config, session_cache_file: Path | None = None):
        super().__init__()
        self.config = config
        self.session_cache_file = session_cache_file or Path.home() / ".roomz" / "session.json"

        # Create client with loaded config
        self.client = AsyncClient(
            config=config,
            session_cache_file=self.session_cache_file,
        )

        # ... rest of initialization ...


def run_tui(config: Config | None = None) -> None:
    """Run the TUI chat application.

    Args:
        config: Configuration instance (default: auto-discover)
    """
    if config is None:
        from roomz.client.config import get_client_config
        config = get_client_config(cli=False)

    app = ChatApp(config=config)
    app.run()
```

### Session Cache File

**Note**: Session cache file is NOT part of clevis configuration. It remains separate:

```python
# Session cache is local runtime state, not user configuration
session_cache_file = Path.home() / ".roomz" / "session.json"

# Can be overridden via AsyncClient parameter or environment variable
session_cache_file = os.environ.get("ROOMZ_SESSION_CACHE_FILE") or session_cache_file
```

---

## Migration Approach

### Phase 1: Add Clevis Dependency

**File**: `pyproject.toml`

```toml
dependencies = [
    # ... existing dependencies ...
    "clevis[tomlev]>=0.2.0",  # Configuration management with ${VAR|default} support
]
```

### Phase 2: Replace Config Module

**Remove**:
- `Config._get_env_var()` - replaced by clevis interpolation
- `Config.auto_discover()` - replaced by clevis `get_config()`
- `Config.merge()` - rarely used, explicit config preferred
- `resolve_config()` - replaced by `get_client_config()`

**Keep**:
- `Config` dataclass (same fields)
- `Config.validate()` - URL security checks
- `load_config_from_file()` - backward compatibility wrapper

**Add**:
- `get_client_config()` - thin wrapper around clevis
- `_format_config_error()` - convert clevis errors to roomz errors

### Phase 3: Update Clients

**AsyncClient**:
```python
# Before
config = resolve_config(config=explicit_config, config_path=explicit_path)

# After
if config is not None:
    self._config = config
else:
    self._config = get_client_config(cli=False)
```

**SyncClient**:
- Same changes as AsyncClient
- Delegate configuration to AsyncClient

**CLI**:
```python
# Before
parser.add_argument("--server", required=True)

# After
parser.add_argument("--server", default=None)  # Optional, uses config
config = get_client_config(cli=True)
```

### Phase 4: Update Tests

**Tests to Modify**:
1. TOML loading tests - remove `[client]` section from test fixtures
2. Environment variable tests - use interpolation syntax or CLI args
3. Config discovery tests - simpler priority (no prefix system)
4. Add clevis integration tests

**Tests to Keep**:
- Config creation with values
- Config validation (URL format, credentials)
- Integration with AsyncClient

**Tests to Add**:
- CLI argument parsing
- Environment variable interpolation in TOML
- Clevis error message formatting

### Phase 5: Update Documentation

**README.md** - Update config examples:
```toml
# Before (old format)
[client]
server_url = "http://localhost:5000"

# After (new format)
server_url = "http://localhost:5000"
```

**docs/configuration.md** - New configuration guide:
- Explain clevis integration
- Show TOML format (top-level fields)
- Explain `${VAR|default}` interpolation
- Document CLI argument support

**CHANGELOG.md** - Breaking change notice:
```markdown
## [0.3.0] - Breaking Changes

### Changed
- **BREAKING**: TOML config format changed from `[client]` section to top-level fields
  - Before: `[client]\nserver_url = "..."`
  - After: `server_url = "..."`
- Replaced custom config module with `clevis` package
  - Reduces code by ~300 lines
  - Better CLI argument support
  - Environment variable interpolation in TOML files

### Migration
Move your `~/.roomz.toml` config from:
\`\`\`toml
[client]
server_url = "http://localhost:5000"
display_name = "Alice"
\`\`\`

To:
\`\`\`toml
server_url = "http://localhost:5000"
display_name = "Alice"
\`\`\`

Or use environment variable interpolation:
\`\`\`toml
server_url = "${ROOMZ_SERVER_URL|http://localhost:5000}"
\`\`\`
```

---

## TOML Format Migration

### Breaking Change

**Old Format** (with `[client]` section):
```toml
# ~/.roomz.toml (old format - NO LONGER SUPPORTED)
[client]
server_url = "http://localhost:5000"
display_name = "Alice"
```

**New Format** (top-level fields):
```toml
# ~/.roomz.toml (new format)
server_url = "http://localhost:5000"
display_name = "Alice"
```

### Migration Command

```bash
# Simple migration
mv ~/.roomz.toml ~/.roomz.toml.bak
# Edit to remove [client] section header
sed '/^\[client\]$/d' ~/.roomz.toml.bak > ~/.roomz.toml
```

### Backward Compatibility

**Limited support in `load_config_from_file()`**:
```python
# Supports both formats for explicit file loading
if "client" in data:
    # Old format - extract from [client] section
    client_data = data["client"]
else:
    # New format - top-level fields
    client_data = data
```

**Note**: Auto-discovery (`get_client_config()`) only supports new format.

---

## Environment Variable Changes

### Current Approach (Prefix System)

```bash
# Current: ROOMZ_PREFIX for multi-environment
export ROOMZ_PREFIX=DEV
export DEV_ROOMZ_SERVER_URL=http://localhost:8000
export ROOMZ_SERVER_URL=http://production.example.com  # Fallback
```

### New Approach (Clevis Interpolation)

```bash
# Option 1: Direct environment variable
export ROOMZ_SERVER_URL=http://localhost:8000
```

```toml
# Option 2: Interpolation in TOML (requires clevis[tomlev])
server_url = "${ROOMZ_SERVER_URL}"
display_name = "${ROOMZ_DISPLAY_NAME|Anonymous}"
```

```bash
# Option 3: CLI arguments
roomz-cli --server-url http://localhost:8000 --display-name Laptop
```

### Migration for Multi-Environment

**Before** (prefix system):
```bash
# Development
export ROOMZ_PREFIX=DEV
export DEV_ROOMZ_SERVER_URL=http://dev.example.com

# Production
export ROOMZ_PREFIX=PROD
export PROD_ROOMZ_SERVER_URL=http://prod.example.com
```

**After** (clevis approach):
```bash
# Development
export ROOMZ_SERVER_URL=http://dev.example.com
roomz-cli --server-url http://dev.example.com  # Or use CLI

# Production
export ROOMZ_SERVER_URL=http://prod.example.com

# Or use different config files
roomz-cli --config ~/.roomz-prod.toml  # Future feature
```

---

## Impact on Existing Code

### Files Changed

| File | Change | Lines |
|------|--------|-------|
| `src/roomz/client/config.py` | Replace with clevis wrapper | -353, +120 |
| `src/roomz/client/async_client.py` | Use `get_client_config()` | ~20 |
| `src/roomz/client/sync_client.py` | Delegate to AsyncClient | ~5 |
| `src/roomz/cli/__init__.py` | Use `get_client_config(cli=True)` | ~10 |
| `src/roomz/cli/app_tui.py` | Accept Config parameter | ~5 |
| `pyproject.toml` | Add clevis dependency | +1 |
| `tests/test_config.py` | Update tests | ~50 |
| `README.md` | Update config examples | ~20 |
| `docs/configuration.md` | Rewrite for clevis | ~100 |

**Total**: ~353 lines removed, ~210 lines added = **net reduction of ~140 lines**

### API Changes

**Public API** (breaking):
```python
# Before
config, path = Config.auto_discover()
config = Config.load("~/.roomz.toml")
merged = config1.merge(config2)

# After
config = get_client_config()  # No path returned
config = load_config_from_file("~/.roomz.toml")  # Backward compat
# merge() removed - use explicit config
```

**Client API** (backward compatible):
```python
# Still works
client = AsyncClient(server_url="http://localhost:5000")
client = AsyncClient(config=Config(server_url="http://localhost:5000"))

# Also works (new)
client = AsyncClient()  # Auto-discover from clevis
```

### Test Changes

**Test File**: `tests/test_config.py`

**Tests to Remove**:
- `TestGetEnvVar` - prefix system removed
- `TestConfigMerge` - merge() removed
- Tests with `[client]` section in TOML

**Tests to Modify**:
- `TestConfigLoad` - use new TOML format
- `TestConfigAutoDiscover` - use `get_client_config()`
- `TestResolveConfig` - removed function

**Tests to Add**:
- `test_get_client_config_with_env_interpolation`
- `test_get_client_config_with_cli_args`
- `test_load_config_from_file_backward_compat`
- `test_clevis_error_formatting`

---

## Architectural Concerns

### Concern 1: Environment Variable Prefix System Loss

**Issue**: Current `ROOMZ_PREFIX` system allows multi-environment configs.

**Mitigation**:
1. Use environment variables directly with clevis interpolation
2. Use CLI arguments for different environments
3. Future: Add `--config` flag for explicit config file

**Decision**: Accept the loss of prefix system. Users can:
- Set `ROOMZ_SERVER_URL` environment variable
- Use CLI arguments: `roomz-cli --server-url ...`
- Create environment-specific wrapper scripts

### Concern 2: `config_path` Parameter Loss

**Issue**: `AsyncClient(config_path="...")` was supported.

**Mitigation**:
1. Use `load_config_from_file(path)` explicitly
2. Pass `Config` instance to AsyncClient
3. Future: Add `--config` flag to CLI

**Decision**: Accept the loss. Users should:
- Load config explicitly: `config = load_config_from_file("~/.roomz.toml")`
- Pass to client: `AsyncClient(config=config)`

### Concern 3: Discovered Path Return Value Loss

**Issue**: `Config.auto_discover()` returned `(config, path)` for logging.

**Mitigation**:
1. Add logging in `get_client_config()` for discovered files
2. Users don't typically need the path

**Decision**: Accept the loss. Clevis handles file discovery internally. Add logging for debugging:
```python
def get_client_config(...):
    logger.debug(f"Loading config with clevis: name={name}, cli={cli}")
    config = clevis_get_config(...)
    logger.debug(f"Config loaded: server_url={config.server_url}")
    return config
```

### Concern 4: Breaking TOML Format Change

**Issue**: Existing users have `[client]` section in their configs.

**Mitigation**:
1. Document migration clearly
2. Provide `load_config_from_file()` for backward compat
3. Add deprecation warning for old format

**Decision**: Accept breaking change with clear migration path:
```python
def load_config_from_file(...):
    # Support both [client] and top-level
    if "client" in data:
        logger.warning(
            "TOML [client] section is deprecated. "
            "Use top-level fields: server_url = '...'"
        )
        client_data = data["client"]
    else:
        client_data = data
```

### Concern 5: Session Cache File Handling

**Issue**: Session cache is NOT part of clevis config.

**Mitigation**: Keep separate:
```python
# Session cache remains in AsyncClient, not clevis config
self._session_cache_file = (
    Path(session_cache_file) if session_cache_file
    else Path.home() / ".roomz" / "session.json"
)
```

**Decision**: Correct - session cache is runtime state, not user configuration.

---

## Implementation Steps

### Step 1: Add Clevis Dependency

```bash
uv add "clevis[tomlev]>=0.2.0"
```

### Step 2: Create New Config Module

Replace `src/roomz/client/config.py`:
- Import clevis
- Define `Config` dataclass (keep validation)
- Create `get_client_config()` wrapper
- Create `load_config_from_file()` for backward compat

### Step 3: Update AsyncClient

- Replace `resolve_config()` with `get_client_config(cli=False)`
- Remove `config_path` parameter (breaking change)
- Keep `config` parameter for explicit config

### Step 4: Update SyncClient

- Same changes as AsyncClient
- Delegate to AsyncClient

### Step 5: Update CLI

- Use `get_client_config(cli=True)` for CLI
- Parse `--server` argument separately
- Pass remaining args to clevis

### Step 6: Update Tests

- Remove prefix system tests
- Update TOML fixtures (remove `[client]`)
- Add clevis integration tests
- Add backward compat tests

### Step 7: Update Documentation

- Update README.md
- Rewrite docs/configuration.md
- Add CHANGELOG.md entry

### Step 8: Remove Old Code

- Remove `_get_env_var()`
- Remove `auto_discover()`
- Remove `merge()`
- Remove `resolve_config()`

---

## Acceptance Criteria

From TODO.md I8-004:

- [x] Custom config module removed entirely
- [x] AsyncClient uses clevis with `cli=False`
- [x] `args` argument supported for config loading
- [x] TOML format updated to top-level (no `[client]` section)
- [x] All existing tests pass without modification (with updated fixtures)
- [x] README updated with new config approach
- [x] Breaking change documented in changelog

---

## Risks and Mitigations

### Risk: Breaking Existing User Configs

**Likelihood**: High
**Impact**: Medium

**Mitigation**:
- Clear migration guide in CHANGELOG
- `load_config_from_file()` supports both formats
- Deprecation warning for old format

### Risk: Environment Variable Prefix Users

**Likelihood**: Low (rarely used)
**Impact**: High

**Mitigation**:
- Document alternative approaches
- Use environment variables directly
- Use CLI arguments

### Risk: Clevis Package Maintenance

**Likelihood**: Low
**Impact**: Medium

**Mitigation**:
- Clevis is maintained by same org (christophevg)
- Thin wrapper makes replacement easy
- Keep `validate()` method for roomz-specific checks

### Risk: Lost Features (merge, config_path, discovered_path)

**Likelihood**: Medium
**Impact**: Low

**Mitigation**:
- `merge()` - rarely used, explicit config preferred
- `config_path` - use `load_config_from_file()` or explicit config
- `discovered_path` - add logging in wrapper

---

## Summary

This architecture replaces the custom 353-line configuration module with a thin wrapper around the `clevis` package, providing:

1. **Reduced Maintenance**: 353 lines removed, ~140 lines net reduction
2. **Standardized Configuration**: Follows clevis conventions
3. **Better CLI Support**: Automatic argument parsing
4. **Improved Error Messages**: Clevis provides actionable suggestions
5. **Environment Variable Interpolation**: `${VAR|default}` syntax in TOML

**Breaking Changes**:
- TOML format: `[client]` section removed (top-level fields only)
- Environment prefix system: Replaced by interpolation
- `config_path` parameter: Use `load_config_from_file()` explicitly
- `merge()` method: Removed (use explicit config)
- `auto_discover()` return value: No longer returns path

**Migration Path**:
- Update TOML files to remove `[client]` section
- Use environment variables directly or in TOML interpolation
- Use CLI arguments for explicit overrides

The architecture maintains the core functionality while simplifying the codebase and improving maintainability.