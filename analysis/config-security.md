# Security Review: Configuration System

**Task**: I8-000 - Generalized Configuration Pattern Security Review
**Date**: 2026-05-26
**Analyst**: Security Engineer Agent
**Status**: Pre-Implementation Security Review

## Executive Summary

This security review analyzes the configuration system for the roomz Python client library, focusing on file handling, sensitive data protection, and the planned generalized configuration pattern. The review identifies security concerns with session cache file permissions, config file location security, and recommendations for the upcoming I8-000 implementation.

**Key Findings**:
- Session cache files contain JWT tokens (sensitive) but lack permission enforcement
- Planned config loading from current directory (`./roomz.toml`) creates security risk
- No file permission validation or warnings for config files
- Session cache files expose server URLs alongside authentication tokens

**Risk Level**: **MEDIUM-HIGH** - Requires mitigation before I8-000 implementation

---

## Security Findings Classification

| Finding | Classification | Action |
|---------|---------------|--------|
| Session cache file permissions | Blocking | Must enforce 0600 permissions |
| Config file location attack (./roomz.toml) | Blocking | Must warn or reject world-writable directories |
| No permission warnings | Related | Add security warnings for insecure permissions |
| Session file content exposure | Related | Consider encrypting session cache |
| Error message information leakage | New | Review logging for sensitive data |
| Server URL validation | New | Add URL scheme validation |

---

## Current Configuration System Analysis

### Configuration Files

**Current State** (from `async_client.py`):

```python
# Display name config location
config_file = Path.home() / ".roomz" / "config.toml"

# Session cache location (user-specified, typically ~/.roomz/session.json)
self._session_cache_file = Path(session_cache_file) if session_cache_file else None
```

**Planned State** (from TODO.md I8-000):

```markdown
Priority Order:
  1. Explicit parameter (e.g., AsyncClient(server_url=...))
  2. Environment variable (e.g., ROOMZ_SERVER_URL, ROOMZ_DISPLAY_NAME)
  3. ./roomz.toml in current working directory (no leading dot)
  4. ~/.roomz.toml in home directory (no folder)
```

### Data Stored in Config Files

| Config Item | Sensitivity | Current Location | Planned Location |
|-------------|-------------|-------------------|------------------|
| `display_name` | Low | `~/.roomz/config.toml` | `./roomz.toml`, `~/.roomz.toml` |
| `server_url` | Low-Medium | Not stored | `./roomz.toml`, `~/.roomz.toml` |
| `session_cache_file` | High (JWT token) | User-specified | Same (user-specified) |

### Session Cache File Structure

```json
{
  "session_cookie": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "server": "http://localhost:8000"
}
```

---

## Critical Findings (CVSS 9.0-10.0)

None identified. Session cache file permissions are HIGH severity.

---

## High Findings (CVSS 7.0-8.9)

### HIGH-1: Session Cache File Permissions

**OWASP Category**: A05:2025 - Security Misconfiguration
**STRIDE**: Information Disclosure
**CVSS Score**: 7.5 (High)

**Description**: Session cache files contain JWT tokens (authentication credentials) but are created without explicit permission restrictions. On multi-user systems, this exposes authentication tokens to other users.

**Impact**:
- JWT tokens visible to other users on shared systems
- Token theft enables full account compromise for token lifetime (up to 30 days)
- Server URL exposed alongside token
- No file permission enforcement on write

**Current Implementation**:

```python
# src/roomz/client/async_client.py - Lines 203-213
def _save_session_cookie(self, cookie_value: str) -> None:
  """Save session cookie to cache file."""
  if not self._session_cache_file:
    return

  try:
    self._session_cache_file.parent.mkdir(parents=True, exist_ok=True)
    with open(self._session_cache_file, "w") as f:
      json.dump({"session_cookie": cookie_value, "server": self._server_url}, f)
  except Exception as e:
    logger.warning(f"Failed to save session cookie: {e}")
```

**Security Issues**:
1. File created with default umask (typically 0644 - world-readable)
2. Parent directory created with default permissions
3. No validation of existing file permissions
4. No warning if file is world-readable

