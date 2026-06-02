# Clevis Package Evaluation

**Date:** 2024-06-02  
**Issue:** #5 - Evaluate clevis for configuration handling  
**Version Evaluated:** clevis 0.2.0

## Executive Summary

**Recommendation: Adopt with modifications**

Clevis provides a well-designed, type-safe configuration management system that can replace most of roomz's custom configuration code. The migration would reduce maintenance burden and provide better CLI argument support, but requires adapting to clevis's simpler precedence model and potentially losing some roomz-specific features.

---

## Package Overview

### Clevis (v0.2.0)

**Source:** https://github.com/christophevg/clevis  
**License:** MIT  
**Dependencies:** dacite (required), tomli/envtoml/tomlev (optional)

Clevis is a configuration management library for Python that uses dataclasses as schemas. It merges configuration from multiple sources with a clear precedence chain.

**Key Features:**
- Type-safe configuration via dataclass schemas
- Layered configuration: CLI > Project TOML > User TOML > Defaults
- Automatic TOML parser selection (stdlib, tomli, envtoml, tomlev)
- Environment variable interpolation (`${VAR}` and `${VAR|default}`)
- CLI argument generation from nested dataclasses
- Helpful error messages with actionable suggestions
- Support for nested configuration structures

**Installation:**
```bash
pip install clevis                    # Python 3.11+
pip install clevis[tomli]             # Python 3.10
pip install clevis[envtoml]           # With ${VAR} interpolation
pip install clevis[tomlev]            # With ${VAR|default} syntax
```

---

## Feature Comparison

| Feature | Roomz Current | Clevis | Notes |
|---------|--------------|--------|-------|
| **Dataclass-based config** | Yes | Yes | Both use dataclasses |
| **TOML file loading** | Yes | Yes | Both support TOML |
| **User-level config** | Yes (`~/.roomz.toml`) | Yes (`~/.{name}.toml`) | Same pattern |
| **Project-level config** | Yes (`./roomz.toml`) | Yes (`./{name}.toml`) | Same pattern |
| **Environment variables** | Yes (prefix support) | Via interpolation | Different approaches |
| **CLI arguments** | No | Yes | Clevis advantage |
| **Explicit config parameter** | Yes | Yes | Both support |
| **Config file path parameter** | Yes | No | Roomz advantage |
| **Config discovery logging** | Yes (returns path) | No | Roomz advantage |
| **Validation methods** | Yes (custom) | Yes (via dataclass) | Different styles |
| **Merge functionality** | Yes (merge method) | No | Roomz advantage |
| **Error messages** | Basic | Enhanced | Clevis advantage |
| **Nested configs** | Manual | Automatic | Clevis advantage |
| **Required fields** | Optional by default | No default = required | Clevis clearer |
| **TOML section** | `[client]` required | Top-level | Incompatible |

---

## Implementation Impact

### What Would Change

**1. Configuration Class**

Current roomz config:
```python
# Current: src/roomz/client/config.py (353 lines)
@dataclass
class Config:
  server_url: str | None = None
  display_name: str | None = None
  
  @staticmethod
  def _get_env_var(prefix: str, base_var: str) -> str | None: ...
  @classmethod
  def load(cls, config_path: str | Path) -> Config: ...
  @classmethod
  def auto_discover(cls) -> tuple[Config, Path | None]: ...
  def merge(self, other: Config) -> Config: ...
  def validate(self) -> list[str]: ...
```

With clevis:
```python
# New: Simplified config.py (~50 lines)
from dataclasses import dataclass
from clevis import get_config, ConfigError

@dataclass
class Config:
  server_url: str | None = None
  display_name: str | None = None

def get_client_config(name: str = "roomz", args: list | None = None) -> Config:
  """Get configuration with roomz-specific defaults."""
  try:
    return get_config(Config, name=name, user=True, project=True, args=args)
  except ConfigError as e:
    # Convert clevis error to roomz ConfigurationError
    from roomz.client.exceptions import ConfigurationError
    raise ConfigurationError(str(e)) from e
```

**2. TOML Format Change**

Current format requires `[client]` section:
```toml
# Current: ~/.roomz.toml
[client]
server_url = "http://localhost:5000"
display_name = "Alice"
```

Clevis uses top-level fields:
```toml
# New: ~/.roomz.toml
server_url = "http://localhost:5000"
display_name = "Alice"
```

**Migration:** Requires user communication. Existing configs need conversion.

**3. Environment Variables**

Current approach with prefix:
```python
# Current: Manual environment variable handling
ROOMZ_PREFIX=DEV
DEV_ROOMZ_SERVER_URL=http://localhost:8000
```

With clevis (using envtoml or tomlev):
```toml
# New: TOML with interpolation
server_url = "${ROOMZ_SERVER_URL}"
# or with default:
server_url = "${ROOMZ_SERVER_URL|http://localhost:5000}"
```

Or via CLI:
```bash
roomz-cli --server-url http://localhost:8000
```

**4. Removed Features**

