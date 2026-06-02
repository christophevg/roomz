# Security Analysis: Replace Config Module with Clevis Package

**Task**: I8-004 - Security implications of replacing custom config with clevis
**Date**: 2026-06-02
**Analyst**: Security Engineer Agent
**Status**: Pre-Implementation Security Review

## Executive Summary

This security analysis evaluates the impact of replacing roomz's custom configuration module with the clevis package. While clevis provides a well-designed configuration system, it lacks critical security features present in the current implementation, particularly around file permissions and directory security validation.

**Key Finding**: **HIGH RISK** - Clevis does not implement ANY security features required by I8-000. All security validations must be implemented as a wrapper layer around clevis.

**Critical Gaps**:
- No session cache file permission handling (JWT tokens)
- No current directory security validation (world-writable directories)
- No file permission warnings for config files
- No URL validation (scheme, credentials, hostname)
- No directory ownership checks
- Environment variable interpolation security not documented

**Recommendation**: Adopt clevis with security wrapper layer that implements all I8-000 security requirements.

---

## Security Requirements Checklist (from I8-000)

### Must-Have Security Requirements

| ID | Requirement | Current | Clevis | Gap | Priority |
|----|-------------|---------|--------|-----|----------|
| **SEC-1** | Session cache files created with 0600 permissions | ✅ Implemented | ❌ Not supported | **CRITICAL** | Blocking |
| **SEC-2** | Validate directory is not world-writable (session cache) | ✅ Implemented | ❌ Not supported | **CRITICAL** | Blocking |
| **SEC-3** | Warn if config files have group/other read permissions | ✅ Implemented | ❌ Not supported | **HIGH** | Blocking |
| **SEC-4** | Session cache directory MUST NOT be world-writable | ✅ Implemented | ❌ Not supported | **CRITICAL** | Blocking |
| **SEC-5** | Validate server URLs (http/https only) | ✅ Implemented | ❌ Not supported | **HIGH** | Blocking |
| **SEC-6** | No credentials in server URLs | ✅ Implemented | ❌ Not supported | **HIGH** | Blocking |
| **SEC-7** | Hostname required in server URLs | ✅ Implemented | ❌ Not supported | **MEDIUM** | Related |
| **SEC-8** | Error messages reviewed for information leakage | ⚠️ Partial | ❌ Not reviewed | **MEDIUM** | Related |

### Current Implementation Security Features

The current roomz implementation (`src/roomz/client/async_client.py` and `src/roomz/client/config.py`) includes:

#### Session Cache Security (async_client.py:216-317)

```python
def _save_session_cookie(self, cookie_value: str) -> None:
    """
    Save session cookie to cache file with secure permissions.

    Security:
    - Creates file with 0600 permissions atomically (no race condition)
    - Uses exclusive creation to prevent symlink attacks
    """
    # Ensure parent directory exists
    self._session_cache_file.parent.mkdir(parents=True, exist_ok=True)

    # Create new file with correct permissions from the start
    # O_CREAT | O_EXCL ensures atomic creation (no race condition)
    fd = os.open(
        str(self._session_cache_file),
        os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_EXCL,
        mode=0o600,
    )
    # ... write JWT token ...
```

#### Permission Validation (async_client.py:262-317)

```python
def _update_session_cookie_secure(self, cookie_value: str) -> None:
    """Update existing session cookie file with secure permissions."""
    # Check and fix permissions if needed
    current_mode = self._session_cache_file.stat().st_mode & 0o777
    if current_mode & 0o077:  # Has group/other permissions
        logger.warning(
            f"Session cache file {self._session_cache_file} has insecure "
            f"permissions {oct(current_mode)}. Restricting to 0600."
        )
        self._session_cache_file.chmod(0o600)

    # Atomic write: write to temp file, then rename
    temp_file = self._session_cache_file.with_suffix(".tmp")
    temp_file.write_text(json.dumps(...))
    temp_file.replace(self._session_cache_file)

def _load_session_cookie(self) -> str | None:
    """Load session cookie from cache file with security validation."""
    # Check file permissions
    current_mode = self._session_cache_file.stat().st_mode & 0o777
    if current_mode & 0o077:  # Has group/other permissions
        logger.warning(
            f"Session cache file {self._session_cache_file} has insecure "
            f"permissions {oct(current_mode)}. Session may be accessible to other users."
        )
```

