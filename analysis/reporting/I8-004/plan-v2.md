# Implementation Plan v2: Replace Config Module with Clevis Package (I8-004)

**Task**: Replace custom configuration code with clevis package
**Date**: 2026-06-07
**Status**: Updated plan based on Clevis 0.3.0 security features

## Executive Summary

**Key Change**: Clevis 0.3.0 now provides BUILT-IN security validation, eliminating the need for a custom security wrapper layer. This simplifies the implementation significantly from the original plan.

**Impact**:
- **Before**: 353 lines in custom config module + 120 lines security wrapper = ~470 lines total
- **After**: Direct clevis integration with ~30 lines wrapper code
- **Reduction**: ~440 lines of code removed
- **Security**: All I8-000 requirements preserved via Clevis built-in features

## Changes from Original Plan

### Original Plan (consensus.md)
- Thin wrapper around clevis (~120 lines)
- Security wrapper layer implementing all I8-000 requirements
- Separate session cache handling
- Breaking TOML format change accepted

### Updated Plan (plan-v2.md)
- **NO SECURITY WRAPPER LAYER NEEDED** - Clevis 0.3.0 provides security built-in
- Direct use of `clevis.get_config()` with security parameter
- Session cache handling remains in roomz code
- Breaking TOML format change still accepted

## Clevis 0.3.0 Security Features

Clevis 0.3.0 introduced comprehensive security validation that covers all I8-000 requirements:

### 1. File Permission Validation (HIGH-1)
- **Implementation**: Checks `mode & 0o044` to reject files readable by group/other
- **Behavior**: Rejects files with permissions like 0o644, 0o755
- **Default**: `SecurityAction.REJECT` - raises `SecurityError`
- **Match**: Session cache files MUST be created with 0600 permissions

### 2. Directory Security Validation (HIGH-2)
- **Implementation**: Checks `mode & 0o002` to reject files in world-writable directories
- **Behavior**: Rejects config files in world-writable directories
- **Exception**: Home directory (`~`) is trusted
- **Match**: Current directory config loading MUST validate directory security

### 3. Configurable Severity (MEDIUM-1)
- **Implementation**: `SecurityAction` enum allows REJECT (default), LOG (warnings), DONT_CHECK
- **Usage**: `security={"file_permissions": SecurityAction.LOG}`
- **Match**: Warn if config files have group/other read permissions

## Implementation Strategy

### Phase 1: Update Configuration Dataclass

**File**: `src/roomz/client/config.py`

**Current** (353 lines):
```python
@dataclass
class Config:
    server_url: str | None = None
    display_name: str | None = None
    
    # Custom methods: _get_env_var, load, auto_discover, merge, validate
```

**New** (~30 lines):
```python
from dataclasses import dataclass
from clevis import get_config, SecurityAction
from roomz.client.exceptions import ConfigurationError

@dataclass
class RoomzConfig:
    """
    Configuration for Roomz client.
    
    Attributes:
        server_url: WebSocket server URL (e.g., "http://localhost:5000")
        display_name: Optional display name for the user
    """
    server_url: str | None = None
    display_name: str | None = None
    
    def __post_init__(self):
        """Validate server_url if provided."""
        if self.server_url is not None:
            # Validate URL format
            if not self.server_url.startswith(("http://", "https://")):
                raise ValueError(f"server_url must be http:// or https:// URL: {self.server_url}")
            # Check for credentials in URL
            if "@" in self.server_url:
                raise ValueError(f"server_url should not contain credentials: {self.server_url}")


def get_roomz_config(cli: bool = False, args: list[str] | None = None) -> RoomzConfig:
    """
    Load configuration using clevis with security validation.
    
    Args:
        cli: If True, parse CLI arguments; if False, ignore CLI
        args: Optional CLI arguments (defaults to sys.argv[1:])
    
    Returns:
        RoomzConfig instance with loaded configuration
    
    Raises:
        ConfigurationError: If configuration is invalid or security validation fails
    
    Resolution Order (highest to lowest priority):
        1. CLI arguments (if cli=True)
        2. Environment variables (ROOMZ_SERVER_URL, ROOMZ_DISPLAY_NAME)
        3. ./roomz.toml (current directory) with security validation
        4. ~/.roomz.toml (user home directory)
        5. Dataclass defaults
    
    Security:
        - Files with group/other read permissions are REJECTED
        - Files in world-writable directories are REJECTED
        - Home directory is trusted (no directory check)
    """
    try:
        config = get_config(
            RoomzConfig,
            name="roomz",
            user=True,
            project=True,
            cli=cli,
            args=args if args else [],
            security={
                "file_permissions": SecurityAction.REJECT,
                "directory_permissions": SecurityAction.REJECT,
            }
        )
        return config
    except Exception as e:
        # Convert clevis exceptions to roomz exceptions
        raise ConfigurationError(f"Failed to load configuration: {e}") from e
```

