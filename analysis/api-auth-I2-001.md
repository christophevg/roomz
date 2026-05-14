# API Analysis: Secret Dialog Authentication (I2-001)

**Task**: I2-001 - Secret Dialog Authentication
**Date**: 2026-05-14
**Analyst**: API Architect Agent

## Executive Summary

This document defines the authentication API for temporary user identification using a shared secret dialog. This is a minimal authentication mechanism for development and early testing, not a production authentication system.

## 1. Design Overview

### 1.1 Purpose

Provide temporary user identification without:
- Database persistence
- Email infrastructure
- Complex authentication flows

### 1.2 Scope

- Authentication dialog: display name + shared secret input
- Server validates secret against environment variable
- Generate temporary session token (JWT or opaque)
- Store token in localStorage
- Include user info in broadcast messages

### 1.3 Non-Goals

- Persistent user accounts
- Email verification
- Password reset
- Multi-factor authentication
- Session persistence across server restarts

## 2. Architecture Decisions

### 2.1 Authentication Strategy

**Decision**: Pre-shared secret with self-contained JWT tokens

**Rationale**:
- Simple to implement (no database required)
- Stateless validation (no server-side session storage)
- Token contains user identity (display name)
- Suitable for development/early testing
- Easy to migrate to real auth later

**Alternative Considered**: In-memory session store
- Requires session cleanup logic
- Sessions lost on server restart
- More complex state management

### 2.2 Token Format

**Decision**: Signed JWT (JSON Web Token)

**Rationale**:
- Self-contained (carries user info)
- Cryptographically signed (tamper-evident)
- Standard format (good library support)
- Stateless validation
- Configurable expiration

**Alternative Considered**: Opaque random token
- Requires server-side session storage
- Would need cleanup logic
- Simpler but less portable

### 2.3 WebSocket Authentication

**Decision**: Authenticate on WebSocket connection using auth parameter

**Rationale**:
- Socket.IO supports `auth` parameter on connection
- Token passed during handshake
- Connection rejected if token invalid
- Clean separation: connect once with credentials

**Alternative Considered**: Authenticate after connection
- Requires separate "authenticate" message
- Unauthenticated connections consume resources
- More complex state machine

## 3. API Endpoints

### 3.1 REST Endpoints

#### POST /auth/login

**Purpose**: Authenticate with shared secret and display name

**Request**:
```json
{
  "display_name": "string (1-50 chars, required)",
  "secret": "string (required)"
}
```

**Success Response (200 OK)**:
```json
{
  "status": "ok",
  "token": "jwt_token_here",
  "user": {
    "id": "user_uuid",
    "display_name": "User Display Name"
  },
  "expires_at": "2024-01-15T12:00:00Z"
}
```

**Error Responses**:

**400 Bad Request**:
```json
{
  "type": "https://roomz.local/errors/validation",
  "title": "Validation Error",
  "status": 400,
  "detail": "display_name is required and must be 1-50 characters",
  "fields": ["display_name"]
}
```

**401 Unauthorized**:
```json
{
  "type": "https://roomz.local/errors/invalid-secret",
  "title": "Invalid Secret",
  "status": 401,
  "detail": "The provided secret is incorrect."
}
```

**429 Too Many Requests**:
```json
{
  "type": "https://roomz.local/errors/rate-limited",
  "title": "Rate Limited",
  "status": 429,
  "detail": "Too many authentication attempts. Please wait before retrying.",
  "retry_after": 60
}
```

#### POST /auth/verify

**Purpose**: Verify token validity and get user info

**Request Headers**:
- `Authorization: Bearer <token>`

**Success Response (200 OK)**:
```json
{
  "status": "ok",
  "user": {
    "id": "user_uuid",
    "display_name": "User Display Name"
  },
  "expires_at": "2024-01-15T12:00:00Z"
}
```

**Error Responses**:

