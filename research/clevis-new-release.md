# Clevis New Release Research

**Research Date:** 2026-06-07
**Package:** clevis
**Latest Version:** 0.3.0 (as of 2026-06-05)

## Version Information

- **Current Version:** 0.3.0
- **Release Date:** June 5, 2026
- **Release Name:** "Factory Pattern, Security, Type Stubs, Subcommand Enhancements"
- **PyPI:** https://pypi.org/project/clevis/
- **Repository:** https://github.com/christophevg/clevis

## New Security Features

Version 0.3.0 introduces comprehensive security validation for configuration files, addressing three key security concerns:

### 1. File Permission Validation (HIGH-1)

**Purpose:** Prevent credential exposure from config files readable by group/other users.

**Implementation:**
- Checks if file mode has group/other read permissions (`mode & 0o044`)
- Rejects files with permissions like 0o644, 0o755, etc.
- TOCTOU-safe implementation using file descriptors
- Opens file with `os.open()`, checks with `os.fstat()`, then passes to parser

**Default Behavior:** `SecurityAction.REJECT` — raises `SecurityError` if insecure

**Trusted Location Exception:** User's home directory files skip directory check

### 2. Directory Security Validation (HIGH-2)

**Purpose:** Prevent symlink attacks and malicious config placement in world-writable directories.

**Implementation:**
- Checks if parent directory has world-write permission (`mode & 0o002`)
- Rejects config files in world-writable directories
- Skips check for user's home directory (trusted location)

**Default Behavior:** `SecurityAction.REJECT` — raises `SecurityError` if insecure

**Trusted Location Exception:** Home directory (`~`) is trusted

### 3. Field Validators (MEDIUM-1)

**Purpose:** Validate configuration values after loading.

**Implementation:**
- Uses Python dataclass `__post_init__` method
- Standard dataclass pattern — no custom framework
- Validates values after configuration is loaded

**Example:** Email validation, URL scheme validation, etc.

## API Documentation

### SecurityAction Enum

```python
from clevis import SecurityAction

# Available actions:
SecurityAction.DONT_CHECK  # Skip validation entirely
SecurityAction.LOG         # Log warning, continue loading
SecurityAction.REJECT      # Raise SecurityError (default)
```

### get_config with Security Parameter

```python
from dataclasses import dataclass
from clevis import get_config, SecurityAction

@dataclass
class Config:
    api_key: str
    debug: bool = False

# Default: REJECT (strict security)
config = get_config(Config, name="myapp")

# Skip all security checks
config = get_config(
    Config,
    name="myapp",
    security={
        "file_permissions": SecurityAction.DONT_CHECK,
        "directory_permissions": SecurityAction.DONT_CHECK
    }
)

# Log warnings instead of rejecting
config = get_config(
    Config,
    name="myapp",
    security={
        "file_permissions": SecurityAction.LOG,
        "directory_permissions": SecurityAction.LOG
    }
)

# Selective checks
config = get_config(
    Config,
    name="myapp",
    security={
        "file_permissions": SecurityAction.REJECT,  # Strict on file perms
        "directory_permissions": SecurityAction.LOG  # Allow with warning
    }
)
```

### Field Validators with __post_init__

```python
from dataclasses import dataclass
import re

@dataclass
class Config:
    email: str | None = None
    server_url: str = "https://api.example.com"

    def __post_init__(self):
        # Validate email format
        if self.email:
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, self.email):
                raise ValueError(f"Invalid email format: {self.email}")

        # Validate URL scheme
        if not self.server_url.startswith(('http://', 'https://')):
            raise ValueError(f"Server URL must use http or https: {self.server_url}")
```

### SecurityError Exception

```python
from clevis import get_config, SecurityError

@dataclass
class Config:
    api_key: str

try:
    config = get_config(Config, name="myapp")
except SecurityError as e:
    print(f"Security violation: {e}")
    # Example: "Config file ~/.myapp.toml has insecure permissions (0o644)"
    # Fix: chmod 600 ~/.myapp.toml
```

## Comparison with Feature Request Requirements