**Remediation**:

```python
import os
import stat
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

def _save_session_cookie(self, cookie_value: str) -> None:
    """
    Save session cookie to cache file with secure permissions.

    Security:
    - Creates file with 0600 permissions (owner read/write only)
    - Creates directory with 0700 permissions (owner access only)
    - Warns if file permissions are insecure
    - Validates parent directory is not world-writable
    """
    if not self._session_cache_file:
        return

    try:
        # Validate parent directory security
        parent = self._session_cache_file.parent
        if parent.exists():
            self._validate_directory_security(parent)
        else:
            # Create with secure permissions
            parent.mkdir(parents=True, exist_ok=True, mode=0o700)

        # Write with secure permissions
        # Use exclusive creation to prevent symlink attacks
        fd = os.open(
            self._session_cache_file,
            os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_EXCL,
            mode=0o600
        )
        try:
            with os.fdopen(fd, 'w') as f:
                json.dump({
                    "session_cookie": cookie_value,
                    "server": self._server_url
                }, f)
        except Exception:
            os.close(fd)
            raise

        logger.debug(f"Session cookie saved to {self._session_cache_file}")

    except FileExistsError:
        # File exists, update it securely
        self._update_session_cookie_secure(cookie_value)
    except Exception as e:
        logger.warning(f"Failed to save session cookie: {e}")

def _update_session_cookie_secure(self, cookie_value: str) -> None:
    """Update existing session cookie file securely."""
    try:
        # Check and fix permissions if needed
        current_mode = self._session_cache_file.stat().st_mode
        if current_mode & 0o077:  # Check for group/other permissions
            logger.warning(
                f"Session cache file {self._session_cache_file} has insecure "
                f"permissions {oct(current_mode)}. Restricting to 0600."
            )
            self._session_cache_file.chmod(0o600)

        # Atomic write: write to temp file, then rename
        temp_file = self._session_cache_file.with_suffix('.tmp')
        temp_file.write_text(json.dumps({
            "session_cookie": cookie_value,
            "server": self._server_url
        }))
        temp_file.replace(self._session_cache_file)

    except Exception as e:
        logger.warning(f"Failed to update session cookie: {e}")

def _validate_directory_security(self, directory: Path) -> None:
    """
    Validate directory security.

    Raises SecurityError if:
    - Directory is world-writable
    - Directory is not owned by current user (on Unix)
    """
    stat_info = directory.stat()

    # Check for world-writable
    if stat_info.st_mode & stat.S_IWOTH:
        raise SecurityError(
            f"Security risk: session cache directory {directory} is world-writable. "
            "Other users could replace session files with malicious content."
        )

    # On Unix, check ownership (optional but recommended)
    if hasattr(os, 'geteuid') and stat_info.st_uid != os.geteuid():
        logger.warning(
            f"Session cache directory {directory} is owned by another user (uid={stat_info.st_uid}). "
            "This may be a security risk."
        )

def _load_session_cookie(self) -> str | None:
    """
    Load session cookie from cache file with security validation.

    Security:
    - Validates file permissions before loading
    - Warns if file is world-readable
    - Validates content structure
    """
    if not self._session_cache_file or not self._session_cache_file.exists():
        return None

    try:
        # Validate file permissions
        file_mode = self._session_cache_file.stat().st_mode
        if file_mode & 0o077:  # Group/other permissions
            logger.warning(
                f"Session cache file {self._session_cache_file} has insecure "
                f"permissions {oct(file_mode)}. Session may be accessible to other users. "
                "Consider running: chmod 600 <file>"
            )

        with open(self._session_cache_file) as f:
            data = json.load(f)

            # Validate structure
            if not isinstance(data, dict):
                logger.warning("Session cache file has invalid structure")
                return None

            # Validate server match
            if data.get("server") != self._server_url:
                logger.debug("Session cache is for different server")
                return None

            cookie = data.get("session_cookie")
            if not cookie or not isinstance(cookie, str):
                logger.warning("Session cache file has invalid session_cookie")
                return None

            return cookie

    except json.JSONDecodeError:
        logger.warning(f"Session cache file {self._session_cache_file} is corrupted")
        return None
    except Exception as e:
        logger.warning(f"Failed to load session cookie: {e}")
        return None


class SecurityError(Exception):
    """Raised when a security issue is detected."""
    pass
```

