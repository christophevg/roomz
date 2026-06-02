# Consensus Report: I8-004 Clevis Integration

**Task**: Replace config module with clevis package
**Date**: 2026-06-02
**Participants**: API Architect, Security Engineer

## Consensus Decision

Adopt clevis package with mandatory security wrapper layer

All domain agents agree that clevis adoption is beneficial, but requires a wrapper layer to preserve security requirements from I8-000.

## Key Agreements

### 1. Architecture Approach
- **Thin wrapper around clevis** (~120 lines vs current 353 lines)
- **Session cache separate** from clevis config (runtime state, not user config)
- **Security wrapper layer** implements all I8-000 security requirements
- **Breaking change accepted**: TOML format from `[client]` section to top-level

### 2. Security Requirements (Must Preserve)
All security features from I8-000 must be preserved:
- Session cache files created with 0600 permissions
- Directory security validation (reject world-writable)
- Config file permission warnings
- Server URL validation (http/https only, no credentials)
- Error messages reviewed for information leakage

### 3. Integration Points

**AsyncClient/SyncClient:**
```python
def __init__(self, server_url=None, config=None, ...):
    if config is not None:
        self._config = config
    elif server_url is not None:
        self._config = Config(server_url=server_url)
    else:
        self._config = get_client_config(cli=False)
```

**CLI:**
```python
def main():
    config = get_client_config(cli=True)
    # ...
```

### 4. Session Cache Handling
Session cache remains in roomz code:
- `~/.roomz/session.json` (runtime state, not user configuration)
- Created with 0600 permissions
- Directory security validation
- Not passed to clevis

### 5. Breaking Changes (Owner Accepted)
1. TOML format: Remove `[client]` section -> top-level fields
2. Environment prefix: No `ROOMZ_PREFIX` system -> use interpolation
3. `config_path` parameter: Removed -> use explicit config
4. `merge()` method: Removed -> use explicit config
5. `auto_discover()` return: No longer returns path

## Implementation Approach

### Phase 1: Security Wrapper Layer
1. Create `src/roomz/client/session_cache.py` - session cache security
2. Create `src/roomz/client/config_security.py` - directory validation
3. Create `src/roomz/client/config_validation.py` - URL validation
4. Create `src/roomz/client/config.py` - clevis wrapper with security

### Phase 2: Client Integration
1. Update `AsyncClient.__init__()` to use `get_client_config(cli=False)`
2. Update `SyncClient` to delegate to AsyncClient
3. Update CLI to use `get_client_config(cli=True)`

### Phase 3: Cleanup and Documentation
1. Remove old config module
2. Update tests (remove `[client]` section from fixtures)
3. Update README and documentation
4. Add migration guide

## Risk Assessment

| Risk | Mitigation | Status |
|------|------------|--------|
| Security features lost | Security wrapper layer | Addressed |
| Breaking TOML format | Owner accepted, migration guide | Accepted |
| Session cache handling | Keep separate from clevis | Addressed |
| URL validation | Implement in wrapper | Addressed |

## Files to Modify

### Remove
- `src/roomz/config/__init__.py`
- `src/roomz/config/config.py`
- `src/roomz/config/security.py`
- `src/roomz/config/validation.py`

### Create
- `src/roomz/client/session_cache.py` (extracted security)
- `src/roomz/client/config_security.py` (extracted security)
- `src/roomz/client/config_validation.py` (extracted security)
- `src/roomz/client/config.py` (clevis wrapper)

### Modify
- `src/roomz/client/async_client.py` - use new config
- `src/roomz/client/sync_client.py` - use new config
- `src/roomz/cli/__init__.py` - use new config
- `src/roomz/cli/__main__.py` - use new config
- `pyproject.toml` - add clevis dependency
- `tests/` - update fixtures
- `docs/configuration.md` - update docs
- `README.md` - update examples

## Sign-off

- **API Architect**: Approved - Architecture sound, integration clear
- **Security Engineer**: Approved - Security wrapper addresses all I8-000 requirements