**401 Unauthorized**:
```json
{
  "type": "https://roomz.local/errors/invalid-token",
  "title": "Invalid Token",
  "status": 401,
  "detail": "Token is invalid or expired."
}
```

#### POST /auth/logout

**Purpose**: Invalidate current session

**Request Headers**:
- `Authorization: Bearer <token>`

**Success Response (200 OK)**:
```json
{
  "status": "ok"
}
```

**Note**: For JWT tokens without server-side storage, logout is primarily client-side (token removal). This endpoint exists for API consistency and future extensibility.

### 3.2 WebSocket Authentication

#### Connection Handshake

**Client Connection**:
```javascript
const socket = io('/socket.io', {
  auth: {
    token: 'jwt_token_here'
  }
});
```

**Server Validation**:
1. Extract token from `auth.token` parameter
2. Validate JWT signature and expiration
3. If valid: accept connection, store user info in session
4. If invalid: reject connection with error message

**Connection Success**:
- WebSocket connection established
- User info attached to socket session
- Client receives `authenticated` event

**Connection Failure**:
- Connection rejected
- Client receives `connect_error` with error details

**Error Format**:
```javascript
// Socket.IO connect_error event
{
  message: "Authentication failed: invalid or expired token",
  data: {
    type: "https://roomz.local/errors/invalid-token",
    title: "Invalid Token"
  }
}
```

### 3.3 WebSocket Events

#### Event: `authenticated`

**Direction**: Server → Client

**Purpose**: Confirm successful authentication

**Payload**:
```json
{
  "user": {
    "id": "user_uuid",
    "display_name": "User Display Name"
  },
  "server_time": "2024-01-15T10:30:00Z"
}
```

**Timing**: Sent immediately after successful connection.

## 4. WebSocket Message Protocol Changes

### 4.1 Modified Events

#### Event: `message`