**File Permission Enforcement**:

```python
# Security module: file_permissions.py
import os
import stat
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)


def ensure_file_permissions(
    file_path: Path,
    expected_mode: int = 0o600,
    fix: bool = True
) -> bool:
    """
    Ensure file has secure permissions.

    Args:
        file_path: Path to file
        expected_mode: Expected file permissions (default: 0600)
        fix: If True, fix permissions if insecure

    Returns:
        True if permissions are secure, False otherwise
    """
    if not file_path.exists():
        return True

    current_mode = file_path.stat().st_mode & 0o777

    # Check for group/other permissions
    if current_mode & 0o077:
        if fix:
            logger.warning(
                f"Fixing insecure permissions on {file_path}: "
                f"{oct(current_mode)} -> {oct(expected_mode)}"
            )
            file_path.chmod(expected_mode)
            return True
        else:
            logger.error(
                f"Insecure permissions on {file_path}: {oct(current_mode)}. "
                f"Expected {oct(expected_mode)}. Run: chmod {oct(expected_mode)[2:]} {file_path}"
            )
            return False

    return True


def check_file_insecure(file_path: Path) -> Optional[str]:
    """
    Check if file has insecure permissions.

    Returns:
        Warning message if insecure, None if secure
    """
    if not file_path.exists():
        return None

    current_mode = file_path.stat().st_mode & 0o777

    if current_mode & 0o077:
        return (
            f"File {file_path} has insecure permissions {oct(current_mode)}. "
            f"Other users can read this file. Run: chmod 600 {file_path}"
        )

    return None
```

