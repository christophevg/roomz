# Consensus Report: I4-001 JWT Session Tokens

**Task**: I4-001 - Replace in-memory session storage with JWT tokens
**Date**: 2026-05-15
**Status**: Approved for Implementation

## Executive Summary

Both API Architect and Security Engineer have reviewed the JWT session implementation design. The consensus is that the approach is sound, with specific security mitigations that must be implemented.

### Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Token format | JWT (HS256) | Standard, well-supported, stateless |
| Token storage | httpOnly cookie | XSS protection, automatic transmission |
| Revocation strategy | Token version + ALLOWED_EMAILS | Balance between simplicity and security |
| Expiration | 30 days | User experience, acceptable for development |
| Channel token | UUID v4 in JWT | Unique per session, unpredictable |

## API Design Summary

### JWT Payload Structure

```json
{
  "sub": "user:<email>",
  "email": "user@example.com",
  "iat": 1713456000,
  "exp": 1716048000,
  "channel_token": "uuid-v4-random-token",
  "ver": 1
}
```

### Key API Changes

1. **POST /auth/request-magic-link**: Add ALLOWED_EMAILS validation (403 if not allowed)
2. **GET /auth/verify**: Issue JWT instead of in-memory session
3. **WebSocket Connection**: Validate JWT + check ALLOWED_EMAILS on every request

### Backward Compatibility

- **Web client**: No changes required (cookie-based auth unchanged)
- **Python client**: No changes required (session_token cookie unchanged)
- **Breaking changes**: None for existing clients

## Security Findings Summary

### Critical (Must Implement)

| Finding | Mitigation | Status |
|---------|------------|--------|
| JWT Token Revocation | Token version strategy + ALLOWED_EMAILS | Required |
| SECRET_KEY Management | Environment variable, 32+ characters | Required |
| Algorithm Confusion | Hardcode HS256, reject "none" | Required |

### High (Should Implement)

| Finding | Mitigation | Status |
|---------|------------|--------|
| ALLOWED_EMAILS Timing | Cache with 60s TTL, validate on every request | Required |
| Token Expiration | 30-day expiration with version revocation | Recommended |
| Channel Token Security | Unique per session, 256-bit entropy | Required |

### Medium (Best Practice)

| Finding | Mitigation | Status |
|---------|------------|--------|
| Cookie Security | Secure=True in production | Required for prod |
| WebSocket Timing | Validate before channel operations | Required |

## Implementation Requirements

### 1. Token Version Strategy

```python
# Minimal implementation for revocation
token_versions = {}  # {email: int}

def get_token_version(email: str) -> int:
    return token_versions.get(email, 1)

def revoke_all_tokens(email: str):
    token_versions[email] = token_versions.get(email, 0) + 1
```

### 2. SECRET_KEY Requirements

- Loaded from `JWT_SECRET_KEY` environment variable
- Minimum 32 characters (256 bits)
- Generate with: `python -c "import secrets; print(secrets.token_urlsafe(32))"`

### 3. Algorithm Hardcoding

```python
JWT_ALGORITHM = "HS256"  # Hardcoded, never from token

def validate_jwt(token: str) -> dict | None:
    payload = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM], ...)
```

### 4. ALLOWED_EMAILS Validation Points

1. Magic link request (POST /auth/request-magic-link)
2. JWT creation (GET /auth/verify)
3. WebSocket connection (on_connect)
4. All API endpoints (via validate_jwt)

### 5. Environment Variables

```bash
JWT_SECRET_KEY=<256-bit-secret>
ALLOWED_EMAILS=alice@example.com,bob@example.com
JWT_EXPIRY_DAYS=30
```

## File Changes

| File | Changes |
|------|---------|
| `app/auth.py` | Add JWT functions, remove SessionManager |
| `app/__init__.py` | Update WebSocket auth with JWT validation |
| `pyproject.toml` | Add PyJWT>=2.8.0 dependency |
| `src/roomz/client/async_client.py` | Optional: expose channel property |

## Test Requirements

### Security Tests (Must Pass)

- [ ] JWT algorithm hardcoded (cannot be changed)
- [ ] "none" algorithm rejected
- [ ] Expired JWT rejected
- [ ] JWT signature verification
- [ ] ALLOWED_EMAILS checked on every request
- [ ] Token version revocation works
- [ ] Email removal from ALLOWED_EMAILS revokes access

### Functional Tests (Must Pass)

- [ ] Login with magic link, get JWT cookie
- [ ] Server restart, reconnect still works
- [ ] Remove email from ALLOWED_EMAILS, access denied
- [ ] WebSocket connection with valid JWT
- [ ] WebSocket connection rejected with invalid JWT

## Risk Assessment

**Overall Risk**: MEDIUM-HIGH

The implementation is acceptable for development with the required mitigations. For production:

| Use Case | Acceptable | Notes |
|----------|------------|-------|
| Development | ✅ Yes | With mitigations |
| Internal tools | ✅ Yes | With mitigations |
| Public-facing | ⚠️ Requires review | Consider access + refresh tokens |
| High-security | ❌ No | Need additional controls |

## Approval

- **API Architect**: ✅ Approved - Design is sound and backward compatible
- **Security Engineer**: ✅ Approved - All critical findings have mitigations

## Next Steps

1. Phase 2.5: Create test stubs for TDD
2. Phase 3: Implementation by python-developer
3. Phase 5: Security review of implementation