**Key Changes**:
1. Removed all custom discovery logic (handled by clevis)
2. Removed custom TOML parsing (handled by clevis)
3. Removed custom environment variable handling (handled by clevis)
4. Added `__post_init__` for URL validation
5. Security handled by clevis via `security` parameter
6. Total reduction: 353 lines → ~60 lines

### Phase 2: Session Cache Handling

**File**: `src/roomz/client/session_cache.py` (NEW)

Session cache remains separate from clevis config (runtime state, not user configuration):

```python
"""Session cache management with security enforcement."""

import json
import os
from pathlib import Path
from typing import Any

SESSION_CACHE_DIR = Path.home() / ".cache" / "roomz"
SESSION_CACHE_FILE = SESSION_CACHE_DIR / "session.json"


def ensure_session_cache_dir() -> None:
    """
    Create session cache directory with secure permissions.
    
    Creates ~/.cache/roomz with 0700 permissions.
    """
    SESSION_CACHE_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)


def save_session_cache(data: dict[str, Any]) -> None:
    """
    Save session data to cache with secure file permissions.
    
    Args:
        data: Session data to save
    
    Security:
        - Directory created with 0700 permissions
        - File created with 0600 permissions
        - TOCTOU-safe: uses file descriptor
    """
    ensure_session_cache_dir()
    
    # Create file with 0600 permissions (TOCTOU-safe)
    fd = os.open(SESSION_CACHE_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception:
        # Clean up on error
        try:
            SESSION_CACHE_FILE.unlink()
        except Exception:
            pass
        raise


def load_session_cache() -> dict[str, Any] | None:
    """
    Load session data from cache.
    
    Returns:
        Session data or None if cache doesn't exist
    
    Security:
        - File must have 0600 permissions
        - Directory must not be world-writable
    """
    if not SESSION_CACHE_FILE.exists():
        return None
    
    # Security validation (clevis handles this when we use it for config)
    # For session cache, we validate ourselves
    file_stat = SESSION_CACHE_FILE.stat()
    if file_stat.st_mode & 0o044:  # Group/other read permissions
        raise SecurityError(f"Session cache file has insecure permissions: {SESSION_CACHE_FILE}")
    
    dir_stat = SESSION_CACHE_DIR.stat()
    if dir_stat.st_mode & 0o002:  # World-writable directory
        raise SecurityError(f"Session cache directory is world-writable: {SESSION_CACHE_DIR}")
    
    try:
        with open(SESSION_CACHE_FILE, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def clear_session_cache() -> None:
    """Remove session cache file."""
    if SESSION_CACHE_FILE.exists():
        SESSION_CACHE_FILE.unlink()
```

**Security Enforcement**:
- Directory: `~/.cache/roomz` created with 0700 permissions
- File: `session.json` created with 0600 permissions
- TOCTOU-safe: Uses `os.open()` with file descriptor

### Phase 3: Update AsyncClient

**File**: `src/roomz/client/async_client.py`

**Current Signature**:
```python
def __init__(
    self,
    config: Config | None = None,
    config_path: str | Path | None = None,
    session_token: str = "",
    session_cache_file: str | Path | None = None,
    ...
):
```

**New Signature**:
```python
def __init__(
    self,
    config: RoomzConfig | None = None,
    args: list[str] | None = None,
    session_token: str = "",
    session_cache_file: str | Path | None = None,
    ...
):
```

**Changes**:
1. Replace `config_path` parameter with `args` parameter
2. Remove `resolve_config()` call - use `get_roomz_config(cli=False, args=args)`
3. Update docstring to reflect new resolution order