**Reference**:
- [OWASP A05:2025 - Security Misconfiguration](https://owasp.org/Top10/A05_2025-Security_Misconfiguration/)
- [CWE-732: Incorrect Permission Assignment](https://cwe.mitre.org/data/definitions/732.html)
- [NIST SP 800-53: AC-3 Access Enforcement](https://csrc.nist.gov/publications/detail/sp/800-53/rev-5/final)

---

### HIGH-2: Config File Location Attack (./roomz.toml)

**OWASP Category**: A05:2025 - Security Misconfiguration
**STRIDE**: Tampering, Elevation of Privilege
**CVSS Score**: 7.8 (High)

**Description**: The planned I8-000 implementation includes loading config from `./roomz.toml` (current directory). This creates a significant security vulnerability: an attacker with write access to a shared directory can place a malicious config file that will be loaded by any user running roomz from that directory.

**Attack Scenario**:

```
# Attacker on shared system (e.g., shared hosting, CI/CD runner)
cd /shared/project
cat > roomz.toml << EOF
[client]
server_url = "https://attacker-server.com"
display_name = "Compromised"
EOF

# Victim runs roomz from /shared/project
# Client connects to attacker's server
# Attacker captures authentication tokens
```

**Impact**:
- Server URL hijacking: Connect to attacker-controlled server
- Credential capture: Authentication tokens sent to attacker
- Phishing: Display name could show misleading information
- Privilege escalation: If victim has higher privileges

**Directory Security Analysis**:

| Location | Risk Level | Attack Vector |
|----------|------------|---------------|
| `./roomz.toml` (CWD) | **HIGH** | Shared directories, malicious repos, CI/CD tampering |
| `~/.roomz.toml` (Home) | **LOW** | Only if home directory compromised |
| `~/.roomz/config.toml` | **LOW** | Only if home directory compromised |
| Environment vars | **MEDIUM** | Process environment exposure |

**Remediation**:

**Option A: Remove Current Directory Loading (Recommended)**

```python
# Remove ./roomz.toml from priority order
# Priority:
#   1. Explicit parameter
#   2. Environment variable
#   3. ~/.roomz.toml (home directory only)
```

**Option B: Validate Directory Security**

```python
def _load_config_from_cwd(self) -> dict | None:
    """
    Load config from current directory with security validation.

    Security:
    - Rejects config in world-writable directories
    - Warns if directory is not owned by current user
    - Validates file permissions
    """
    config_file = Path.cwd() / "roomz.toml"

    if not config_file.exists():
        return None

    try:
        # Validate directory security
        self._validate_directory_security(config_file.parent)

        # Validate file permissions
        file_mode = config_file.stat().st_mode
        if file_mode & 0o077:
            logger.warning(
                f"Config file {config_file} has insecure permissions. "
                "Other users could modify this file. Ignoring."
            )
            return None

        # Load config
        return self._parse_config_file(config_file)

    except SecurityError as e:
        logger.error(f"Security validation failed for {config_file}: {e}")
        return None
    except Exception as e:
        logger.warning(f"Failed to load config from {config_file}: {e}")
        return None
```

**Option C: Warning Banner (If Current Directory Must Be Supported)**

```python
def _load_config_from_cwd(self) -> dict | None:
    """Load config from current directory with prominent security warning."""
    config_file = Path.cwd() / "roomz.toml"

    if not config_file.exists():
        return None

    # Prominent warning
    logger.warning(
        "SECURITY WARNING: Loading config from current directory. "
        "Only use this in trusted directories. "
        "Attacker with write access to current directory can hijack config. "
        "Consider using ~/.roomz.toml or environment variables instead."
    )

    # Continue with Option B validation...
```

**Recommendation**: Use **Option A** (remove current directory loading). The convenience does not justify the security risk. Users who need directory-specific config can use environment variables or explicit parameters.

**Reference**:
- [OWASP A05:2025 - Security Misconfiguration](https://owasp.org/Top10/A05_2025-Security_Misconfiguration/)
- [CWE-426: Untrusted Search Path](https://cwe.mitre.org/data/definitions/426.html)
- [CWE-427: Uncontrolled Search Path Element](https://cwe.mitre.org/data/definitions/427.html)

---

## Medium Findings (CVSS 4.0-6.9)

### MEDIUM-1: No Permission Warnings for Config Files

**OWASP Category**: A05:2025 - Security Misconfiguration
**STRIDE**: Information Disclosure
**CVSS Score**: 5.5 (Medium)

**Description**: The `_load_display_name_from_config` function reads config files without checking file permissions. If config files contain sensitive values in the future, they may be exposed to other users.

**Current Implementation**:

```python
# src/roomz/client/async_client.py - Lines 43-68
config_file = Path.home() / ".roomz" / "config.toml"
if config_file.exists():
  try:
    content = config_file.read_text()
    # ... parse config ...
```

**Remediation**:

```python
def _load_display_name_from_config() -> str | None:
    """
    Load display name from environment variable or config file.

    Security:
    - Checks config file permissions
    - Warns if file is group/other readable
    - Validates file is owned by current user (on Unix)
    """
    # Check environment variable first
    env_name = os.environ.get("ROOMZ_DISPLAY_NAME")
    if env_name:
        return env_name.strip() or None

    # Check config file
    config_file = Path.home() / ".roomz" / "config.toml"
    if not config_file.exists():
        return None

    try:
        # Validate directory security
        _validate_config_directory_security(config_file.parent)

        # Check file permissions
        file_mode = config_file.stat().st_mode
        if file_mode & 0o077:  # Group/other readable
            logger.warning(
                f"Config file {config_file} has insecure permissions {oct(file_mode)}. "
                "Consider running: chmod 600 <file>"
            )

        # Parse config
        content = config_file.read_text()
        # ... rest of parsing ...

    except Exception as e:
        logger.warning(f"Failed to load display name from config: {e}")

    return None


def _validate_config_directory_security(directory: Path) -> None:
    """Validate config directory security."""
    if not directory.exists():
        return

    stat_info = directory.stat()

    # Check for world-writable (critical)
    if stat_info.st_mode & stat.S_IWOTH:
        raise SecurityError(
            f"Security risk: config directory {directory} is world-writable. "
            "Other users could modify config files."
        )

    # Check for world-readable (warning)
    if stat_info.st_mode & stat.S_IROTH:
        logger.warning(
            f"Config directory {directory} is world-readable. "
            "Config values may be visible to other users."
        )
```

**Reference**:
- [OWASP A05:2025 - Security Misconfiguration](https://owasp.org/Top10/A05_2025-Security_Misconfiguration/)
- [CWE-732: Incorrect Permission Assignment](https://cwe.mitre.org/data/definitions/732.html)

---

### MEDIUM-2: Session File Content Exposure

**OWASP Category**: A04:2025 - Cryptographic Failures
**STRIDE**: Information Disclosure
**CVSS Score**: 5.3 (Medium)

**Description**: Session cache file stores JWT token and server URL in plaintext. If file is compromised (via permissions attack or backup), attacker gains both authentication token and target server.

**Current Storage**:

```json
{
  "session_cookie": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "server": "http://localhost:8000"
}
```

**Remediation Options**:

**Option A: Encrypt Session Cache (Recommended for High-Security Environments)**

```python
from cryptography.fernet import Fernet
from cryptography.fernet import InvalidToken
import base64
import os

class SessionCacheEncryption:
    """Encrypt session cache files."""

    def __init__(self):
        self._key: bytes | None = None

    def get_encryption_key(self) -> bytes:
        """
        Get or derive encryption key.

        Uses machine-specific key stored in:
        - Linux: ~/.local/share/roomz/.key
        - macOS: ~/Library/Application Support/roomz/.key
        - Windows: %APPDATA%/roomz/.key
        """
        if self._key:
            return self._key

        # Determine platform-specific location
        if os.name == 'nt':
            key_file = Path(os.environ['APPDATA']) / 'roomz' / '.key'
        elif sys.platform == 'darwin':
            key_file = Path.home() / 'Library' / 'Application Support' / 'roomz' / '.key'
        else:
            key_file = Path.home() / '.local' / 'share' / 'roomz' / '.key'

        if key_file.exists():
            self._key = key_file.read_bytes()
        else:
            # Generate new key
            self._key = Fernet.generate_key()
            key_file.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            key_file.write_bytes(self._key)
            key_file.chmod(0o600)

        return self._key

    def encrypt_session_data(self, data: dict) -> bytes:
        """Encrypt session data."""
        fernet = Fernet(self.get_encryption_key())
        json_data = json.dumps(data).encode()
        return fernet.encrypt(json_data)

    def decrypt_session_data(self, encrypted: bytes) -> dict | None:
        """Decrypt session data."""
        try:
            fernet = Fernet(self.get_encryption_key())
            json_data = fernet.decrypt(encrypted)
            return json.loads(json_data)
        except InvalidToken:
            logger.warning("Failed to decrypt session cache - key may have changed")
            return None
        except Exception as e:
            logger.warning(f"Failed to decrypt session cache: {e}")
            return None

# Usage in AsyncClient
def _save_session_cookie(self, cookie_value: str) -> None:
    """Save encrypted session cookie."""
    if not self._session_cache_file:
        return

    try:
        encryption = SessionCacheEncryption()
        encrypted_data = encryption.encrypt_session_data({
            "session_cookie": cookie_value,
            "server": self._server_url
        })

        # Write with secure permissions
        fd = os.open(
            self._session_cache_file,
            os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_EXCL,
            mode=0o600
        )
        with os.fdopen(fd, 'wb') as f:
            f.write(encrypted_data)

    except Exception as e:
        logger.warning(f"Failed to save session cookie: {e}")
```

**Option B: Minimal Storage (Default)**

```python
# Only store JWT, not server URL (server passed explicitly)
# Reduces exposure but still has JWT in plaintext
{
  "session_cookie": "eyJ..."
}
```

**Recommendation**: Use **Option B** as default (minimal storage), offer **Option A** as opt-in for high-security environments. Add documentation explaining the trade-offs.

**Reference**:
- [OWASP A04:2025 - Cryptographic Failures](https://owasp.org/Top10/A04_2025-Cryptographic_Failures/)
- [CWE-311: Missing Encryption of Sensitive Data](https://cwe.mitre.org/data/definitions/311.html)

---

### MEDIUM-3: Server URL Validation

**OWASP Category**: A01:2025 - Broken Access Control
**STRIDE**: Tampering
**CVSS Score**: 4.3 (Medium)

**Description**: Server URL from config is not validated. A malicious config file could redirect connections to attacker-controlled servers.

**Remediation**:

```python
from urllib.parse import urlparse

def validate_server_url(url: str) -> str:
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
        Validated URL

    Raises:
        ValueError: If URL is invalid or dangerous
    """
    try:
        parsed = urlparse(url)

        # Must be http or https
        if parsed.scheme not in ('http', 'https'):
            raise ValueError(
                f"Invalid server URL: scheme must be http or https, got {parsed.scheme}"
            )

        # Must have hostname
        if not parsed.hostname:
            raise ValueError("Invalid server URL: missing hostname")

        # No credentials in URL
        if parsed.username or parsed.password:
            raise ValueError(
                "Invalid server URL: credentials in URL are not allowed. "
                "Use environment variables for authentication."
            )

        # Warn on localhost/private IPs (development mode)
        if parsed.hostname in ('localhost', '127.0.0.1', '::1'):
            logger.warning(
                "Server URL points to localhost. This should only be used in development."
            )

        if parsed.hostname.startswith('192.168.') or parsed.hostname.startswith('10.'):
            logger.warning(
                f"Server URL points to private IP {parsed.hostname}. "
                "This should only be used in development or private networks."
            )

        return url

    except Exception as e:
        raise ValueError(f"Invalid server URL: {e}") from e


# Usage in AsyncClient.__init__
def __init__(
    self,
    server_url: str,
    session_token: str = "",
    # ...
):
    # Validate server URL
    self._server_url = validate_server_url(server_url)
    # ...
```

**Reference**:
- [OWASP A01:2025 - Broken Access Control](https://owasp.org/Top10/A01_2025-Broken_Access_Control/)
- [CWE-918: Server-Side Request Forgery](https://cwe.mitre.org/data/definitions/918.html)

---

## Low Findings (CVSS 0.1-3.9)

### LOW-1: Error Message Information Leakage

**OWASP Category**: A09:2025 - Security Logging Failures
**STRIDE**: Information Disclosure
**CVSS Score**: 3.1 (Low)

**Description**: Exception messages in config loading include file paths and may leak information about system structure.

**Current Implementation**:

```python
except Exception as e:
    logger.warning(f"Failed to load display name from config: {e}")
```

**Remediation**:

```python
except PermissionError:
    logger.warning(f"Permission denied reading config file {config_file}")
except json.JSONDecodeError:
    logger.warning(f"Config file {config_file} contains invalid JSON")
except Exception as e:
    # Log details internally, generic message publicly
    logger.debug(f"Failed to load config: {e}")  # Internal debug
    logger.warning("Failed to load config file")  # Public warning
```

**Reference**:
- [OWASP A09:2025 - Security Logging Failures](https://owasp.org/Top10/A09_2025-Security_Logging_Failures/)

---

### LOW-2: Config File Migration Security

**OWASP Category**: A05:2025 - Security Misconfiguration
**STRIDE**: Tampering
**CVSS Score**: 2.4 (Low)

**Description**: The planned migration from `~/.roomz/config.toml` to `~/.roomz.toml` should include security checks during migration.

**Remediation**:

```python
def migrate_config_file(old_path: Path, new_path: Path) -> bool:
    """
    Migrate config file with security validation.

    Security:
    - Validates old file permissions before reading
    - Creates new file with secure permissions
    - Atomically moves file
    - Cleans up old file securely
    """
    if not old_path.exists():
        return False

    # Check old file permissions
    old_mode = old_path.stat().st_mode
    if old_mode & 0o077:
        logger.warning(
            f"Old config file {old_path} has insecure permissions. "
            f"New file will be created with 0600 permissions."
        )

    # Read old config
    try:
        old_config = old_path.read_text()
    except Exception as e:
        logger.error(f"Failed to read old config: {e}")
        return False

    # Write new config with secure permissions
    try:
        fd = os.open(new_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode=0o600)
        with os.fdopen(fd, 'w') as f:
            f.write(old_config)
    except FileExistsError:
        logger.warning(f"New config file {new_path} already exists. Skipping migration.")
        return False
    except Exception as e:
        logger.error(f"Failed to write new config: {e}")
        return False

    # Remove old config securely
    try:
        # Overwrite old file before removing (secure delete)
        old_path.write_bytes(b'\x00' * old_path.stat().st_size)
        old_path.unlink()
    except Exception as e:
        logger.warning(f"Failed to remove old config: {e}")

    logger.info(f"Migrated config from {old_path} to {new_path}")
    return True
```

**Reference**:
- [OWASP A05:2025 - Security Misconfiguration](https://owasp.org/Top10/A05_2025-Security_Misconfiguration/)

---

## Design Question Answers

### 1. Should config files have restricted permissions (e.g., 0600)?

**Answer**: **YES**, with nuance:

| File Type | Recommended Permissions | Rationale |
|-----------|------------------------|-----------|
| Session cache (`session.json`) | **0600** | Contains JWT token (authentication credential) |
| Config file (`roomz.toml`) | **0644 acceptable** | Contains display_name and server_url (low sensitivity) |
| Directory (`~/.roomz/`) | **0700** | Prevents other users from creating malicious files |
| Directory (`~/.roomz.toml` parent) | **Home dir default** | Typically already restricted |

**Implementation Priority**: HIGH for session cache, MEDIUM for config files.

### 2. Should we warn if config file is world-readable?

**Answer**: **YES**:

```python
# Recommended warning behavior
if file_mode & 0o044:  # World-readable
    logger.warning(
        f"Config file {file_path} is world-readable. "
        "Config values may be visible to other users. "
        "Consider running: chmod 600 {file_path}"
    )

if file_mode & 0o022:  # Group/other writable
    logger.error(
        f"Security risk: Config file {file_path} is writable by others. "
        "Other users could modify this file. "
        "Run: chmod 600 {file_path}"
    )
    # Option: Refuse to load writable files
    return None
```

**Implementation Priority**: MEDIUM.

### 3. How to handle sensitive config values (if any)?

**Answer**: Current config values have low sensitivity:

| Config Value | Sensitivity | Protection |
|--------------|-------------|------------|
| `display_name` | **LOW** | None needed (public in messages) |
| `server_url` | **LOW-MEDIUM** | Validate URL, warn on suspicious hosts |
| `session_cache_file` | **HIGH** | Encrypt, restrict permissions |

**Future sensitive values** (if added):
- API keys: Store in environment variables only, never in config files
- Secrets/tokens: Same as API keys
- Passwords: Never store in config files

**Recommendation**: Document in config file schema which values are sensitive and how to protect them.

### 4. Is server_url considered sensitive? What about future config items?

**Answer**:

**`server_url` Sensitivity**: **LOW-MEDIUM**

- **Not sensitive for development**: `http://localhost:8000`
- **Potentially sensitive in production**: Internal server names, non-public endpoints
- **Attack vector**: Malicious config could redirect to attacker server

**Protection**:
```python
# Validate server URL
def validate_server_url(url: str) -> str:
    """Validate server URL scheme and hostname."""
    # See MEDIUM-3 for implementation
```

**Future Config Items Classification**:

| Config Item | Sensitivity | Storage Recommendation |
|-------------|-------------|----------------------|
| `api_key` | **CRITICAL** | Environment variable only |
| `token` | **CRITICAL** | Environment variable only |
| `password` | **CRITICAL** | Never store in client config |
| `timeout` | **LOW** | Config file OK |
| `debug_mode` | **LOW** | Config file OK |
| `retry_count` | **LOW** | Config file OK |

**Recommendation**: Add documentation explicitly stating which config values are sensitive.

---

## Security Checklist for I8-000 Implementation

### Before Implementation

- [ ] Decide on current directory config loading (recommend: remove)
- [ ] Implement session cache file permission enforcement (0600)
- [ ] Add directory security validation (not world-writable)
- [ ] Implement server URL validation
- [ ] Add permission warnings for config files

### During Implementation

- [ ] Create `SecurityError` exception class
- [ ] Add `_validate_directory_security()` method
- [ ] Add `_save_session_cookie_secure()` with permission enforcement
- [ ] Add config file permission checks in `_load_*` functions
- [ ] Add server URL validation in `AsyncClient.__init__`

### After Implementation

- [ ] Test permission enforcement (0644 -> warning, 0777 -> error)
- [ ] Test directory security validation (world-writable dir -> error)
- [ ] Test server URL validation (javascript: URLs rejected)
- [ ] Test session cache encryption (if implemented)
- [ ] Document security considerations in configuration.md

---

## Recommendations

### Must Implement Before I8-000

| ID | Finding | Action |
|----|---------|--------|
| HIGH-1 | Session cache permissions | Enforce 0600 on session files |
| HIGH-2 | Current directory loading | Remove `./roomz.toml` from priority or add security validation |
| MEDIUM-3 | Server URL validation | Add URL scheme and hostname validation |

### Should Implement for I8-000

| ID | Finding | Action |
|----|---------|--------|
| MEDIUM-1 | Permission warnings | Add warnings for insecure permissions |
| MEDIUM-2 | Session encryption | Offer optional encryption for session cache |

### Document for Users

| ID | Finding | Action |
|----|---------|--------|
| LOW-1 | Error messages | Review logging for information leakage |
| LOW-2 | Migration | Add secure migration path for config files |

---

## Positive Security Observations

1. **Environment Variable Priority**: Config values can be overridden by environment variables, allowing secure injection of secrets without config files.

2. **No Secrets in Config**: Current config values (`display_name`, `server_url`) have low sensitivity.

3. **Explicit Session Cache**: Session cache location is explicit, not auto-discovered, giving users control.

4. **JWT in Cookie**: Session cookie stored separately from config, following separation of concerns.

5. **Config File Parsing**: Simple TOML parsing with limited attack surface (no arbitrary code execution).

---

## Recommended Configuration System Design

Based on this security analysis, the recommended configuration priority order for I8-000:

```markdown
**Priority Order (Revised)**:
  1. Explicit parameter (e.g., AsyncClient(server_url=...))
  2. Environment variable (e.g., ROOMZ_SERVER_URL, ROOMZ_DISPLAY_NAME)
  3. ~/.roomz.toml in home directory (NOT current directory)

**File Permissions**:
  - Session cache: 0600 (owner read/write)
  - Config files: 0644 acceptable (no secrets)
  - Config directories: 0700 (owner access only)

**Security Validations**:
  - Validate server URL (scheme, hostname)
  - Warn on insecure file permissions
  - Error on world-writable directories
  - Enforce session cache permissions

**Future Sensitive Values**:
  - Mark sensitive values in config schema
  - Recommend environment variables for secrets
  - Never store passwords in config files
```

---

## References

- [OWASP Top 10:2025](https://owasp.org/Top10/)
- [OWASP A01:2025 - Broken Access Control](https://owasp.org/Top10/A01_2025-Broken_Access_Control/)
- [OWASP A04:2025 - Cryptographic Failures](https://owasp.org/Top10/A04_2025-Cryptographic_Failures/)
- [OWASP A05:2025 - Security Misconfiguration](https://owasp.org/Top10/A05_2025-Security_Misconfiguration/)
- [OWASP A09:2025 - Security Logging Failures](https://owasp.org/Top10/A09_2025_Security_Logging_Failures/)
- [CWE-732: Incorrect Permission Assignment](https://cwe.mitre.org/data/definitions/732.html)
- [CWE-426: Untrusted Search Path](https://cwe.mitre.org/data/definitions/426.html)
- [CWE-311: Missing Encryption of Sensitive Data](https://cwe.mitre.org/data/definitions/311.html)
- [NIST SP 800-53: AC-3 Access Enforcement](https://csrc.nist.gov/publications/detail/sp/800-53/rev-5/final)