**Current (I1-001)**:
```json
{
  "id": "message_uuid",
  "sid": "socket_id",
  "content": "Hello world",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

**New (I2-001)**:
```json
{
  "id": "message_uuid",
  "user": {
    "id": "user_uuid",
    "display_name": "Alice"
  },
  "content": "Hello world",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

**Changes**:
- Replace `sid` with `user` object
- Include `user.id` for stable identification across reconnections
- Include `user.display_name` for human-readable display

#### Event: `user_joined`

**Current (I1-001)**:
```json
{
  "sid": "socket_id",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

**New (I2-001)**:
```json
{
  "user": {
    "id": "user_uuid",
    "display_name": "Alice"
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

**Changes**:
- Replace `sid` with `user` object
- Include display name for welcome message display

#### Event: `user_left`

**Current (I1-001)**:
```json
{
  "sid": "socket_id",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

**New (I2-001)**:
```json
{
  "user": {
    "id": "user_uuid",
    "display_name": "Alice"
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

**Changes**:
- Replace `sid` with `user` object
- Include display name for departure message display

### 4.2 Backward Compatibility

**Consideration**: Should I1-001 format still be supported?

**Recommendation**: No backward compatibility needed. This is development phase, not production. Breaking changes are acceptable before first release.

## 5. Token Design

### 5.1 JWT Claims

```json
{
  "sub": "user_uuid",
  "name": "Display Name",
  "iat": 1705315800,
  "exp": 1705319400,
  "iss": "roomz",
  "aud": "roomz-client"
}
```

**Claims**:
- `sub`: Subject - unique user identifier (UUID v4)
- `name`: Display name for user
- `iat`: Issued at (Unix timestamp)
- `exp`: Expiration time (Unix timestamp)
- `iss`: Issuer - "roomz"
- `aud`: Audience - "roomz-client"

### 5.2 Token Lifetime

**Session Token**: 24 hours default

**Configuration**:
- `AUTH_TOKEN_EXPIRY_HOURS`: Environment variable (default: 24)
- Token expiration enforced by JWT validation
- Client should store expiration time and refresh proactively

### 5.3 Token Security

**Signing Algorithm**: HS256 (HMAC with SHA-256)

**Secret Key**:
- Development: Hardcoded in code or environment variable
- Production: Secure random key from environment variable
- `JWT_SECRET_KEY`: Environment variable (256+ bits recommended)

**Key Rotation**:
- Support multiple keys during rotation period
- New key becomes primary, old key still validates
- Implementation: `JWT_SECRET_KEY` and optional `JWT_SECRET_KEY_PREVIOUS`

## 6. Rate Limiting

### 6.1 Login Endpoint

**Limit**: 10 requests per IP per minute

**Implementation**:
- In-memory rate limit counter (acceptable for development)
- Reset counter every minute
- Return `Retry-After` header on limit exceeded

**Configuration**:
- `AUTH_RATE_LIMIT_PER_MINUTE`: Environment variable (default: 10)

### 6.2 Rate Limit Response

**HTTP Headers**:
```
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1705315860
Retry-After: 45
```

## 7. Error Handling

### 7.1 Error Types

| Type | Title | Status | When |
|------|-------|--------|------|
| `validation` | Validation Error | 400 | Invalid input format |
| `invalid-secret` | Invalid Secret | 401 | Wrong secret provided |
| `invalid-token` | Invalid Token | 401 | Token validation failed |
| `rate-limited` | Rate Limited | 429 | Too many requests |
| `server-error` | Server Error | 500 | Unexpected error |

### 7.2 Error Response Format (RFC 7807)

All errors follow RFC 7807 Problem Details format:

```json
{
  "type": "https://roomz.local/errors/{error-type}",
  "title": "Human-readable title",
  "status": 400,
  "detail": "Specific error details",
  "instance": "/auth/login"
}
```

## 8. Session Management

### 8.1 Client-Side Storage

**localStorage Keys**:
- `roomz_token`: JWT token string
- `roomz_user`: User info object `{id, display_name}`
- `roomz_expires_at`: Token expiration timestamp (ISO 8601)

### 8.2 Token Validation Flow

```
Client Start → Check localStorage
  ↓
Token exists?
  → Yes → Verify token with server (POST /auth/verify)
    → Valid → Connect WebSocket with token
    → Invalid → Show login dialog
  → No → Show login dialog
```

### 8.3 Automatic Token Refresh

**Not Implemented in I2-001**: Token refresh is deferred to I5-003.

For I2-001, clients handle expiration by:
1. Checking `expires_at` before connection
2. Prompting for re-authentication when expired
3. Clearing localStorage on logout

## 9. Security Considerations

### 9.1 Threat Model

**In Scope for I2-001**:
- Prevent casual access (shared secret blocks random users)
- Identify users by display name (auditability)
- Token tampering prevention (JWT signature)

**Out of Scope for I2-001**:
- Account takeover protection (no persistent accounts)
- Session hijacking mitigation (HTTPS only, secure cookies later)
- Brute force protection (basic rate limiting only)
- Persistent user tracking (no database)

### 9.2 Security Measures

**Implemented**:
1. Shared secret validation (environment variable `AUTH_SECRET`)
2. JWT signature validation (prevents token tampering)
3. Token expiration (limits exposure window)
4. Rate limiting on login endpoint (prevents brute force)
5. HTTPS enforcement (production deployment)

**Not Implemented (Future)**:
1. Token refresh mechanism
2. Session revocation
3. IP-based rate limiting per user
4. CAPTCHA on repeated failures
5. Secure session cookie alternative

### 9.3 Recommendations for Production

When moving to production (I5-xxx):
1. Replace shared secret with magic link authentication
2. Add MongoDB session persistence
3. Implement token refresh
4. Add CSRF protection
5. Use secure HTTP-only cookies for token storage
6. Implement proper session revocation

### 9.4 Environment Variables

**Required**:
```
AUTH_SECRET=<shared-secret-string>
JWT_SECRET_KEY=<256-bit-random-key>
```

**Optional**:
```
AUTH_TOKEN_EXPIRY_HOURS=24
AUTH_RATE_LIMIT_PER_MINUTE=10
```

**Development Defaults** (not for production):
```
AUTH_SECRET=development-secret-change-me
JWT_SECRET_KEY=development-key-256-bits-please-change-me
```

## 10. Implementation Notes

### 10.1 Backend Changes Required

**File**: `app/__init__.py`

1. Add JWT library dependency (`PyJWT`)
2. Add authentication helper functions
3. Add `/auth/login` route handler
4. Add `/auth/verify` route handler
5. Add `/auth/logout` route handler
6. Modify `on_connect` to validate JWT from auth parameter
7. Modify `on_message` to use user info from session
8. Modify `user_joined` and `user_left` events to use user info
9. Add rate limiting middleware for `/auth/login`

**New Files**:
- `app/auth.py`: Authentication utilities (JWT, rate limiting, validation)
- `app/models.py`: Data models (User, Token payload)

### 10.2 Frontend Changes Required

**File**: `app/pages/chat/chat.js`

1. Add authentication check on component mount
2. Show login dialog if not authenticated
3. Send `POST /auth/login` with display name and secret
4. Store token in localStorage
5. Pass token in Socket.IO connection `auth` parameter
6. Handle `authenticated` event
7. Handle `connect_error` event
8. Update message display to show `user.display_name`
9. Update system messages to show user names

**New Files**:
- `app/components/LoginDialog.js`: Login dialog component

### 10.3 Migration Path

**From I1-001 to I2-001**:
1. Deploy new backend with authentication
2. Existing clients will fail to connect (no token)
3. Frontend shows login dialog
4. User enters display name and secret
5. Authentication succeeds, normal operation resumes

**Note**: This is a breaking change. Acceptable in development phase.

## 11. OpenAPI Specification

The following OpenAPI spec will be created in `docs/openapi.yaml`:

```yaml
openapi: 3.1.0
info:
  title: Roomz Authentication API
  version: 0.1.0
  description: |
    Temporary authentication API for development phase.
    Uses shared secret and JWT tokens for user identification.

servers:
  - url: http://localhost:5000
    description: Development server

paths:
  /auth/login:
    post:
      summary: Authenticate with shared secret
      operationId: login
      tags: [Authentication]
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/LoginRequest'
      responses:
        '200':
          description: Authentication successful
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/LoginResponse'
        '400':
          description: Validation error
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Error'
        '401':
          description: Invalid secret
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Error'
        '429':
          description: Rate limited
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Error'

  /auth/verify:
    post:
      summary: Verify token validity
      operationId: verifyToken
      tags: [Authentication]
      security:
        - BearerAuth: []
      responses:
        '200':
          description: Token is valid
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/VerifyResponse'
        '401':
          description: Invalid token
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Error'

  /auth/logout:
    post:
      summary: Logout and invalidate session
      operationId: logout
      tags: [Authentication]
      security:
        - BearerAuth: []
      responses:
        '200':
          description: Logout successful
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Success'

components:
  schemas:
    LoginRequest:
      type: object
      required: [display_name, secret]
      properties:
        display_name:
          type: string
          minLength: 1
          maxLength: 50
          description: User display name
        secret:
          type: string
          description: Shared secret for authentication

    LoginResponse:
      type: object
      properties:
        status:
          type: string
          enum: [ok]
        token:
          type: string
          description: JWT token for subsequent requests
        user:
          $ref: '#/components/schemas/User'
        expires_at:
          type: string
          format: date-time
          description: Token expiration time

    VerifyResponse:
      type: object
      properties:
        status:
          type: string
          enum: [ok]
        user:
          $ref: '#/components/schemas/User'
        expires_at:
          type: string
          format: date-time

    User:
      type: object
      properties:
        id:
          type: string
          format: uuid
          description: Unique user identifier
        display_name:
          type: string
          description: User display name

    Success:
      type: object
      properties:
        status:
          type: string
          enum: [ok]

    Error:
      type: object
      required: [type, title, status]
      properties:
        type:
          type: string
          format: uri
          description: Error type URI
        title:
          type: string
          description: Human-readable error title
        status:
          type: integer
          description: HTTP status code
        detail:
          type: string
          description: Detailed error message
        instance:
          type: string
          description: Request path

  securitySchemes:
    BearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT
```

## 12. Testing Strategy

### 12.1 Unit Tests

**Authentication Module (`app/auth.py`)**:
- Token generation with valid claims
- Token validation success
- Token validation failure (expired)
- Token validation failure (invalid signature)
- Token validation failure (malformed)
- Rate limit counter logic

**Models (`app/models.py`)**:
- User model validation
- Display name constraints (length, characters)
- Token payload serialization

### 12.2 Integration Tests

**Login Endpoint**:
- Successful login returns token
- Invalid secret returns 401
- Missing fields return 400
- Rate limiting returns 429

**Verify Endpoint**:
- Valid token returns user info
- Invalid token returns 401
- Expired token returns 401

**WebSocket Authentication**:
- Connection with valid token succeeds
- Connection with invalid token fails
- Connection without token fails
- Authenticated user info in socket session

**Message Events**:
- Message includes user info
- User joined event includes display name
- User left event includes display name

### 12.3 End-to-End Tests

**User Flow**:
1. Open app (unauthenticated)
2. See login dialog
3. Enter display name and secret
4. Submit login
5. Receive token
6. WebSocket connects automatically
7. Send message
8. See own message with display name
9. Open second tab
10. Login with different name
11. See join notification with display name
12. See messages from both users with names

## 13. Action Items

### Backend Implementation (Priority Order)

1. **Add dependencies**:
   - Add `PyJWT` to `pyproject.toml`
   - Add `python-dotenv` for environment variables (if not present)

2. **Create authentication module** (`app/auth.py`):
   - JWT token generation
   - JWT token validation
   - Rate limiting logic
   - Secret validation

3. **Create data models** (`app/models.py`):
   - User model
   - Token payload model
   - Login request/response models

4. **Add HTTP routes**:
   - `POST /auth/login`
   - `POST /auth/verify`
   - `POST /auth/logout`

5. **Modify WebSocket handlers**:
   - `on_connect`: Add JWT validation
   - `on_disconnect`: Clean up user session
   - `on_message`: Use user info from session

6. **Add environment configuration**:
   - Create `.env.example` with required variables
   - Update documentation

### Frontend Implementation (Priority Order)

1. **Create login dialog component**:
   - Display name input
   - Secret input
   - Submit button
   - Error display

2. **Add authentication logic**:
   - Check localStorage for existing token
   - Validate token on startup
   - Show login dialog if not authenticated
   - Handle login submission

3. **Modify WebSocket connection**:
   - Pass token in auth parameter
   - Handle `authenticated` event
   - Handle `connect_error` event

4. **Update message display**:
   - Show `user.display_name` instead of `sid`
   - Update system messages to use display names

### Documentation

1. **Update API documentation**:
   - Create `docs/openapi.yaml` with authentication endpoints

2. **Update README**:
   - Add authentication flow description
   - Add environment variable setup

3. **Create development guide**:
   - How to set `AUTH_SECRET`
   - How to test authentication

## 14. Conclusion

This API design provides a simple but secure authentication mechanism for the development phase. The shared secret approach allows controlled access without requiring email infrastructure, while JWT tokens provide stateless authentication suitable for WebSocket connections.

The design is intentionally temporary and will be replaced with proper magic link authentication in Iteration 5. However, the API contracts are designed to be compatible with that transition (same endpoints, same token format, same user info structure).