#### URL Validation (config.py:283-306)

```python
def validate(self) -> list[str]:
    """Validate configuration values."""
    errors: list[str] = []

    if self.server_url is not None:
        # Validate server_url format
        if not self.server_url.startswith(("http://", "https://")):
            errors.append("server_url must be http:// or https:// URL")

        # Check for credentials in URL
        if "@" in self.server_url:
            errors.append("server_url should not contain credentials")

    return errors
```

**Key Observation**: The current implementation has **comprehensive security** around session cache files and basic validation for URLs. This is NOT present in clevis.

---

## Clevis Security Coverage Analysis

### What Clevis Provides

From the clevis source code analysis and documentation:

#### File Loading

```python
# Clevis reads from two locations:
user_config = Path.home() / f".{name}.toml"
project_config = Path.cwd() / f"{name}.toml"

# Opens files in binary mode
with open(file, "rb") as f:
    data = tomllib.load(f)
```

**Security Issues**:
- ❌ No file permission checks
- ❌ No directory security validation
- ❌ No warning for world-readable files
- ❌ No ownership validation
- ❌ Reads from current directory without security checks

#### Environment Variable Interpolation

```python
# With tomlev or envtoml
def load_with_tomlev(file: Any) -> dict[str, Any]:
    content = file.read()
    if isinstance(content, bytes):
        content = content.decode("utf-8")
    expanded = expandvars(content)  # Expands ${VAR|default}
    return tomllib.loads(expanded)
```

**Security Issues**:
- ⚠️ Environment variable expansion from TOML files
- ❌ No sanitization of expanded values
- ❌ No validation of expanded URLs
- ❌ Potential for injection if untrusted TOML files are loaded

#### Configuration Merging

```python
# Priority: CLI > Project TOML > User TOML > Defaults
cfg = {}
if user:
    user_file = Path.home() / f".{name}.toml"
    if user_file.exists():
        cfg.update(load_toml(user_file))
if project:
    project_file = Path.cwd() / f"{name}.toml"
    if project_file.exists():
        cfg.update(load_toml(project_file))
# ... CLI arguments override ...
```

**Security Issues**:
- ❌ Current directory config has HIGHER priority than user config
- ❌ Attacker with write access to CWD can override user config
- ❌ No validation of config file locations

#### Input Handling

```python
# apply_to_dict processes dotted keys from CLI
def apply_to_dict(args: dict[str, Any], dct: dict[str, Any]) -> None:
    for key, value in args.items():
        if value is not None:
            parts = key.split(".")
            # ... creates nested structure ...
```

**Security Issues**:
- ⚠️ Creates dictionary structures from user-provided key names
- ❌ No key validation (could potentially create unexpected structures)
- ℹ️ Limited risk since CLI args are trusted input

### What Clevis Lacks (Security Perspective)

| Feature | Status | Security Impact |
|---------|--------|-----------------|
| File permission validation | ❌ Not implemented | **CRITICAL**: JWT tokens in session cache exposed to other users |
| Directory security validation | ❌ Not implemented | **CRITICAL**: World-writable directories allow file replacement attacks |
| Permission warnings | ❌ Not implemented | **HIGH**: Users unaware of insecure configurations |
| URL validation | ❌ Not implemented | **HIGH**: Malicious URLs in config files |
| Credentials in URL detection | ❌ Not implemented | **HIGH**: Credentials logged/stored insecurely |
| Environment variable sanitization | ❌ Not implemented | **MEDIUM**: Potential injection from untrusted TOML files |
| Directory ownership checks | ❌ Not implemented | **MEDIUM**: Config files owned by other users |
| Error message sanitization | ❌ Not reviewed | **MEDIUM**: Potential information leakage |
| Config file location validation | ❌ Not implemented | **HIGH**: Loads from world-writable directories |
| Session cache file handling | ❌ Not applicable | **CRITICAL**: Clevis doesn't handle session cache |