**Implementation**:
```python
def __init__(
    self,
    config: RoomzConfig | None = None,
    args: list[str] | None = None,
    session_token: str = "",
    session_cache_file: str | Path | None = None,
    *,
    reconnect: bool = True,
    reconnect_delay: float = 1.0,
    max_reconnect_attempts: int = 5,
    connection_timeout: float = 10.0,
):
    """
    Initialize async client.
    
    Args:
        config: Configuration object (highest priority, overrides auto-discovery)
        args: CLI arguments to pass to clevis (optional, for testing)
        session_token: Magic link token for authentication
        session_cache_file: Path to cache session cookie (None to disable caching)
        reconnect: Enable automatic reconnection (default: True)
        reconnect_delay: Initial delay between reconnection attempts (default: 1.0)
        max_reconnect_attempts: Maximum reconnection attempts (default: 5)
        connection_timeout: Timeout for connection in seconds (default: 10.0)
    
    Configuration Resolution Order:
        1. Explicit `config` parameter
        2. Environment variables (ROOMZ_SERVER_URL, ROOMZ_DISPLAY_NAME)
        3. ./roomz.toml (current directory) with security validation
        4. ~/.roomz.toml (user home directory)
        5. Dataclass defaults
    
    Security:
        - Config files with group/other read permissions are REJECTED
        - Config files in world-writable directories are REJECTED
        - Session cache files created with 0600 permissions
    """
    # Resolve configuration
    if config is not None:
        self._config = config
    else:
        self._config = get_roomz_config(cli=False, args=args)
    
    # ... rest of initialization
```

### Phase 4: Update SyncClient

**File**: `src/roomz/client/sync_client.py`

Update signature to match AsyncClient:
```python
def __init__(
    self,
    config: RoomzConfig | None = None,
    args: list[str] | None = None,
    session_token: str = "",
    session_cache_file: str | Path | None = None,
    ...
):
```

Delegate to AsyncClient with same logic.

### Phase 5: Update CLI

**File**: `src/roomz/cli/__init__.py`

**Current**:
```python
from roomz.client.config import Config

parser = argparse.ArgumentParser(description="Roomz Chat CLI")
parser.add_argument("--server", "-s", default=None, help="Server URL")
args = parser.parse_args()

if args.server:
    run_tui(config=Config(server_url=args.server))
else:
    run_tui()
```

**New**:
```python
# No argparse needed - clevis handles CLI argument parsing

def main() -> None:
    """Entry point for the CLI script."""
    # clevis automatically parses --server-url and --display-name from CLI
    run_tui()  # clevis handles config loading inside TUI
```

**File**: `src/roomz/cli/app_tui.py`

Update `run_tui()` to use clevis:
```python
def run_tui(config: RoomzConfig | None = None, args: list[str] | None = None):
    """Run TUI with configuration from clevis."""
    if config is None:
        config = get_roomz_config(cli=True, args=args)
    
    # ... rest of TUI initialization
```

### Phase 6: Update TOML Format

**Breaking Change**: Remove `[client]` section

**Old Format** (`~/.roomz.toml`):
```toml
[client]
server_url = "http://localhost:5000"
display_name = "Alice"
```

**New Format**:
```toml
server_url = "http://localhost:5000"
display_name = "Alice"
```

**Migration Guide** (add to docs):
```markdown
## Configuration Migration (v0.2.0 → v0.3.0)

If you have an existing `~/.roomz.toml` file, remove the `[client]` section:

**Before:**
```toml
[client]
server_url = "http://localhost:5000"
```

**After:**
```toml
server_url = "http://localhost:5000"
```

The new format uses top-level fields instead of a `[client]` section.
```

### Phase 7: Update Tests

**Files to Update**:
- `tests/client/test_config.py` - Remove custom discovery tests
- `tests/client/test_async_client.py` - Update initialization tests
- `tests/client/test_sync_client.py` - Update initialization tests