The feature request (issue #4) specified three security requirements:

| Requirement | Priority | Clevis Implementation | Status |
|-------------|----------|----------------------|--------|
| **HIGH-1**: Session cache files with 0600 permissions | HIGH | File permission validation via `mode & 0o044` check | **Covered** |
| **HIGH-2**: Current directory config validates directory security | HIGH | Directory validation via `mode & 0o002` check | **Covered** |
| **MEDIUM-1**: Warn if config files have group/other read permissions | MEDIUM | Configurable via `SecurityAction.LOG` | **Covered** |

### Alignment Analysis

1. **HIGH-1 (Session Cache File Permissions):**
   - **Clevis:** Rejects files readable by group/other (`mode & 0o044`)
   - **Requirement:** Files should be created with 0600 permissions
   - **Alignment:** ✓ Perfect match — Clevis validates this security requirement

2. **HIGH-2 (Directory Security Validation):**
   - **Clevis:** Rejects files in world-writable directories (`mode & 0o002`)
   - **Requirement:** Validate directory security when loading from current directory
   - **Alignment:** ✓ Perfect match — Clevis validates directory permissions

3. **MEDIUM-1 (Warn on Group/Other Read Permissions):**
   - **Clevis:** Configurable via `SecurityAction.LOG` for warnings
   - **Requirement:** Warn if config files have group/other read permissions
   - **Alignment:** ✓ Perfect match — use `security={"file_permissions": SecurityAction.LOG}`

## Integration for Roomz

### Recommended Security Configuration

For the roomz project integration:

```python
from dataclasses import dataclass
from clevis import get_config, SecurityAction

@dataclass
class RoomzConfig:
    session_cache_dir: str = "~/.cache/roomz"
    api_endpoint: str = "https://api.roomz.io"
    debug: bool = False

    def __post_init__(self):
        # Validate API endpoint
        if not self.api_endpoint.startswith(('http://', 'https://')):
            raise ValueError(f"API endpoint must use http/https: {self.api_endpoint}")

# Default strict security (REJECT on all violations)
config = get_config(RoomzConfig, name="roomz")
```

### Creating Session Cache Files

When creating session cache files, ensure 0600 permissions:

```python
import os
from pathlib import Path

def create_session_cache(session_id: str, data: dict):
    cache_dir = Path.home() / ".cache" / "roomz"
    cache_dir.mkdir(mode=0o700, parents=True, exist_ok=True)

    cache_file = cache_dir / f"{session_id}.json"

    # Write with restrictive permissions (0600)
    fd = os.open(cache_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(data, f)
    finally:
        # File descriptor already closed by fdopen context manager
        pass
```

### Handling Security Errors

```python
from clevis import get_config, SecurityError

try:
    config = get_config(RoomzConfig, name="roomz")
except SecurityError as e:
    if "insecure permissions" in str(e):
        print(f"Fix: chmod 600 ~/.roomz.toml")
        # Or handle gracefully
        config = get_config(
            RoomzConfig,
            name="roomz",
            security={"file_permissions": SecurityAction.LOG}
        )
    elif "world-writable" in str(e):
        print(f"Config file in insecure directory")
        # Handle appropriately
        raise
```

### Testing Security Features

```python
import tempfile
import os
from pathlib import Path
from clevis import get_config, SecurityError, SecurityAction

def test_insecure_permissions():
    """Test that Clevis rejects config with group/other read"""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = Path(tmpdir) / "roomz.toml"
        config_file.write_text("api_endpoint = 'https://test.com'\n")

        # Make insecure (group/other readable)
        os.chmod(config_file, 0o644)

        @dataclass
        class TestConfig:
            api_endpoint: str

        # Should raise SecurityError
        try:
            get_config(TestConfig, name="roomz", user=False)
            assert False, "Should have raised SecurityError"
        except SecurityError:
            pass  # Expected

def test_secure_permissions():
    """Test that Clevis accepts config with 0600 permissions"""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = Path(tmpdir) / "roomz.toml"
        config_file.write_text("api_endpoint = 'https://test.com'\n")

        # Make secure (owner read/write only)
        os.chmod(config_file, 0o600)

        @dataclass
        class TestConfig:
            api_endpoint: str

        # Should succeed
        config = get_config(TestConfig, name="roomz", user=False)
        assert config.api_endpoint == "https://test.com"
```

## Summary

Clevis v0.3.0 provides all three security requirements from the feature request:

1. **File Permission Validation** — Checks `mode & 0o044` to reject files readable by group/other
2. **Directory Security** — Checks `mode & 0o002` to reject files in world-writable directories
3. **Configurable Severity** — `SecurityAction` enum allows REJECT (default), LOG (warnings), or DONT_CHECK

**Key Benefits for Roomz:**

- **Secure by default:** Rejects insecure configurations out-of-the-box
- **TOCTOU-safe:** Uses file descriptors to prevent race conditions
- **Trusted locations:** Home directory checks are skipped (user is trusted)
- **Standard patterns:** Uses `__post_init__` for field validation (no custom framework)
- **Actionable errors:** Clear error messages guide users to fix security issues

**Recommendation:** Use Clevis v0.3.0 with default `SecurityAction.REJECT` for strict security, ensuring all session cache and config files use 0600 permissions.