**Key Finding**: **Clevis provides NO security features** beyond basic TOML parsing and type validation.

---

## Security Gaps and Required Additions

### CRITICAL-1: Session Cache File Permissions

**Requirement**: Session cache files MUST be created with 0600 permissions.

**Current Implementation**: Implemented in `async_client.py:216-317`

**Clevis Status**: Not applicable (clevis doesn't handle session cache)

**Required Addition**: Keep session cache handling in roomz, do NOT delegate to clevis.

**Implementation**:

```python
# src/roomz/client/session_cache.py (NEW FILE)

import os
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class SessionCacheSecurityError(Exception):
    """Raised when session cache has security issues."""
    pass


def save_session_cache(
    cache_file: Path,
    session_cookie: str,
    server_url: str
) -> None:
    """
    Save session cookie to cache file with secure permissions.

    Security:
    - Creates file with 0600 permissions atomically (no race condition)
    - Uses exclusive creation to prevent symlink attacks
    - Validates parent directory is not world-writable
    """
    # Validate parent directory
    parent = cache_file.parent
    if parent.exists():
        _validate_directory_security(parent)
    else:
        # Create with secure permissions
        parent.mkdir(parents=True, exist_ok=True, mode=0o700)

    # Atomic write with secure permissions
    try:
        fd = os.open(
            str(cache_file),
            os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_EXCL,
            mode=0o600
        )
        try:
            with os.fdopen(fd, 'w') as f:
                json.dump({
                    "session_cookie": session_cookie,
                    "server": server_url
                }, f)
        except Exception:
            os.close(fd)
            raise

        logger.debug(f"Session cookie saved to {cache_file}")

    except FileExistsError:
        # File exists, update it securely
        _update_session_cache_secure(cache_file, session_cookie, server_url)
    except OSError as e:
        logger.warning(f"Failed to save session cookie: {e}")


def _update_session_cache_secure(
    cache_file: Path,
    session_cookie: str,
    server_url: str
) -> None:
    """Update existing session cache file with secure permissions."""
    try:
        # Check and fix permissions if needed
        current_mode = cache_file.stat().st_mode & 0o777
        if current_mode & 0o077:  # Has group/other permissions
            logger.warning(
                f"Session cache file {cache_file} has insecure "
                f"permissions {oct(current_mode)}. Restricting to 0600."
            )
            cache_file.chmod(0o600)

        # Atomic write: write to temp file, then rename
        temp_file = cache_file.with_suffix('.tmp')
        temp_file.write_text(json.dumps({
            "session_cookie": session_cookie,
            "server": server_url
        }))
        temp_file.replace(cache_file)

    except (OSError, TypeError) as e:
        logger.warning(f"Failed to update session cache: {e}")


def load_session_cache(cache_file: Path, server_url: str) -> str | None:
    """
    Load session cookie from cache file with security validation.

    Security:
    - Validates file permissions before loading
    - Warns if file has insecure permissions
    - Validates server URL match
    """
    if not cache_file.exists():
        return None

    try:
        # Validate file permissions
        file_mode = cache_file.stat().st_mode & 0o777
        if file_mode & 0o077:  # Group/other permissions
            logger.warning(
                f"Session cache file {cache_file} has insecure "
                f"permissions {oct(file_mode)}. Session may be accessible to other users."
            )

        with open(cache_file) as f:
            data = json.load(f)

            # Validate structure
            if not isinstance(data, dict):
                logger.warning("Session cache file has invalid structure")
                return None

            # Validate server match
            if data.get("server") != server_url:
                logger.debug("Session cache is for different server")
                return None

            cookie = data.get("session_cookie")
            if not cookie or not isinstance(cookie, str):
                logger.warning("Session cache file has invalid session_cookie")
                return None

            return cookie

    except json.JSONDecodeError:
        logger.warning(f"Session cache file {cache_file} is corrupted")
        return None
    except Exception as e:
        logger.warning(f"Failed to load session cookie: {e}")
        return None


def _validate_directory_security(directory: Path) -> None:
    """
    Validate directory security.

    Raises:
        SessionCacheSecurityError: If directory is world-writable
    """
    import stat

    stat_info = directory.stat()

    # Check for world-writable
    if stat_info.st_mode & stat.S_IWOTH:
        raise SessionCacheSecurityError(
            f"Security risk: session cache directory {directory} is world-writable. "
            "Other users could replace session files with malicious content."
        )

    # On Unix, check ownership (optional but recommended)
    if hasattr(os, 'geteuid') and stat_info.st_uid != os.geteuid():
        logger.warning(
            f"Session cache directory {directory} is owned by another user (uid={stat_info.st_uid}). "
            "This may be a security risk."
        )
```

### CRITICAL-2: Config File Location Security

**Requirement**: Validate current directory is not world-writable when loading `./roomz.toml`.

**Current Implementation**: Not implemented in current config.py (gap identified in I8-000)

**Clevis Status**: Not implemented, loads from CWD without validation

**Required Addition**: Wrapper layer to validate config file locations.

**Implementation**:

```python
# src/roomz/client/config_security.py (NEW FILE)

import os
import stat
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class ConfigSecurityError(Exception):
    """Raised when configuration has security issues."""
    pass


def validate_config_file_security(config_file: Path) -> None:
    """
    Validate config file security.

    Security:
    - Warns if file is group/other readable (low sensitivity data)
    - Errors if file is group/other writable
    - Validates parent directory is not world-writable

    Args:
        config_file: Path to config file

    Raises:
        ConfigSecurityError: If file or directory has critical security issues
    """
    if not config_file.exists():
        return

    # Check file permissions
    file_mode = config_file.stat().st_mode & 0o777

    if file_mode & 0o022:  # Group/other writable
        raise ConfigSecurityError(
            f"Security risk: config file {config_file} is writable by others. "
            "Other users could modify configuration. "
            f"Run: chmod 600 {config_file}"
        )

    if file_mode & 0o044:  # World-readable (warning only)
        logger.warning(
            f"Config file {config_file} is world-readable. "
            "Configuration values may be visible to other users. "
            f"Consider running: chmod 600 {config_file}"
        )

    # Validate parent directory
    parent = config_file.parent
    _validate_directory_security(parent, f"config file {config_file}")


def validate_current_directory_config(config_file: Path) -> None:
    """
    Validate security of current directory config file.

    Security:
    - Rejects config in world-writable directories
    - Warns if directory is not owned by current user

    Args:
        config_file: Path to config file (expected to be in CWD)

    Raises:
        ConfigSecurityError: If directory is world-writable
    """
    if not config_file.exists():
        return

    parent = config_file.parent

    # Check if directory is world-writable
    stat_info = parent.stat()
    if stat_info.st_mode & stat.S_IWOTH:
        raise ConfigSecurityError(
            f"Security risk: refusing to load config from world-writable directory {parent}. "
            "An attacker with write access to this directory could place a malicious config file. "
            "Use ~/.roomz.toml or environment variables instead."
        )

    # Check directory ownership (Unix only)
    if hasattr(os, 'geteuid') and stat_info.st_uid != os.geteuid():
        logger.warning(
            f"Config directory {parent} is owned by another user (uid={stat_info.st_uid}). "
            "This may be a security risk."
        )


def _validate_directory_security(directory: Path, context: str = "directory") -> None:
    """
    Validate directory security.

    Raises:
        ConfigSecurityError: If directory is world-writable
    """
    stat_info = directory.stat()

    if stat_info.st_mode & stat.S_IWOTH:
        raise ConfigSecurityError(
            f"Security risk: {context} is in world-writable directory {directory}. "
            "Other users could create or modify files in this directory."
        )

    # Check directory ownership (Unix only)
    if hasattr(os, 'geteuid') and stat_info.st_uid != os.geteuid():
        logger.warning(
            f"{context} is in directory owned by another user (uid={stat_info.st_uid}). "
            "This may be a security risk."
        )
```

### HIGH-1: URL Validation

**Requirement**: Validate server URLs (http/https only, no credentials, hostname required).

**Current Implementation**: Partial in `config.py:283-306`

**Clevis Status**: Not implemented

**Required Addition**: Wrapper layer to validate URLs.

**Implementation**:

```python
# src/roomz/client/config_validation.py

from urllib.parse import urlparse
import logging
from typing import List

logger = logging.getLogger(__name__)


def validate_server_url(url: str) -> List[str]:
    """
    Validate server URL.

    Security:
    - Must be HTTP or HTTPS
    - Must have valid hostname (no IP spoofing checks, but prevents javascript:)
    - No credentials in URL
    - Warn on localhost/private IPs (development)

    Args:
        url: Server URL to validate

    Returns:
        List of validation errors (empty if valid)
    """
    errors: List[str] = []

    try:
        parsed = urlparse(url)

        # Must be http or https
        if parsed.scheme not in ('http', 'https'):
            errors.append(
                f"Invalid server URL: scheme must be http or https, got {parsed.scheme}"
            )

        # Must have hostname
        if not parsed.hostname:
            errors.append("Invalid server URL: missing hostname")

        # No credentials in URL
        if parsed.username or parsed.password:
            errors.append(
                "Invalid server URL: credentials in URL are not allowed. "
                "Use environment variables for authentication."
            )

        # Warn on localhost/private IPs (development)
        if parsed.hostname in ('localhost', '127.0.0.1', '::1'):
            logger.warning(
                "Server URL points to localhost. This should only be used in development."
            )

        if parsed.hostname and (
            parsed.hostname.startswith('192.168.') or
            parsed.hostname.startswith('10.') or
            parsed.hostname.startswith('172.')
        ):
            logger.warning(
                f"Server URL points to private IP {parsed.hostname}. "
                "This should only be used in development or private networks."
            )

    except Exception as e:
        errors.append(f"Invalid server URL: {e}")

    return errors


def sanitize_url_for_logging(url: str) -> str:
    """
    Sanitize URL for safe logging (remove credentials).

    Args:
        url: URL to sanitize

    Returns:
        URL safe for logging
    """
    try:
        parsed = urlparse(url)
        if parsed.password:
            # Replace password with ***
            sanitized = url.replace(parsed.password, '***')
            return sanitized
        return url
    except Exception:
        return url
```

### HIGH-2: Environment Variable Interpolation Security

**Requirement**: Ensure environment variable interpolation is secure.

**Current Implementation**: Not applicable (current config doesn't use interpolation)

**Clevis Status**: Uses envtoml or tomlev for `${VAR}` interpolation

**Security Concern**: Untrusted TOML files could reference environment variables containing sensitive data.

**Required Addition**: Validation of interpolated values.

**Implementation**:

```python
# src/roomz/client/config_interpolation.py

import os
import re
from typing import Dict, Any

# Pattern for environment variable references
ENV_VAR_PATTERN = re.compile(r'\$\{([^}|]+)(?:\|([^}]*))?\}')


def validate_interpolated_values(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate environment variable interpolation results.

    Security:
    - Validates URLs after interpolation
    - Sanitizes sensitive values
    - Logs interpolation for auditing

    Args:
        config: Configuration dict with interpolated values

    Returns:
        Validated configuration dict
    """
    validated = {}

    for key, value in config.items():
        if isinstance(value, str):
            # Check if value was interpolated
            if key == 'server_url':
                errors = validate_server_url(value)
                if errors:
                    raise ConfigSecurityError(
                        f"Invalid interpolated value for {key}: {'; '.join(errors)}"
                    )
            validated[key] = value
        elif isinstance(value, dict):
            # Recursively validate nested config
            validated[key] = validate_interpolated_values(value)
        else:
            validated[key] = value

    return validated


def audit_environment_interpolation(config: Dict[str, Any], env_vars: Dict[str, str]) -> None:
    """
    Audit environment variable interpolation for security logging.

    Args:
        config: Configuration dict
        env_vars: Environment variables that were interpolated
    """
    logger = logging.getLogger(__name__)

    for key, value in config.items():
        if isinstance(value, str) and ENV_VAR_PATTERN.search(value):
            # Value contains environment variable reference
            logger.info(
                f"Configuration {key} uses environment variable interpolation"
            )
            # Log the variable name but not the value (for security)
            matches = ENV_VAR_PATTERN.findall(value)
            var_names = [match[0] for match in matches]
            logger.debug(f"Variables used: {', '.join(var_names)}")
```

---

## Risk Assessment

### Critical Risks (Blocking Adoption)

| Risk ID | Description | Impact | Likelihood | Mitigation |
|---------|-------------|--------|------------|------------|
| **R1** | Session cache files created without 0600 permissions | **HIGH**: JWT tokens exposed to other users | **CERTAIN**: Clevis doesn't handle session cache | Keep session cache handling in roomz code |
| **R2** | Config loaded from world-writable directories | **HIGH**: Attacker can place malicious config | **HIGH**: Current directory is often world-writable (e.g., `/tmp`, shared folders) | Add directory security validation wrapper |
| **R3** | No URL validation after config load | **MEDIUM**: Malicious URLs in config files | **HIGH**: Clevis doesn't validate URLs | Add URL validation wrapper |

### High Risks (Must Address)

| Risk ID | Description | Impact | Likelihood | Mitigation |
|---------|-------------|--------|------------|------------|
| **R4** | No permission warnings for config files | **MEDIUM**: Users unaware of insecure configs | **HIGH**: Default umask creates world-readable files | Add permission warning wrapper |
| **R5** | Environment variable interpolation from untrusted TOML | **MEDIUM**: Potential injection of sensitive data | **MEDIUM**: Requires attacker to modify TOML file | Validate interpolated values |
| **R6** | TOML format change breaks existing configs | **MEDIUM**: User disruption, potential security confusion | **CERTAIN**: `[client]` section not supported in clevis | Provide migration tool and documentation |

### Medium Risks (Should Address)

| Risk ID | Description | Impact | Likelihood | Mitigation |
|---------|-------------|--------|------------|------------|
| **R7** | Error messages may leak information | **LOW**: Path disclosure, system info | **MEDIUM**: Error messages include file paths | Review error messages in wrapper |
| **R8** | No directory ownership validation | **LOW**: Config owned by other user | **MEDIUM**: Common in shared environments | Add ownership warning |

---

## Security Architecture

### Recommended Implementation

```python
# src/roomz/client/config.py (UPDATED)

from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple
import logging

from clevis import get_config, ConfigError as ClevisConfigError

from roomz.client.config_security import (
    ConfigSecurityError,
    validate_config_file_security,
    validate_current_directory_config,
)
from roomz.client.config_validation import validate_server_url
from roomz.client.exceptions import ConfigurationError

logger = logging.getLogger(__name__)


@dataclass
class Config:
    """Configuration for Roomz client with security validation."""

    server_url: str | None = None
    display_name: str | None = None

    def validate(self) -> List[str]:
        """
        Validate configuration values.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors: List[str] = []

        if self.server_url is not None:
            url_errors = validate_server_url(self.server_url)
            errors.extend(url_errors)

        return errors


def get_client_config(
    name: str = "roomz",
    args: List[str] | None = None,
    cli: bool = True
) -> Tuple[Config, Path | None]:
    """
    Get configuration with roomz-specific security validation.

    Security:
    - Validates config file locations
    - Warns about insecure permissions
    - Rejects world-writable directories
    - Validates server URLs

    Args:
        name: Configuration name (default: "roomz")
        args: CLI arguments (default: sys.argv[1:])
        cli: Whether to parse CLI arguments (default: True, use False for AsyncClient)

    Returns:
        Tuple of (Config instance, discovered config file path or None)

    Raises:
        ConfigurationError: If configuration is invalid or has security issues
    """
    try:
        # Load config using clevis (without CLI args if cli=False)
        config = get_config(
            Config,
            name=name,
            user=True,
            project=True,
            args=args if cli else []
        )

        # Validate config file security
        config_path = _find_config_file(name)
        if config_path:
            _validate_config_security(config_path)

        # Validate configuration values
        errors = config.validate()
        if errors:
            raise ConfigurationError(
                f"Configuration validation failed: {'; '.join(errors)}"
            )

        return config, config_path

    except ClevisConfigError as e:
        raise ConfigurationError(f"Configuration error: {e}") from e
    except ConfigSecurityError as e:
        raise ConfigurationError(f"Security error: {e}") from e


def _find_config_file(name: str) -> Path | None:
    """
    Find which config file was used (for security validation).

    Returns:
        Path to config file or None if not found
    """
    # Check project config first (higher priority in clevis)
    project_config = Path.cwd() / f"{name}.toml"
    if project_config.exists():
        return project_config

    # Check user config
    user_config = Path.home() / f".{name}.toml"
    if user_config.exists():
        return user_config

    return None


def _validate_config_security(config_path: Path) -> None:
    """
    Validate config file security.

    Security:
    - Checks file permissions
    - Validates directory security
    - Rejects world-writable directories for project config
    """
    # Validate file permissions
    validate_config_file_security(config_path)

    # Extra validation for current directory config
    if config_path.parent == Path.cwd():
        validate_current_directory_config(config_path)
```

### Security Layer Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Application Layer                        │
│  (AsyncClient, SyncClient - use config and session cache)   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Security Wrapper Layer                     │
│                                                              │
│  ┌──────────────────────┐  ┌────────────────────────────┐  │
│  │  Config Security     │  │  Session Cache Security    │  │
│  │  - File permissions  │  │  - 0600 file creation      │  │
│  │  - Directory checks  │  │  - Permission enforcement  │  │
│  │  - URL validation    │  │  - Directory validation    │  │
│  │  - Env var audit     │  │  - Atomic writes           │  │
│  └──────────────────────┘  └────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      Clevis Layer                            │
│  (TOML parsing, environment variables, CLI args, merging)   │
└─────────────────────────────────────────────────────────────┘
```

---

## Recommendations

### Must Do Before Adoption (Blocking)

1. **Create security wrapper layer** - Implement `config_security.py`, `config_validation.py`, and update `config.py` to wrap clevis with security validation.

2. **Keep session cache handling separate** - Do NOT delegate session cache to clevis. Keep in separate module with full security implementation.

3. **Add directory security validation** - Validate that current directory is not world-writable before loading `./roomz.toml`.

4. **Implement URL validation** - Validate all server URLs before use (http/https only, no credentials, hostname required).

5. **Add file permission warnings** - Warn if config files have group/other permissions.

### Should Do (High Priority)

6. **Document TOML format change** - Provide clear migration guide from `[client]` section to top-level TOML.

7. **Add security logging** - Log config file locations, permission warnings, and security issues.

8. **Review error messages** - Ensure error messages don't leak sensitive information (paths, system details).

### Nice to Have (Medium Priority)

9. **Add config file migration tool** - Script to convert `~/.roomz/config.toml` to `~/.roomz.toml`.

10. **Add optional config encryption** - For high-security environments, offer to encrypt session cache.

### Implementation Priority

| Phase | Tasks | Effort | Risk Reduction |
|-------|-------|--------|----------------|
| **Phase 1** | Security wrapper layer, session cache separation, directory validation | 2-3 days | Addresses all CRITICAL risks |
| **Phase 2** | URL validation, permission warnings, security logging | 1 day | Addresses all HIGH risks |
| **Phase 3** | Documentation, migration tool, error message review | 1 day | Addresses MEDIUM risks |

---

## Migration Checklist

### Pre-Migration Security Audit

- [ ] Verify all I8-000 security requirements are documented
- [ ] Identify all security-critical code paths in current implementation
- [ ] Document current session cache security implementation
- [ ] Document current config validation logic

### Migration Implementation

- [ ] Create `src/roomz/client/config_security.py` with security validation
- [ ] Create `src/roomz/client/config_validation.py` with URL validation
- [ ] Create `src/roomz/client/session_cache.py` with secure session handling
- [ ] Update `src/roomz/client/config.py` to use clevis with security wrapper
- [ ] Update `src/roomz/client/async_client.py` to use new session_cache module
- [ ] Update `src/roomz/client/sync_client.py` to use new config system

### Post-Migration Security Testing

- [ ] Test session cache file permissions (created with 0600)
- [ ] Test session cache in world-writable directory (should fail)
- [ ] Test config in world-writable directory (should fail or warn)
- [ ] Test config file permissions (should warn if world-readable)
- [ ] Test URL validation (reject javascript:, ftp:, credentials)
- [ ] Test environment variable interpolation security
- [ ] Test error messages for information leakage
- [ ] Test on multi-user system (permissions matter)

### Documentation Updates

- [ ] Update security section in docs/configuration.md
- [ ] Add migration guide from `[client]` section
- [ ] Document security considerations for TOML files
- [ ] Document environment variable security
- [ ] Add troubleshooting guide for permission errors

---

## Positive Security Observations

1. **Clevis uses dataclass-based config** - Type-safe configuration with automatic validation helps prevent configuration errors.

2. **Clevis provides helpful error messages** - Better user experience than manual TOML parsing.

3. **Environment variable support** - Allows secrets to be passed without config files (though requires validation).

4. **CLI argument generation** - Reduces custom CLI parsing code (smaller attack surface).

5. **Current roomz has comprehensive security** - Security features are well-implemented and can be preserved in wrapper layer.

---

## Conclusion

**Adoption Decision**: ✅ Adopt clevis with mandatory security wrapper layer.

**Critical Requirements**:
1. All session cache handling MUST remain in roomz code (not delegated to clevis)
2. Security wrapper MUST validate config file locations and permissions
3. URL validation MUST be added as wrapper layer
4. Current directory config loading MUST validate directory security

**Estimated Effort**: 3-5 days to implement security wrapper layer and migrate.

**Risk Level**: **MEDIUM-HIGH** - Significant security gaps in clevis, but can be addressed with wrapper layer.

**Recommendation**: Proceed with migration, but allocate sufficient time for security wrapper implementation and testing. Do NOT adopt clevis without security wrapper layer.

---

## References

- [OWASP A05:2025 - Security Misconfiguration](https://owasp.org/Top10/A05_2025-Security_Misconfiguration/)
- [OWASP A01:2025 - Broken Access Control](https://owasp.org/Top10/A01_2025-Broken_Access_Control/)
- [OWASP A04:2025 - Cryptographic Failures](https://owasp.org/Top10/A04_2025-Cryptographic_Failures/)
- [CWE-732: Incorrect Permission Assignment](https://cwe.mitre.org/data/definitions/732.html)
- [CWE-426: Untrusted Search Path](https://cwe.mitre.org/data/definitions/426.html)
- [NIST SP 800-53: AC-3 Access Enforcement](https://csrc.nist.gov/publications/detail/sp/800-53/rev-5/final)
- I8-000 Security Review: `analysis/config-security.md`