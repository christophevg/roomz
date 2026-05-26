# Functional Review: I8-000 (Generalized Configuration Pattern)

**Date**: 2026-05-26
**Reviewer**: Functional Analyst Agent
**Status**: CONDITIONAL APPROVAL

## Executive Summary

The implementation of I8-000 is **functionally correct** for the core requirements, but has **incomplete security hardening** as specified in the consensus document. The configuration system works as designed, but the security requirements from the security review were not fully implemented.

**Verdict**: Requires security improvements before full approval.

---

## Requirements Checklist

| Requirement | Status | Notes |
|-------------|--------|-------|
| Config Class (dataclass) | PASS | Config dataclass with server_url, display_name |
| AsyncClient constructor (config/config_path params) | PASS | Uses config and config_path, no individual params |
| Resolution order | PASS | Correct priority chain implemented |
| Environment variable prefix | PASS | ROOMZ_PREFIX support implemented |
| No backward compatibility | PASS | No ~/.roomz/config.toml fallback |
| Session cache 0600 permissions | PASS | os.chmod(file, 0o600) implemented |
| Server URL validation | PASS | http/https validated in connect() |
| Config file format (TOML, [roomz] section) | PASS | Correct TOML parsing |

---

## Detailed Review

### 1. Config Class (PASS)

**File**: `src/roomz/client/config.py` (lines 34-36)

```python
@dataclass
class Config:
  server_url: str | None = None
  display_name: str | None = None
```

- Correctly implements dataclass with required attributes
- Includes `validate()` method for server_url validation
- Includes `merge()` method for combining configs
- Includes `load()` and `auto_discover()` class methods

### 2. AsyncClient Constructor (PASS)

**File**: `src/roomz/client/async_client.py` (lines 70-82)

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

- `config` parameter for explicit Config instance
- `config_path` parameter for loading from file
- No individual `server_url` or `display_name` parameters (as per requirements)
- Uses `resolve_config()` for proper resolution chain

### 3. Resolution Order (PASS)

**File**: `src/roomz/client/config.py` (lines 263-305)

The `resolve_config()` function implements correct priority:

1. Explicit `config` parameter (returned immediately if provided)
2. Explicit `config_path` parameter (loaded and merged with auto-discover)
3. Auto-discover from environment (prefixed then unprefixed)
4. Auto-discover from `./roomz.toml`
5. Auto-discover from `~/.roomz.toml`

Environment variable resolution in `_get_env_var()` (lines 78-108):
- Correctly tries prefixed variable first (`{PREFIX}_{BASE_VAR}`)
- Falls back to unprefixed variable
- Uses `ROOMZ_PREFIX` environment variable for prefix

### 4. Backward Compatibility (PASS)

**Requirement**: "No backward compatibility: Drop ~/.roomz/config.toml"

The implementation correctly does NOT include fallback to `~/.roomz/config.toml`:

```python
config_files = [
  Path.cwd() / "roomz.toml",  # ./roomz.toml
  Path.home() / ".roomz.toml",  # ~/.roomz.toml
]
```

This matches the requirements summary which explicitly states to drop backward compatibility.

### 5. Session Cache Permissions (PASS)

**File**: `src/roomz/client/async_client.py` (lines 216-233)

```python
def _save_session_cookie(self, cookie_value: str) -> None:
  if not self._session_cache_file:
    return

  try:
    self._session_cache_file.parent.mkdir(parents=True, exist_ok=True)
    with open(self._session_cache_file, "w") as f:
      json.dump({"session_cookie": cookie_value, "server": self._config.server_url}, f)

    # Enforce 0600 permissions (owner read/write only)
    os.chmod(self._session_cache_file, 0o600)
  except Exception as e:
    logger.warning(f"Failed to save session cookie: {e}")
```

- Session cache files are created with 0600 permissions
- Security requirement HIGH-1 satisfied

### 6. Server URL Validation (PASS)

**File**: `src/roomz/client/async_client.py` (lines 274-285)