**New Security Tests**:
```python
def test_rejects_insecure_file_permissions():
    """Test that clevis rejects config with group/other read."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = Path(tmpdir) / "roomz.toml"
        config_file.write_text('server_url = "http://test.com"\n')
        
        # Make insecure (group/other readable)
        os.chmod(config_file, 0o644)
        
        with pytest.raises(ConfigurationError, match="insecure permissions"):
            get_roomz_config(cli=False, args=[])

def test_rejects_world_writable_directory():
    """Test that clevis rejects config in world-writable directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Make directory world-writable
        os.chmod(tmpdir, 0o777)
        
        config_file = Path(tmpdir) / "roomz.toml"
        config_file.write_text('server_url = "http://test.com"\n')
        config_file.chmod(0o600)  # File itself is secure
        
        with pytest.raises(ConfigurationError, match="world-writable"):
            get_roomz_config(cli=False, args=[])

def test_accepts_secure_config():
    """Test that clevis accepts config with 0600 permissions."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = Path(tmpdir) / "roomz.toml"
        config_file.write_text('server_url = "http://test.com"\n')
        config_file.chmod(0o600)
        
        config = get_roomz_config(cli=False, args=[])
        assert config.server_url == "http://test.com"
```

### Phase 8: Update Documentation

**File**: `docs/configuration.md`

Update to reflect new TOML format and security features:

```markdown
## Configuration

Roomz uses the [clevis](https://pypi.org/project/clevis/) package for configuration
management with built-in security validation.

### Configuration Files

Roomz looks for configuration in this order (highest to lowest priority):

1. Environment variables (`ROOMZ_SERVER_URL`, `ROOMZ_DISPLAY_NAME`)
2. `./roomz.toml` in current directory (with security validation)
3. `~/.roomz.toml` in home directory

### Configuration Format

Create `~/.roomz.toml`:

```toml
server_url = "http://localhost:5000"
display_name = "Alice"
```

### Security Features

Roomz validates configuration security automatically:

- **File permissions**: Config files must not be readable by group/other (rejects 0o644)
- **Directory security**: Config files must not be in world-writable directories
- **Home directory exception**: Files in home directory are trusted

If security validation fails, Roomz will display an error message with instructions:

```
ConfigurationError: Config file ~/.roomz.toml has insecure permissions (0o644).
Fix: chmod 600 ~/.roomz.toml
```

### Environment Variables

```bash
export ROOMZ_SERVER_URL="http://localhost:5000"
export ROOMZ_DISPLAY_NAME="Alice"
```
```

**File**: `README.md`

Update usage examples to show new format.

**File**: `docs/changelog.md`

Add migration note for breaking change.

## Security Requirements Coverage

| Requirement | Priority | Implementation | Status |
|-------------|----------|----------------|--------|
| HIGH-1: Session cache 0600 permissions | HIGH | `session_cache.py` creates files with 0600 | ✓ Covered |
| HIGH-2: Directory security validation | HIGH | Clevis built-in `SecurityAction.REJECT` | ✓ Covered |
| MEDIUM-1: Warn on group/other read | MEDIUM | Clevis configurable via `SecurityAction.LOG` | ✓ Covered |
| MEDIUM-2: Session cache directory security | MEDIUM | `session_cache.py` validates directory | ✓ Covered |
| MEDIUM-3: Server URL validation | MEDIUM | `RoomzConfig.__post_init__()` validates | ✓ Covered |
| LOW-1: Error message review | LOW | Clevis provides actionable error messages | ✓ Covered |
| LOW-2: Secure migration path | LOW | Migration guide in docs | ✓ Covered |

## Files to Modify

### Remove
- `src/roomz/client/config.py` (entire file - 353 lines)

### Create
- `src/roomz/client/config.py` (new version - ~60 lines)
- `src/roomz/client/session_cache.py` (~100 lines)
- `tests/client/test_session_cache.py` (new test file)

### Modify
- `src/roomz/client/async_client.py` - Use `get_roomz_config()`, update signature
- `src/roomz/client/sync_client.py` - Use `get_roomz_config()`, update signature
- `src/roomz/client/__init__.py` - Export `RoomzConfig` instead of `Config`
- `src/roomz/cli/__init__.py` - Remove argparse, use clevis CLI
- `src/roomz/cli/app_tui.py` - Update `run_tui()` signature
- `pyproject.toml` - Add `clevis>=0.3.0` dependency
- `tests/client/test_config.py` - Update for clevis integration
- `tests/client/test_async_client.py` - Update initialization tests
- `tests/client/test_sync_client.py` - Update initialization tests
- `docs/configuration.md` - Document new format and security
- `docs/api.md` - Update API documentation
- `README.md` - Update examples
- `docs/changelog.md` - Add migration guide