The following features would need reimplementation:

| Feature | Impact | Solution |
|---------|--------|----------|
| `config_path` parameter | Medium | Add wrapper that calls clevis with project=False |
| `auto_discover()` returns path | Low | Logging is optional; can be removed |
| `merge()` method | Low | Rarely used; can use explicit config instead |
| Custom `validate()` | Low | Use dataclass validation or add post-init |
| Environment prefix (ROOMZ_PREFIX) | Medium | Use interpolation or CLI args |
| `[client]` TOML section | High | Breaking change for users |

---

## Migration Complexity

### Low Complexity Areas

1. **Core config loading** - Clevis handles this directly
2. **Type safety** - Both use dataclasses
3. **Default values** - Both support defaults in dataclass

### Medium Complexity Areas

1. **Environment variable prefix** - Need to choose:
   - Option A: Use clevis interpolation in TOML
   - Option B: Set environment variables directly
   - Option C: Add CLI arguments

2. **TOML format migration** - Need to:
   - Document breaking change
   - Provide migration guide
   - Consider backward compatibility layer

3. **Config path parameter** - Need wrapper:
   ```python
   def load_config(path: str | Path) -> Config:
     path = Path(path).expanduser()
     # Clevis doesn't support custom paths directly
     # Would need to load TOML manually and pass to dataclass
   ```

### High Complexity Areas

1. **Breaking TOML format change** - Users have existing configs
2. **Integration testing** - All config resolution paths need testing

---

## Pros and Cons

### Advantages of Adopting Clevis

1. **Reduced maintenance** - 300+ lines of config code removed
2. **Better CLI support** - Automatic `--flag` generation
3. **Better error messages** - Helpful ConfigError with suggestions
4. **Nested configs** - Automatic handling of nested dataclasses
5. **Standard precedence** - Clear CLI > project > user > defaults
6. **Interpolation support** - `${VAR}` in TOML files
7. **Type-safe** - Dataclass-based with automatic type checking
8. **Upstream maintenance** - Bugs fixed in clevis benefit all users

### Disadvantages of Adopting Clevis

1. **Breaking TOML change** - `[client]` section not supported
2. **Lost features** - merge(), path return, prefix system
3. **New dependency** - dacite required, optional TOML parsers
4. **Less control** - Cannot customize precedence without forking
5. **Different paradigm** - CLI args highest, not explicit config
6. **Migration effort** - Users need to update config files

---

## Detailed Analysis

### Configuration Precedence

**Roomz Current:**
```
1. Explicit config parameter (highest)
2. Explicit config_path parameter
3. Prefixed environment variable (DEV_ROOMZ_*)
4. Unprefixed environment variable (ROOMZ_*)
5. ./roomz.toml (project)
6. ~/.roomz.toml (user)
7. Default Config() (lowest)
```

**Clevis:**
```
1. CLI arguments (highest)
2. ./{name}.toml (project)
3. ~/{name}.toml (user)
4. Dataclass defaults (lowest)
```

**Gap Analysis:**
- Clevis doesn't have explicit config/file parameter (uses CLI)
- Clevis puts project > user; roomz puts user > project
- Clevis doesn't have environment variable prefix system

### Environment Variable Support

**Roomz:**
```python
# Automatic prefix system
ROOMZ_PREFIX=DEV
DEV_ROOMZ_SERVER_URL=http://localhost:8000
# Falls back to ROOMZ_SERVER_URL if DEV_* not found
```

**Clevis (with envtoml):**
```toml
# TOML file with interpolation
server_url = "${ROOMZ_SERVER_URL}"
# Or with default:
server_url = "${ROOMZ_SERVER_URL|http://localhost:5000}"
```

**Clevis (via CLI):**
```bash
# CLI arguments override everything
roomz-cli --server-url http://localhost:8000
```

### Error Handling

**Roomz Current:**
```python
# Custom ConfigurationError
raise ConfigurationError(f"Failed to parse config file {config_path}: {e}")
```

**Clevis:**
```python
# Enhanced ConfigError with field path
except ConfigError as e:
  print(e.field_path)  # "database.host"
  print(e.message)     # "Required field has no value"
  # Message includes suggestions for fixing
```

---

## Migration Strategy

### Option A: Full Adoption (Recommended)

Replace roomz config with clevis, accept breaking changes:

1. **Phase 1: Internal migration**
   - Replace config.py with clevis wrapper
   - Update all config usage
   - Remove custom config code

2. **Phase 2: User communication**
   - Document TOML format change
   - Provide migration guide
   - Version bump with changelog

3. **Phase 3: Optional compatibility**
   - Add deprecation warning for `[client]` section
   - Support both formats for one version
   - Remove in next major version

**Effort:** 2-3 days  
**Lines removed:** ~300  
**Lines added:** ~50

### Option B: Partial Adoption

Use clevis internally but keep roomz Config class as wrapper:

1. Keep current API (`Config.load()`, `Config.auto_discover()`)
2. Use clevis for TOML parsing and validation
3. Handle TOML format conversion internally
4. Preserve environment variable prefix system