```python
async def connect(self, session_token: str | None = None) -> None:
  # Validate configuration
  if self._config.server_url is None:
    raise ConfigurationError(
      "server_url is not configured. "
      "Provide config with server_url, set ROOMZ_SERVER_URL, "
      "or create ./roomz.toml or ~/.roomz.toml"
    )

  # Validate server_url format
  if not self._config.server_url.startswith(("http://", "https://")):
    raise ConfigurationError(
      f"server_url must be http:// or https:// URL, got: {self._config.server_url}"
    )
```

- Validates http:// or https:// scheme
- Raises ConfigurationError on invalid URL
- Also validated in Config.validate() method

### 7. SyncClient Integration (PASS)

**File**: `src/roomz/client/sync_client.py` (lines 53-98)

SyncClient correctly delegates to AsyncClient:
- Passes `config` and `config_path` parameters
- All other parameters delegated correctly
- No duplication of configuration logic

### 8. CLI Integration (PASS)

**File**: `src/roomz/cli/app_tui.py` (lines 143-168)

ChatApp correctly uses Config:
- Accepts optional `config` parameter in `__init__`
- Passes config to AsyncClient constructor
- Falls back to auto-discovery when config is None

```python
def __init__(self, config: Config | None = None):
  ...
  self.client = AsyncClient(
    config=config,
    session_cache_file=Path.home() / ".roomz" / "session.json",
  )
```

---

## Test Coverage Review

**File**: `tests/test_config.py`

| Test Case | Status | Coverage |
|------------|--------|----------|
| Config defaults | PASS | Empty Config() tested |
| Config with values | PASS | Explicit values tested |
| Config merge | PASS | Merge behavior tested |
| Config validation | PASS | Invalid URL, credentials detected |
| Environment variables | PASS | With/without prefix tested |
| Config file loading | PASS | TOML parsing tested |
| Auto-discovery | PASS | Priority chain tested |
| resolve_config() | PASS | All paths tested |
| Integration with AsyncClient | PASS | ConfigurationError on missing server_url |

All core functionality is tested. Tests are well-structured and cover the priority chain correctly.

---

## Security Review (INCOMPLETE)

The consensus document (reporting/I8-000/consensus.md) specified several security requirements. This section evaluates their implementation status:

### HIGH Priority Requirements

| Requirement | Status | Notes |
|-------------|--------|-------|
| **HIGH-1**: Session cache 0600 permissions | PASS | Implemented in _save_session_cookie() |
| **HIGH-2**: Directory security validation | FAIL | NOT IMPLEMENTED |

**HIGH-2 Details**: The consensus requires rejecting config from world-writable directories. Current implementation in `Config.auto_discover()` loads `./roomz.toml` without any security validation:

```python
for config_file in config_files:
  if config_file.exists():
    try:
      file_config = cls.load(config_file)
      # No security validation here!
```

### MEDIUM Priority Requirements

| Requirement | Status | Notes |
|-------------|--------|-------|
| **MEDIUM-1**: Config file permission warnings | FAIL | NOT IMPLEMENTED |
| **MEDIUM-2**: Session directory validation | FAIL | NOT IMPLEMENTED |
| **MEDIUM-3**: Server URL validation | PARTIAL | http/https done, hostname missing |

**MEDIUM-1 Details**: No warning when config files have group/other read permissions.

**MEDIUM-2 Details**: No validation that session cache directory is not world-writable.

**MEDIUM-3 Details**: Server URL validation checks scheme and credentials but does not validate hostname presence:

```python
# Current: checks scheme
if not self._config.server_url.startswith(("http://", "https://")):

# Missing: hostname validation
# Should verify parsed URL has valid hostname
```

### LOW Priority Requirements

| Requirement | Status | Notes |
|-------------|--------|-------|
| **LOW-1**: Error message information leakage | PASS | Generic messages, no sensitive data |
| **LOW-2**: Secure migration path | N/A | Backward compatibility dropped |

---

## Gaps Identified

### Gap 1: Missing Security Exception Class

The consensus document specifies creating a `SecurityError` exception:

```python
class SecurityError(Exception):
  """Raised when a security issue is detected."""
```