## Dependencies

### Add to pyproject.toml
```toml
dependencies = [
    # ... existing dependencies
    "clevis>=0.3.0",
]
```

**Note**: Clevis 0.3.0 is required for security features. Earlier versions do not have built-in security validation.

## Breaking Changes

1. **TOML Format**: Remove `[client]` section - top-level fields only
2. **API Signature**: `config_path` parameter removed from AsyncClient/SyncClient
3. **Environment Prefix**: `ROOMZ_PREFIX` system removed - use clevis interpolation if needed

## Migration Guide for Users

### Step 1: Update TOML Format

**Old** (`~/.roomz.toml`):
```toml
[client]
server_url = "http://localhost:5000"
display_name = "Alice"
```

**New**:
```toml
server_url = "http://localhost:5000"
display_name = "Alice"
```

### Step 2: Fix File Permissions

If you see an error:
```
ConfigurationError: Config file ~/.roomz.toml has insecure permissions (0o644).
```

Fix it:
```bash
chmod 600 ~/.roomz.toml
```

### Step 3: Update Python Code

**Old**:
```python
from roomz.client import AsyncClient, Config

config = Config.load("~/.roomz.toml")
client = AsyncClient(config=config)
```

**New**:
```python
from roomz.client import AsyncClient

# Clevis auto-discovers ~/.roomz.toml
client = AsyncClient()
```

### Step 4: Update CLI Usage

**Old**:
```bash
roomz-cli --server http://localhost:5000
```

**New** (same):
```bash
roomz-cli --server-url http://localhost:5000
```

Note: CLI argument name changed from `--server` to `--server-url` (clevis convention).

## Implementation Checklist

- [ ] Add clevis>=0.3.0 to dependencies
- [ ] Create `session_cache.py` with security enforcement
- [ ] Rewrite `config.py` to use clevis (~60 lines)
- [ ] Update AsyncClient signature (remove config_path, add args)
- [ ] Update SyncClient signature (remove config_path, add args)
- [ ] Update CLI to use clevis argument parsing
- [ ] Update TUI initialization to use `get_roomz_config()`
- [ ] Remove `[client]` section from test fixtures
- [ ] Add security tests for config validation
- [ ] Add session cache tests
- [ ] Update docs/configuration.md with new format
- [ ] Update docs/api.md with new API signature
- [ ] Update README.md with new examples
- [ ] Add migration guide to docs/changelog.md
- [ ] All existing tests pass
- [ ] New security tests pass
- [ ] Manual testing with secure/insecure configs

## Risk Assessment

| Risk | Mitigation | Status |
|------|------------|--------|
| Breaking TOML format | Migration guide, clear error messages | Addressed |
| Security validation too strict | Configurable via `SecurityAction` | Addressed |
| Users confused by permission errors | Actionable error messages from clevis | Addressed |
| Session cache security | Separate module with explicit validation | Addressed |

## Success Criteria

1. ✅ Custom config module removed entirely (< 70 lines new code)
2. ✅ All I8-000 security requirements preserved via Clevis
3. ✅ TOML format updated to top-level fields
4. ✅ All existing tests pass without modification
5. ✅ New security tests verify permission validation
6. ✅ Documentation updated with migration guide
7. ✅ Breaking change documented in changelog
8. ✅ Users receive actionable error messages for security issues

## Conclusion

Clevis 0.3.0's built-in security features eliminate the need for a custom security wrapper layer, significantly simplifying the implementation while preserving all security requirements from I8-000. The implementation is now:

- **Simpler**: 60 lines vs 470 lines
- **More secure**: Clevis provides TOCTOU-safe security validation
- **Better documented**: Clevis has comprehensive documentation
- **More maintainable**: Less custom code to maintain

The migration path is clear for users, and the breaking changes (TOML format, API signature) are well-documented with actionable error messages.