**Effort:** 3-4 days  
**Lines removed:** ~150  
**Lines added:** ~100

### Option C: No Adoption

Keep custom configuration implementation.

**Reasons to choose:**
- Cannot break TOML format
- Need prefix system for multi-environment setups
- Want explicit config parameter precedence
- Current implementation works well

**Effort:** 0 days  
**Technical debt:** Continue maintaining custom config code

---

## Recommendation

**Adopt clevis with Option A (Full Adoption)**

Rationale:
1. **Simplification** - Remove 300+ lines of config code
2. **Better CLI** - Automatic argument generation
3. **Upstream maintenance** - Less code to maintain
4. **Standard patterns** - Follow clevis conventions
5. **Type safety** - Better error messages

**Acceptable tradeoffs:**
- TOML format change is minor (remove `[client]` section)
- Environment prefix can be replaced with interpolation or CLI
- Config path parameter rarely used (can add wrapper if needed)

**Implementation steps:**
1. Add `clevis[tomlev]` dependency (for `${VAR|default}` support)
2. Create thin wrapper in `config.py`
3. Update tests
4. Document migration in changelog
5. Consider one-version compatibility layer for `[client]` section

---

## Code Examples

### Current Roomz Usage

```python
from roomz.client import AsyncClient, Config

# Explicit config
client = AsyncClient(config=Config(server_url="http://localhost:5000"))

# Auto-discover
client = AsyncClient()  # Discovers from env/toml

# With session caching
client = AsyncClient(
  config=Config(server_url="http://localhost:8000"),
  session_cache_file="~/.roomz/session.json"
)
```

### With Clevis Integration

```python
from roomz.client import AsyncClient
from roomz.client.config import get_client_config

# Explicit config (same as before)
config = Config(server_url="http://localhost:5000")
client = AsyncClient(config=config)

# Auto-discover with clevis
config = get_client_config("roomz")
client = AsyncClient(config=config)

# CLI arguments automatically supported
# python client.py --server-url http://localhost:8000 --display-name Alice
```

### Wrapper Implementation

```python
# src/roomz/client/config.py
from dataclasses import dataclass
from pathlib import Path
from typing import Self

from clevis import get_config, ConfigError

from roomz.client.exceptions import ConfigurationError


@dataclass
class Config:
  """Configuration for Roomz client."""
  server_url: str | None = None
  display_name: str | None = None

  @classmethod
  def load(cls, config_path: str | Path) -> Self:
    """Load configuration from a TOML file.
    
    Note: Clevis uses top-level TOML, not [client] section.
    """
    path = Path(config_path).expanduser()
    if not path.exists():
      raise FileNotFoundError(f"Config file not found: {path}")
    
    # Load with clevis (project=False to use only this file)
    try:
      return get_config(cls, name=path.stem, project=False, user=False)
    except ConfigError as e:
      raise ConfigurationError(f"Configuration error: {e}") from e

  @classmethod
  def auto_discover(cls) -> tuple[Self, Path | None]:
    """Auto-discover configuration from environment and files."""
    try:
      config = get_config(cls, name="roomz", user=True, project=True)
      # Clevis doesn't return path; we could add logic to find it
      return config, None
    except ConfigError as e:
      raise ConfigurationError(f"Configuration error: {e}") from e

  def validate(self) -> list[str]:
    """Validate configuration values."""
    errors: list[str] = []
    if self.server_url and not self.server_url.startswith(("http://", "https://")):
      errors.append("server_url must be http:// or https:// URL")
    if self.server_url and "@" in self.server_url:
      errors.append("server_url should not contain credentials")
    return errors


def get_client_config(name: str = "roomz", args: list[str] | None = None) -> Config:
  """Get configuration with roomz-specific handling.
  
  Args:
    name: Configuration name (default: "roomz")
    args: CLI arguments (default: sys.argv[1:])
  
  Returns:
    Configuration instance
  """
  try:
    return get_config(Config, name=name, args=args)
  except ConfigError as e:
    raise ConfigurationError(str(e)) from e
```

---

## Testing Impact

### Tests to Keep

- Config creation with values
- Config validation (URL format, credentials)
- Integration with AsyncClient

### Tests to Modify

- TOML loading (remove `[client]` section)
- Environment variable handling (use interpolation)
- Config discovery (simpler precedence)

### Tests to Add

- CLI argument parsing
- Environment variable interpolation
- Error message formatting

---

## Conclusion

Clevis is a well-designed package that addresses most of roomz's configuration needs. The primary adoption barrier is the TOML format change (removing `[client]` section), but this is manageable with proper documentation and version management.

**Final Recommendation:** Proceed with adoption using Option A (Full Adoption) with a one-version compatibility layer for existing TOML files.

**Estimated Effort:** 2-3 days  
**Risk Level:** Low to Medium (breaking TOML format)  
**Benefit:** Reduced maintenance, better CLI support, upstream bug fixes