**Status**: NOT FOUND in exceptions.py

### Gap 2: Missing Directory Security Validation

The security analysis recommended this validation function:

```python
def _validate_directory_security(self, directory: Path) -> None:
  """Validate directory is not world-writable."""
  stat_info = directory.stat()
  if stat_info.st_mode & stat.S_IWOTH:
    raise SecurityError(f"Directory {directory} is world-writable")
```

**Status**: NOT IMPLEMENTED

### Gap 3: Missing File Permission Warnings

Config files should warn if they have group/other permissions:

```python
file_mode = config_file.stat().st_mode
if file_mode & 0o077:
  logger.warning(f"Config file {config_file} has insecure permissions")
```

**Status**: NOT IMPLEMENTED

### Gap 4: Missing Hostname Validation

Server URL should validate that hostname exists:

```python
parsed = urlparse(url)
if not parsed.hostname:
  raise ValueError("Invalid server URL: missing hostname")
```

**Status**: NOT IMPLEMENTED (only scheme validation)

---

## Documentation Review

### Config Docstrings (PASS)

The `Config` class has comprehensive docstrings:
- Resolution order documented
- Environment variables documented
- Config file format documented
- Prefix system documented

### AsyncClient Docstrings (PASS)

The `AsyncClient` class has comprehensive docstrings:
- Configuration priority documented
- Usage examples provided
- Environment variables documented

### CLI Integration (PASS)

The CLI has appropriate comments and usage documentation.

---

## Recommendations

### Must Fix Before Approval

1. **Add directory security validation for `./roomz.toml`**
   - Reject config from world-writable directories
   - Log security warning when loading from current directory

2. **Add hostname validation to server URL**
   - Validate that parsed URL has a hostname
   - Optionally warn on localhost/private IPs

### Should Fix (Medium Priority)

3. **Add file permission warnings**
   - Warn if config file has group/other permissions
   - Suggest chmod 600 to users

4. **Add SecurityError exception class**
   - Add to exceptions.py
   - Use for security-related rejections

5. **Validate session cache directory**
   - Check that parent directory is not world-writable
   - Warn if permissions are too open

### Nice to Have (Low Priority)

6. **Enhance server URL validation**
   - Parse URL properly with urlparse
   - Validate all components
   - Warn on suspicious hosts

---

## Conclusion

**VERDICT**: **CONDITIONAL APPROVAL**

The core configuration pattern is correctly implemented:
- Config dataclass works as specified
- Resolution order matches requirements
- Environment variable prefix works correctly
- Session cache permissions enforced
- Server URL validation partially implemented
- Tests provide good coverage

However, the security hardening specified in the consensus document is incomplete:

**Critical**: Directory security validation (HIGH-2) must be implemented before this can be fully approved. Loading `./roomz.toml` from world-writable directories is a security risk.

**Recommended Action**: Implement the security validations from the consensus document, then this task can be marked complete.

---

## Files Reviewed

- `/Users/xtof/Workspace/agentic/roomz/src/roomz/client/config.py` - Core configuration module
- `/Users/xtof/Workspace/agentic/roomz/src/roomz/client/async_client.py` - AsyncClient implementation
- `/Users/xtof/Workspace/agentic/roomz/src/roomz/client/sync_client.py` - SyncClient wrapper
- `/Users/xtof/Workspace/agentic/roomz/src/roomz/cli/app_tui.py` - CLI integration
- `/Users/xtof/Workspace/agentic/roomz/tests/test_config.py` - Configuration tests
- `/Users/xtof/Workspace/agentic/roomz/src/roomz/client/exceptions.py` - Exception classes

## Related Documents

- `/Users/xtof/Workspace/agentic/roomz/TODO.md` - Task definition
- `/Users/xtof/Workspace/agentic/roomz/reporting/I8-000/consensus.md` - Consensus design
- `/Users/xtof/Workspace/agentic/roomz/analysis/config-api.md` - API design
- `/Users/xtof/Workspace/agentic/roomz/analysis/config-security.md` - Security analysis