# Consensus: I8-000 Configuration Pattern

**Date**: 2026-05-26
**Task**: I8-000 - Generalized Configuration Pattern
**Participants**: API Architect, Security Engineer

## Summary

Domain agents reviewed the proposed configuration system for the roomz Python client. The key design decisions were validated with important security modifications.

## Agreed Design Decisions

### 1. Config File Location: Single File (API Architect ✅ Security Engineer ✅)

**Decision**: Migrate from `~/.roomz/config.toml` (folder) to `~/.roomz.toml` (single file)

**Rationale**:
- Better discoverability
- Simpler user experience
- Session cache remains at `~/.roomz/session.json` (runtime data, not user config)
- Backward compatibility with deprecation warning for old location

### 2. Configuration Priority Order (API Architect ✅ Security Engineer ⚠️)

**Original Proposal**:
1. Explicit parameter
2. Environment variable
3. `./roomz.toml` (current directory)
4. `~/.roomz.toml` (home directory)
5. `~/.roomz/config.toml` (deprecated)

**Security Modification**:
- `./roomz.toml` creates security risk in world-writable directories
- **Modified Priority**:
  1. Explicit parameter
  2. Environment variable
  3. `./roomz.toml` (with security validation - reject if world-writable)
  4. `~/.roomz.toml`
  5. `~/.roomz/config.toml` (deprecated)

**Security Validation for `./roomz.toml`**:
- Reject config from world-writable directories
- Warn if config file is world-readable
- Log security warning when loading from current directory

### 3. Config Items (API Architect ✅ Security Engineer ✅)

All client settings follow the same pattern:

| Config Item | Env Var | Sensitivity |
|-------------|---------|-------------|
| `server_url` | `ROOMZ_SERVER_URL` | Low-Medium |
| `display_name` | `ROOMZ_DISPLAY_NAME` | Low |
| `session_cache_file` | `ROOMZ_SESSION_CACHE_FILE` | N/A (path only) |

### 4. File Permissions (Security Engineer Required)

| File | Permissions | Rationale |
|------|-------------|-----------|
| `session.json` | **0600** | Contains JWT token |
| `roomz.toml` | 0644 OK | No secrets |
| `~/.roomz/` directory | **0700** | Prevents tampering |

### 5. Server URL Validation (Security Engineer Required)

Validate server URL to prevent hijacking:
- Must be `http://` or `https://`
- No credentials in URL
- Valid hostname
- Warn on localhost/private IPs (development mode)

### 6. Backward Compatibility (API Architect ✅)

- Old config location still works with deprecation warning
- Explicit parameter signature accepts `None`
- Clear error messages when required config missing

## Implementation Checklist

### Phase 1: Core Configuration System
- [ ] Create `src/roomz/client/config.py` module
- [ ] Add `ConfigurationError` to `exceptions.py`
- [ ] Implement `Config` class with priority loading
- [ ] Add TOML dependency (`tomli` for Python < 3.11)

### Phase 2: Security Hardening
- [ ] Implement session cache file permission enforcement (0600)
- [ ] Add directory security validation (reject world-writable)
- [ ] Add server URL validation
- [ ] Add config file permission warnings

### Phase 3: Client Integration
- [ ] Update `AsyncClient.__init__()` to use `Config.load()`
- [ ] Update `AsyncClient.connect()` to validate `server_url`
- [ ] Update `SyncClient` to delegate to `AsyncClient`
- [ ] Update CLI app to use `Config.load()`

### Phase 4: Testing & Documentation
- [ ] Add configuration tests (priority, security, validation)
- [ ] Update documentation (`docs/configuration.md`)
- [ ] Add migration guide for `~/.roomz/config.toml`
- [ ] Add deprecation warning for old config location

## Security Considerations

### HIGH Priority (Must Implement)
1. Session cache file permissions (0600)
2. Current directory config validation (reject world-writable)
3. Server URL validation

### MEDIUM Priority (Should Implement)
1. Config file permission warnings
2. Directory permission checks

### LOW Priority (Document)
1. Migration path security
2. Error message information leakage

## Files Created

- `analysis/config-api.md` - API design analysis
- `analysis/config-security.md` - Security analysis
- `reporting/I8-000/consensus.md` - This document