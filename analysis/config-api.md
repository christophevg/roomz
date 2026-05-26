# Configuration API Design

**Date**: 2026-05-26
**Task**: Design a generalized configuration system for the roomz Python client
**Issue**: I8-000 (Issue #1)

## Executive Summary

This document proposes a unified configuration system for the roomz Python client library, replacing the current ad-hoc configuration patterns with a consistent, hierarchical configuration loading mechanism. The design enables zero-configuration startup while maintaining full flexibility for programmatic use.

**Key Decisions**:
- Migrate from `~/.roomz/config.toml` (folder) to `~/.roomz.toml` (single file)
- Make `server_url` optional with auto-discovery
- Unified priority: explicit parameter → environment variable → local config → home config
- Full backward compatibility with migration support

---

## Current State Analysis

### Current Configuration Patterns

#### Pattern 1: Explicit `server_url` Parameter (Required)

```python
# Currently required - no config fallback
client = AsyncClient(server_url="http://localhost:8000")
```

**Issue**: Every client instantiation requires explicit server URL, even for development environments.

#### Pattern 2: `display_name` from Environment/Config (Implemented)

```python
def _load_display_name_from_config() -> str | None:
    """
    Load display name from environment variable or config file.

    Priority:
        1. ROOMZ_DISPLAY_NAME environment variable
        2. ~/.roomz/config.toml file
    """
    # Check environment variable first
    env_name = os.environ.get("ROOMZ_DISPLAY_NAME")
    if env_name:
        return env_name.strip() or None

    # Check config file
    config_file = Path.home() / ".roomz" / "config.toml"
    # ... TOML parsing ...
```

**Strengths**:
- Clear priority order
- Simple TOML format
- Works well for single config value

**Weaknesses**:
- Inconsistent with `server_url` (required vs. optional)
- Folder-based config (`~/.roomz/config.toml`) vs. single file
- Not generalized for future config items

#### Pattern 3: `session_cache_file` as Explicit Parameter

```python
# Hardcoded in CLI app
self.client = AsyncClient(
    server_url=self.server_url,
    session_cache_file=Path.home() / ".roomz" / "session.json",
)
```

**Issue**: Session cache location is hardcoded in app, not configurable.

### Current Config File Location

```
~/.roomz/
  config.toml      # Display name config
  session.json     # Session cookie cache (created at runtime)
```

**Issues**:
- Creates a folder for just two files
- Session cache is automatically created, config is manually created
- No single source of truth for all configuration

---

## Design Questions

### Question 1: Single File vs. Folder

**Recommendation**: Migrate to single file `~/.roomz.toml`

**Rationale**:

| Aspect | Folder (`~/.roomz/`) | Single File (`~/.roomz.toml`) |
|--------|---------------------|-------------------------------|
| **Discoverability** | Requires looking inside folder | Immediate visibility |
| **XDG compliance** | Would need `~/.config/roomz/` | Non-standard |
| **Complexity** | Directory creation, multiple files | One file, simple |
| **User experience** | "Where's my config?" | "Here's my config" |
| **Git integration** | Folder-level `.gitkeep` | File-level tracking |
| **Session cache** | Separation of concerns | Same location, different files |

**Decision**: Single file `~/.roomz.toml` for configuration, `~/.roomz/session.json` for session cache (runtime data, not user config).

**Alternative**: XDG Base Directory specification (`~/.config/roomz/config.toml`) - more complex, not requested.

### Question 2: Supported Configuration Items

**Recommendation**: Support all client configuration items

```toml
# ~/.roomz.toml

[client]
# WebSocket server URL (required if not in env or parameter)
server_url = "http://localhost:8000"

# Display name for this device/session
display_name = "Laptop"

# Session cache file location (default: ~/.roomz/session.json)
# session_cache_file = "/custom/path/session.json"
```

**Priority Order** (for each config item):

1. **Explicit parameter** (highest priority)
   ```python
   client = AsyncClient(server_url="http://localhost:8000")
   ```

2. **Environment variable**
   ```bash
   export ROOMZ_SERVER_URL="http://localhost:8000"
   ```

3. **Local config file** (`./roomz.toml`)
   - For project-specific settings
   - Checked into VCS for team consistency

4. **Home config file** (`~/.roomz.toml`)
   - For user-specific settings
   - Default location for personal configuration

**Rationale**: This priority follows the "specificity wins" principle, where explicit parameters override everything, and project-local config overrides user-global config.

### Question 3: Backward Compatibility

**Recommendation**: Support both old and new locations with deprecation warning

**Migration Path**:

1. **Phase 1** (Current release): Support both locations
   - Check `~/.roomz/config.toml` if `~/.roomz.toml` doesn't exist
   - Log deprecation warning if using old location
   - No breaking changes

2. **Phase 2** (Next major version): Remove old location support
   - Document migration: `mv ~/.roomz/config.toml ~/.roomz.toml`

**Implementation**:

```python
def _load_config_file() -> dict[str, Any]:
    """Load configuration from file with backward compatibility."""
    config = {}

    # Check local config first
    local_config = Path("./roomz.toml")
    if local_config.exists():
        config.update(_parse_toml(local_config))

    # Check home config (new location)
    home_config = Path.home() / ".roomz.toml"
    if home_config.exists():
        config.update(_parse_toml(home_config))
        return config

    # Fall back to old location (deprecated)
    old_config = Path.home() / ".roomz" / "config.toml"
    if old_config.exists():
        logger.warning(
            "Using deprecated config location ~/.roomz/config.toml. "
            "Please migrate to ~/.roomz.toml"
        )
        config.update(_parse_toml(old_config))

    return config
```

---

## Proposed API Design

### AsyncClient Constructor

**Before** (Current):

```python
AsyncClient(
    server_url: str,                    # REQUIRED
    session_token: str = "",
    *,
    reconnect: bool = True,
    reconnect_delay: float = 1.0,
    max_reconnect_attempts: int = 5,
    connection_timeout: float = 10.0,
    session_cache_file: str | Path | None = None,
    display_name: str | None = None,
)
```

**After** (Proposed):

```python
AsyncClient(
    server_url: str | None = None,      # NOW OPTIONAL
    session_token: str = "",
    *,
    reconnect: bool = True,
    reconnect_delay: float = 1.0,
    max_reconnect_attempts: int = 5,
    connection_timeout: float = 10.0,
    session_cache_file: str | Path | None = None,
    display_name: str | None = None,
)
```

**Key Changes**:
1. `server_url` is now `str | None = None`
2. If not provided, loaded from config/env
3. If still not found, raises `ConfigurationError` on `connect()`

### Configuration Error Handling

```python
class ConfigurationError(ClientError):
    """Raised when required configuration is missing."""

    def __init__(self, message: str, config_key: str):
        super().__init__(message)
        self.config_key = config_key
```

**Error Message**:

```python
# On connect() without server_url
raise ConfigurationError(
    "server_url is required but not configured. "
    "Set it via:\n"
    "  1. AsyncClient(server_url='...')\n"
    "  2. ROOMZ_SERVER_URL environment variable\n"
    "  3. ./roomz.toml or ~/.roomz.toml\n"
    "See: https://roomz.readthedocs.io/configuration.html",
    config_key="server_url"
)
```

### Configuration Loading Module

Create a dedicated `config.py` module for configuration loading:

```python
# src/roomz/client/config.py

"""
Configuration loading for Roomz client.

Priority order (highest to lowest):
1. Explicit parameter
2. Environment variable (ROOMZ_SERVER_URL, ROOMZ_DISPLAY_NAME, etc.)
3. Local config file (./roomz.toml)
4. Home config file (~/.roomz.toml)
5. Backward compatibility (~/.roomz/config.toml) - deprecated
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Environment variable mapping
ENV_PREFIX = "ROOMZ_"
ENV_VARS = {
    "server_url": "ROOMZ_SERVER_URL",
    "display_name": "ROOMZ_DISPLAY_NAME",
    "session_cache_file": "ROOMZ_SESSION_CACHE_FILE",
}

# Default config file locations
LOCAL_CONFIG = Path("./roomz.toml")
HOME_CONFIG = Path.home() / ".roomz.toml"
OLD_CONFIG = Path.home() / ".roomz" / "config.toml"  # Deprecated


class Config:
    """Configuration container with loaded values and sources."""

    def __init__(
        self,
        server_url: str | None = None,
        display_name: str | None = None,
        session_cache_file: Path | None = None,
    ):
        self.server_url = server_url
        self.display_name = display_name
        self.session_cache_file = session_cache_file
        self._sources: dict[str, str] = {}

    def get_source(self, key: str) -> str | None:
        """Get the source from which a config value was loaded."""
        return self._sources.get(key)

    @classmethod
    def load(
        cls,
        *,
        server_url: str | None = None,
        display_name: str | None = None,
        session_cache_file: str | Path | None = None,
    ) -> "Config":
        """
        Load configuration with priority: parameter > env > local > home.

        Args:
            server_url: Explicit server URL (highest priority)
            display_name: Explicit display name (highest priority)
            session_cache_file: Explicit session cache file (highest priority)

        Returns:
            Config with loaded values and source tracking
        """
        config = cls()

        # Load from files first (lowest priority)
        file_config = _load_config_file()

        # Apply each config item with priority
        config.server_url = _resolve_value(
            explicit=server_url,
            env_var=ENV_VARS["server_url"],
            file_value=file_config.get("server_url"),
            file_section="client",
        )
        if config.server_url:
            config._sources["server_url"] = "parameter" if server_url else (
                "env" if os.environ.get(ENV_VARS["server_url"])
                else "file"
            )

        config.display_name = _resolve_value(
            explicit=display_name,
            env_var=ENV_VARS["display_name"],
            file_value=file_config.get("display_name"),
            file_section="client",
        )
        if config.display_name:
            config._sources["display_name"] = "parameter" if display_name else (
                "env" if os.environ.get(ENV_VARS["display_name"])
                else "file"
            )

        config.session_cache_file = _resolve_path_value(
            explicit=Path(session_cache_file) if session_cache_file else None,
            env_var=ENV_VARS["session_cache_file"],
            file_value=file_config.get("session_cache_file"),
            default=Path.home() / ".roomz" / "session.json",
        )
        config._sources["session_cache_file"] = (
            "parameter" if session_cache_file else (
                "env" if os.environ.get(ENV_VARS["session_cache_file"])
                else "file" if file_config.get("session_cache_file")
                else "default"
            )
        )

        return config


def _resolve_value(
    explicit: str | None,
    env_var: str,
    file_value: str | None,
    file_section: str = "client",
) -> str | None:
    """Resolve a configuration value with priority."""
    # Priority 1: Explicit parameter
    if explicit is not None:
        return explicit.strip() or None

    # Priority 2: Environment variable
    env_value = os.environ.get(env_var)
    if env_value:
        return env_value.strip() or None

    # Priority 3: File value
    if file_value:
        return file_value.strip() or None

    return None


def _resolve_path_value(
    explicit: Path | None,
    env_var: str,
    file_value: str | None,
    default: Path,
) -> Path:
    """Resolve a path configuration value with priority."""
    # Priority 1: Explicit parameter
    if explicit is not None:
        return explicit

    # Priority 2: Environment variable
    env_value = os.environ.get(env_var)
    if env_value:
        return Path(env_value.strip())

    # Priority 3: File value
    if file_value:
        return Path(file_value.strip())

    # Priority 4: Default
    return default


def _load_config_file() -> dict[str, Any]:
    """
    Load configuration from TOML files.

    Priority:
        1. ./roomz.toml (local)
        2. ~/.roomz.toml (home)
        3. ~/.roomz/config.toml (deprecated)

    Returns:
        Dict with configuration values (flattened from [client] section)
    """
    config: dict[str, Any] = {}

    # Check local config first
    if LOCAL_CONFIG.exists():
        config.update(_parse_toml(LOCAL_CONFIG))
        logger.debug(f"Loaded config from {LOCAL_CONFIG}")

    # Check home config (new location)
    if HOME_CONFIG.exists():
        config.update(_parse_toml(HOME_CONFIG))
        logger.debug(f"Loaded config from {HOME_CONFIG}")
        return config

    # Fall back to old location (deprecated)
    if OLD_CONFIG.exists():
        logger.warning(
            f"Using deprecated config location {OLD_CONFIG}. "
            f"Please migrate to {HOME_CONFIG}"
        )
        config.update(_parse_toml(OLD_CONFIG))

    return config


def _parse_toml(file_path: Path) -> dict[str, Any]:
    """
    Parse a TOML configuration file.

    Expects [client] section for client configuration.

    Args:
        file_path: Path to TOML file

    Returns:
        Dict with configuration values from [client] section
    """
    try:
        import tomllib  # Python 3.11+
    except ImportError:
        import tomli as tomllib  # type: ignore[import-not-found]

    try:
        with open(file_path, "rb") as f:
            data = tomllib.load(f)

        # Extract [client] section
        client_config = data.get("client", {})

        # Also allow top-level keys (for simple configs)
        # but [client] section takes precedence
        result: dict[str, Any] = {}
        for key in ["server_url", "display_name", "session_cache_file"]:
            if key in data:
                result[key] = data[key]
        if "client" in data:
            result.update(data["client"])

        return result

    except Exception as e:
        logger.warning(f"Failed to load config from {file_path}: {e}")
        return {}
```

### Updated AsyncClient Implementation

```python
# src/roomz/client/async_client.py (updated)

from roomz.client.config import Config
from roomz.client.exceptions import ConfigurationError

class AsyncClient:
    """
    Async WebSocket client for Roomz real-time chat.

    Configuration Priority (for server_url, display_name, session_cache_file):
        1. Explicit parameter (highest priority)
        2. Environment variable (ROOMZ_SERVER_URL, ROOMZ_DISPLAY_NAME, etc.)
        3. Local config file (./roomz.toml)
        4. Home config file (~/.roomz.toml)

    Usage:
        # Explicit configuration (highest priority)
        async with AsyncClient(server_url="http://localhost:8000") as client:
            await client.send("Hello!")

        # Zero-configuration (requires ~/.roomz.toml or ROOMZ_SERVER_URL)
        async with AsyncClient() as client:
            await client.send("Hello!")

    Config File (~/.roomz.toml):
        [client]
        server_url = "http://localhost:8000"
        display_name = "Laptop"

    Environment Variables:
        export ROOMZ_SERVER_URL="http://localhost:8000"
        export ROOMZ_DISPLAY_NAME="Laptop"
    """

    def __init__(
        self,
        server_url: str | None = None,
        session_token: str = "",
        *,
        reconnect: bool = True,
        reconnect_delay: float = 1.0,
        max_reconnect_attempts: int = 5,
        connection_timeout: float = 10.0,
        session_cache_file: str | Path | None = None,
        display_name: str | None = None,
    ):
        """
        Initialize async client.

        Args:
            server_url: WebSocket server URL (e.g., "http://localhost:5000").
                       Optional if configured via env/config.
            session_token: Magic link token for authentication (optional)
            reconnect: Enable automatic reconnection (default: True)
            reconnect_delay: Initial delay between reconnection attempts (default: 1.0s)
            max_reconnect_attempts: Maximum reconnection attempts (default: 5)
            connection_timeout: Timeout for connection in seconds (default: 10.0)
            session_cache_file: Path to cache session cookie (default: ~/.roomz/session.json)
            display_name: Optional display name (loaded from env/config if not provided)

        Raises:
            ConfigurationError: If server_url is not configured and connect() is called
        """
        # Load configuration with priority
        config = Config.load(
            server_url=server_url,
            display_name=display_name,
            session_cache_file=session_cache_file,
        )

        self._server_url = config.server_url
        self._session_token = session_token
        self._reconnect = reconnect
        self._reconnect_delay = reconnect_delay
        self._max_reconnect_attempts = max_reconnect_attempts
        self._connection_timeout = connection_timeout
        self._session_cache_file = config.session_cache_file
        self._display_name = config.display_name
        self._config = config  # Keep for debugging

        # ... rest of initialization ...
```

### Connection Validation

```python
async def connect(self, session_token: str | None = None) -> None:
    """
    Establish WebSocket connection with authentication.

    Raises:
        ConfigurationError: If server_url is not configured
        ConnectionError: If connection fails
        AuthenticationError: If authentication fails
    """
    # Validate configuration
    if not self._server_url:
        raise ConfigurationError(
            "server_url is required but not configured. "
            "Set it via:\n"
            "  1. AsyncClient(server_url='...')\n"
            "  2. export ROOMZ_SERVER_URL='...'\n"
            "  3. ./roomz.toml [client] server_url = '...'\n"
            "  4. ~/.roomz.toml [client] server_url = '...'\n"
            "See: https://roomz.readthedocs.io/configuration.html",
            config_key="server_url"
        )

    # ... rest of connection logic ...
```

---

## Usage Examples

### Zero-Configuration (Recommended for Development)

```bash
# ~/.roomz.toml
[client]
server_url = "http://localhost:8000"
display_name = "Laptop"
```

```python
# Python code - simplest possible
async with AsyncClient() as client:
    await client.send("Hello!")
```

### Environment Variables (CI/CD)

```bash
export ROOMZ_SERVER_URL="http://production.example.com"
export ROOMZ_DISPLAY_NAME="CI Bot"
```

```python
async with AsyncClient() as client:
    await client.send("Deploy complete")
```

### Project-Specific Config

```bash
# ./roomz.toml (checked into VCS)
[client]
server_url = "http://dev.example.com:8000"
```

```python
# All team members use same dev server
async with AsyncClient() as client:
    await client.send("Testing...")
```

### Explicit Configuration (Tests)

```python
# Tests always use explicit configuration
client = AsyncClient(
    server_url="http://test-server:8000",
    session_cache_file=None,  # Disable caching in tests
)
```

---

## SyncClient Wrapper

The `SyncClient` wrapper should delegate configuration loading to `AsyncClient`:

```python
class SyncClient:
    """
    Synchronous WebSocket client for Roomz real-time chat.

    Provides a synchronous API wrapping the async implementation.
    Runs async event loop in background thread.

    Configuration is delegated to AsyncClient - see AsyncClient docs for details.
    """

    def __init__(
        self,
        server_url: str | None = None,
        session_token: str = "",
        *,
        reconnect: bool = True,
        reconnect_delay: float = 1.0,
        max_reconnect_attempts: int = 5,
        connection_timeout: float = 10.0,
        session_cache_file: str | Path | None = None,
        display_name: str | None = None,
    ):
        """
        Initialize sync client.

        Args:
            server_url: WebSocket server URL (optional if configured via env/config)
            session_token: Session token for authentication
            session_cache_file: Path to cache session cookie (default: ~/.roomz/session.json)
            display_name: Optional display name (loaded from env/config if not provided)

        See AsyncClient for full configuration documentation.
        """
        self._async_client = AsyncClient(
            server_url=server_url,
            session_token=session_token,
            reconnect=reconnect,
            reconnect_delay=reconnect_delay,
            max_reconnect_attempts=max_reconnect_attempts,
            connection_timeout=connection_timeout,
            session_cache_file=session_cache_file,
            display_name=display_name,
        )
        # ... rest of initialization ...
```

---

## CLI Integration

Update the TUI app to use configuration:

```python
# src/roomz/cli/app_tui.py (updated)

from roomz.client import AsyncClient
from roomz.client.config import Config

class ChatApp(App[None]):
    def __init__(self, server_url: str | None = None):
        super().__init__()

        # Load configuration
        config = Config.load(server_url=server_url)

        self.server_url = config.server_url
        self.email: str | None = None

        # Create client with loaded config
        self.client = AsyncClient(
            server_url=config.server_url,
            session_cache_file=config.session_cache_file,
            display_name=config.display_name,
        )

        # ... rest of initialization ...


def run_tui(server_url: str | None = None) -> None:
    """Run the TUI chat application."""
    app = ChatApp(server_url=server_url)
    app.run()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Roomz Chat TUI")
    parser.add_argument(
        "--server",
        "-s",
        default=None,  # Changed from required default
        help="Server URL (default: loaded from config or ROOMZ_SERVER_URL)",
    )
    args = parser.parse_args()

    run_tui(server_url=args.server)
```

---

## Migration Guide

### For Users (From `~/.roomz/config.toml` to `~/.roomz.toml`)

**Before**:

```bash
# ~/.roomz/config.toml
[client]
display_name = "Laptop"
```

**After**:

```bash
# ~/.roomz.toml
[client]
display_name = "Laptop"
server_url = "http://localhost:8000"  # Now configurable!
```

**Migration Command**:

```bash
mv ~/.roomz/config.toml ~/.roomz.toml
```

### For Developers (Breaking Changes)

**Before** (Current API):

```python
# server_url was required
client = AsyncClient(server_url="http://localhost:8000")
```

**After** (New API):

```python
# server_url is now optional
client = AsyncClient()  # Uses config/env

# Explicit still works
client = AsyncClient(server_url="http://localhost:8000")
```

**Backward Compatibility**: The old `server_url: str` signature still works (positional argument), but now accepts `None`.

---

## Implementation Checklist

- [ ] Create `src/roomz/client/config.py` module
- [ ] Add `ConfigurationError` exception to `exceptions.py`
- [ ] Update `AsyncClient.__init__()` to use `Config.load()`
- [ ] Update `AsyncClient.connect()` to validate `server_url`
- [ ] Update `SyncClient` to delegate to `AsyncClient`
- [ ] Update CLI app to use `Config.load()`
- [ ] Add TOML dependency (`tomli` for Python < 3.11)
- [ ] Add configuration tests
- [ ] Update documentation (docs/configuration.md, docs/api.md)
- [ ] Add migration guide to docs
- [ ] Add deprecation warning for old config location

---

## Testing Strategy

### Unit Tests

```python
# tests/test_config.py

def test_config_priority_parameter_overrides_env():
    """Explicit parameter should override environment variable."""
    os.environ["ROOMZ_SERVER_URL"] = "http://env.example.com"
    config = Config.load(server_url="http://param.example.com")
    assert config.server_url == "http://param.example.com"
    assert config.get_source("server_url") == "parameter"

def test_config_priority_env_overrides_file(tmp_path):
    """Environment variable should override file config."""
    config_file = tmp_path / ".roomz.toml"
    config_file.write_text('[client]\nserver_url = "http://file.example.com"')

    os.environ["ROOMZ_SERVER_URL"] = "http://env.example.com"
    # Mock Path.home() to use tmp_path
    # ...

    config = Config.load()
    assert config.server_url == "http://env.example.com"
    assert config.get_source("server_url") == "env"

def test_config_file_loading_local_over_home(tmp_path):
    """Local config should override home config."""
    home_config = tmp_path / "home" / ".roomz.toml"
    home_config.parent.mkdir(parents=True)
    home_config.write_text('[client]\nserver_url = "http://home.example.com"')

    local_config = tmp_path / "local" / "roomz.toml"
    local_config.parent.mkdir(parents=True)
    local_config.write_text('[client]\nserver_url = "http://local.example.com"')

    # Mock paths
    # ...

    config = Config.load()
    assert config.server_url == "http://local.example.com"

def test_config_backward_compatibility(tmp_path):
    """Old config location should still work with deprecation warning."""
    old_config = tmp_path / ".roomz" / "config.toml"
    old_config.parent.mkdir(parents=True)
    old_config.write_text('[client]\nserver_url = "http://old.example.com"')

    # Should load from old location and log warning
    config = Config.load()
    assert config.server_url == "http://old.example.com"

def test_config_missing_server_url():
    """Should return None for missing server_url."""
    config = Config.load()
    assert config.server_url is None

def test_async_client_raises_on_missing_server_url():
    """Should raise ConfigurationError when connecting without server_url."""
    client = AsyncClient()  # server_url not configured

    with pytest.raises(ConfigurationError) as exc_info:
        asyncio.run(client.connect())

    assert exc_info.value.config_key == "server_url"
    assert "ROOMZ_SERVER_URL" in str(exc_info.value)
```

---

## Documentation Updates

### docs/configuration.md (Add Section)

```markdown
## Client Configuration

The roomz Python client can be configured via:

### Configuration Priority

Configuration is loaded with the following priority (highest first):

1. **Explicit parameter** - `AsyncClient(server_url="...")`
2. **Environment variable** - `ROOMZ_SERVER_URL`, `ROOMZ_DISPLAY_NAME`
3. **Local config file** - `./roomz.toml` (project-level)
4. **Home config file** - `~/.roomz.toml` (user-level)

### Config File Format

Create `~/.roomz.toml`:

\`\`\`toml
[client]
server_url = "http://localhost:8000"
display_name = "Laptop"
\`\`\`

### Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `ROOMZ_SERVER_URL` | WebSocket server URL | `http://localhost:8000` |
| `ROOMZ_DISPLAY_NAME` | Display name for this device | `Laptop` |
| `ROOMZ_SESSION_CACHE_FILE` | Session cache location | `/tmp/session.json` |

### Zero-Configuration Usage

If `server_url` is configured in `~/.roomz.toml` or via `ROOMZ_SERVER_URL`:

\`\`\`python
async with AsyncClient() as client:
    await client.send("Hello!")
\`\`\`

### Migration from ~/.roomz/config.toml

The old config location `~/.roomz/config.toml` is deprecated but still supported.

To migrate:

\`\`\`bash
mv ~/.roomz/config.toml ~/.roomz.toml
\`\`\`
```

---

## Risks and Mitigations

### Risk: Breaking Change for Existing Users

**Mitigation**:
- `server_url: str` parameter still accepts `str` values (backward compatible)
- Old config location still works with deprecation warning
- Clear error message when `server_url` is missing

### Risk: Configuration Complexity

**Mitigation**:
- Zero-configuration is the happy path (just set `~/.roomz.toml`)
- Explicit parameter always works (tests, scripts)
- Clear error messages with actionable guidance

### Risk: TOML Parsing Errors

**Mitigation**:
- Graceful degradation: log warning, continue without file config
- Don't crash on malformed config
- Provide clear error message in logs

---

## Acceptance Criteria

From TODO.md I8-000:

- [x] All config items follow the same priority pattern
- [x] `AsyncClient()` works without explicit `server_url` when config exists
- [x] `ROOMZ_*` environment variables have highest config priority
- [x] `./roomz.toml` loaded from current directory
- [x] `~/.roomz.toml` loaded from home directory
- [x] Explicit parameters override all config sources
- [x] Clear error messages when required config is missing
- [x] Migration or compatibility for existing `~/.roomz/config.toml` users

---

## Summary

This design provides:

1. **Unified Configuration**: All client settings use the same priority system
2. **Zero-Configuration Startup**: Simple `~/.roomz.toml` enables `AsyncClient()` without parameters
3. **Backward Compatibility**: Old config location still works with deprecation warning
4. **Clear Error Messages**: Actionable guidance when configuration is missing
5. **Flexible Usage**: Supports zero-config, env vars, project configs, and explicit parameters

The implementation follows the async-first principle (configuration loaded synchronously before async operations) and maintains the Client/AsyncClient naming convention for consistency.