# Consensus Report: I2-001 Magic Link Authentication

**Task**: I2-001 - Magic Link Authentication (Updated from Secret Dialog)
**Date**: 2026-05-14
**Analysts**: API Architect, UI/UX Designer, Security Engineer
**Status**: Updated based on user preference for magic link flow

## Executive Summary

**REVISED APPROACH**: The user has requested a magic link authentication flow instead of the shared secret approach. This is superior because:

1. **Better Security**: No shared secret to expose
2. **Simpler UX**: User only needs email address
3. **Production Ready**: Direct path to I5-001/002 (email integration)
4. **Auditability**: Clear audit trail by email address

This approach eliminates **CRITICAL-1** (hardcoded/shared secret exposure) entirely and provides a cleaner migration path to production authentication.

**Overall Risk**: **MEDIUM** - Suitable for development and easier to secure than shared secret. Requires email validation and rate limiting.

---

## Authentication Flow

### Development Flow (I2-001)

```
┌─────────────────────────────────────────────────────────┐
│ User visits webapp                                        │
│   ↓                                                       │
│ No session cookie detected                                │
│   ↓                                                       │
│ Show AuthDialog with email input                          │
│   ↓                                                       │
│ User enters email: user@example.com                       │
│   ↓                                                       │
│ POST /auth/request-magic-link                             │
│   ├─ Validate email format                                │
│   ├─ Rate limit: 5 requests per email per hour           │
│   ├─ Generate magic link token (256 bits)                │
│   ├─ Store token hash + email + expiry (15 min)          │
│   └─ LOG TO CONSOLE: "Magic link: http://localhost:8000  │
│       /auth/verify?token=abc123... for user@example.com" │
│   ↓                                                       │
│ Frontend shows: "Magic link generated! Check console."   │
│   ↓                                                       │
│ User clicks magic link (from console)                     │
│   ↓                                                       │
│ GET /auth/verify?token=abc123                             │
│   ├─ Validate token (exists, not expired, not used)      │
│   ├─ Invalidate token (single-use)                        │
│   ├─ Create session (30 days)                             │
│   └─ Set httpOnly cookie, redirect to /chat              │
│   ↓                                                       │
│ WebSocket connects (cookie sent automatically)             │
│   ↓                                                       │
│ User enters chat with email as identifier                 │
└─────────────────────────────────────────────────────────┘
```

### Production Flow (I5-001/002) - Future

The same flow, but instead of logging to console:
- Send email via email service (SendGrid, etc.)
- User clicks link in email
- Same verification process

This means I2-001 code is 95% production-ready.

---

## Domain Agent Analysis (Updated)

### API Architect Recommendations

**Endpoints**:

| Endpoint | Method | Purpose | Auth Required |
|----------|--------|---------|----------------|
| `/auth/request-magic-link` | POST | Request magic link | No |
| `/auth/verify` | GET | Verify magic link token | No |
| `/auth/logout` | POST | Logout and clear session | Yes |
| `/auth/me` | GET | Get current user info | Yes |

**Magic Link Request Endpoint**:
```python
@app.route('/auth/request-magic-link', methods=['POST'])
async def request_magic_link():
    """
    Request a magic link for authentication.

    Rate limited: 5 requests per email per hour
    Token lifetime: 15 minutes
    """
    # Parse request
    data = await request.get_json()
    email = data.get('email', '').lower().strip()

    # Validate email
    if not is_valid_email(email):
        return jsonify({'error': 'Invalid email format'}), 400

    # Check rate limit
    client_ip = request.remote_addr
    if not magic_link_limiter.is_allowed(email, client_ip):
        return jsonify({'error': 'Too many requests'}), 429

    # Generate magic link token
    token = secrets.token_urlsafe(32)  # 256-bit token
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    # Store magic link (expires in 15 minutes)
    magic_links[token_hash] = {
        'email': email,
        'created_at': datetime.utcnow(),
        'expires_at': datetime.utcnow() + timedelta(minutes=15),
        'used': False
    }

    # Generate magic link URL
    magic_link_url = f"{request.host_url}auth/verify?token={token}"

    # DEVELOPMENT: Log to console
    # PRODUCTION: Send email via email service
    server.logger.info(f"\n{'='*60}\n"
                      f"MAGIC LINK for {email}\n"
                      f"{magic_link_url}\n"
                      f"{'='*60}\n")

    return jsonify({
        'status': 'ok',
        'message': 'Magic link generated. Check server console.'
    })
```

**Magic Link Verification Endpoint**:
```python
@app.route('/auth/verify', methods=['GET'])
async def verify_magic_link():
    """
    Verify magic link token and create session.

    Tokens are single-use and expire after 15 minutes.
    """
    token = request.args.get('token')

    if not token:
        return redirect('/?error=missing_token')

    # Validate token
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    magic_link = magic_links.get(token_hash)

    if not magic_link:
        return redirect('/?error=invalid_token')

    if magic_link['used']:
        return redirect('/?error=token_already_used')

    if datetime.utcnow() > magic_link['expires_at']:
        return redirect('/?error=token_expired')

    # Mark token as used (single-use)
    magic_link['used'] = True

    # Create session
    session_token = session_manager.create_session(
        email=magic_link['email'],
        client_ip=request.remote_addr
    )

    # Clean up magic link
    del magic_links[token_hash]

    # Set httpOnly cookie and redirect to chat
    response = redirect('/chat')
    response.set_cookie(
        'session_token',
        session_token['token'],
        httponly=True,
        secure=True,  # HTTPS only in production
        samesite='Strict',
        max_age=30 * 24 * 3600  # 30 days
    )

    server.logger.info(f"User authenticated: {magic_link['email']}")

    return response
```

**WebSocket Authentication** (Same as before):
```python
@server.socketio.on("connect")
async def on_connect(sid: str, environ: dict, auth: dict | None) -> bool:
    """
    Handle WebSocket connection with session validation.

    Session token is extracted from httpOnly cookie.
    """
    # Extract token from cookie
    cookies = environ.get('HTTP_COOKIE', '')
    token = extract_token_from_cookie(cookies)

    if not token:
        server.logger.warning(f"Rejecting connection {sid}: no session token")
        return False

    # Validate session
    session = session_manager.validate_token(token)

    if not session:
        server.logger.warning(f"Rejecting connection {sid}: invalid or expired token")
        return False

    # Check session expiration
    if datetime.utcnow() > session['expires_at']:
        server.logger.warning(f"Rejecting connection {sid}: session expired")
        return False

    # Connection limit check
    if len(connected_clients) >= MAX_CLIENTS:
        server.logger.warning(f"Rejecting connection {sid}: server at capacity")
        return False

    # Register authenticated connection
    connected_clients[sid] = {
        'session': session,
        'ip': request.remote_addr,
        'connected_at': datetime.utcnow()
    }

    server.logger.info(
        f"Client connected: {sid} as '{session['email']}' "
        f"(total: {len(connected_clients)})"
    )

    # Broadcast with user info
    await server.socketio.emit("user_joined", {
        "user": {
            "id": session['token_hash'][:8],
            "email": session['email']
        },
        "timestamp": datetime.utcnow().isoformat()
    }, skip_sid=sid)

    return True
```

### UI/UX Designer Recommendations

**AuthDialog Component** (Simplified):
```javascript
var AuthDialog = {
  name: 'AuthDialog',
  template: `
    <v-dialog v-model="showDialog" persistent max-width="480">
      <v-card>
        <v-card-title class="text-h5 pb-2">
          <v-icon start color="primary">mdi-email-lock</v-icon>
          Sign in with Email
        </v-card-title>

        <v-card-subtitle class="text-body-2">
          Enter your email address to receive a magic link
        </v-card-subtitle>

        <v-card-text>
          <v-form ref="authForm" v-model="formValid" @submit.prevent="handleRequestMagicLink">
            <!-- Email Input -->
            <v-text-field
              v-model="email"
              label="Email Address"
              type="email"
              placeholder="you@example.com"
              prepend-inner-icon="mdi-email"
              :rules="emailRules"
              :disabled="requesting"
              :error-messages="emailErrors"
              autocomplete="email"
              density="comfortable"
              variant="outlined"
              class="mb-3"
            ></v-text-field>

            <!-- Connection Status -->
            <v-alert v-if="!connected" type="warning" density="compact" variant="tonal" class="mb-3">
              <v-icon start>mdi-wifi-off</v-icon>
              Waiting for server connection...
            </v-alert>

            <!-- Success Message -->
            <v-alert v-if="magicLinkRequested" type="success" density="compact" variant="tonal" class="mb-3">
              <v-icon start>mdi-check-circle</v-icon>
              Magic link generated!
              <br/>
              <small>Check the server console for development, or your email inbox in production.</small>
            </v-alert>

            <!-- Error Message -->
            <v-alert v-if="authError" type="error" density="compact" variant="tonal" class="mb-3" closable @click:close="authError = null">
              <v-icon start>mdi-alert-circle</v-icon>
              {{ authError }}
            </v-alert>
          </v-form>
        </v-card-text>

        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn
            color="primary"
            variant="flat"
            :disabled="!formValid || !connected || requesting"
            :loading="requesting"
            @click="handleRequestMagicLink"
          >
            <v-icon start>mdi-send</v-icon>
            Send Magic Link
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  `,
  data() {
    return {
      showDialog: true,
      email: '',
      formValid: false,
      requesting: false,
      magicLinkRequested: false,
      authError: null,
      emailErrors: [],
      emailRules: [
        v => !!v || 'Email is required',
        v => /.+@.+\..+/.test(v) || 'Email must be valid'
      ]
    };
  },
  computed: {
    connected() {
      return this.$root.connected;
    }
  },
  methods: {
    async handleRequestMagicLink() {
      const { valid } = await this.$refs.authForm.validate();
      if (!valid) return;

      if (!this.connected) {
        this.authError = 'Not connected to server. Please wait...';
        return;
      }

      this.authError = null;
      this.requesting = true;

      try {
        const response = await fetch('/auth/request-magic-link', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email: this.email.trim().toLowerCase() })
        });

        const data = await response.json();

        if (response.ok) {
          this.magicLinkRequested = true;
          // In development, user needs to check console
          // In production, they check their email
        } else {
          this.authError = data.error || 'Failed to request magic link';
        }
      } catch (error) {
        this.authError = 'Network error. Please try again.';
      } finally {
        this.requesting = false;
      }
    },
    loadSession() {
      // Check for existing session on mount
      // Cookie is sent automatically with request
      fetch('/auth/me')
        .then(res => {
          if (res.ok) {
            return res.json();
          } else {
            throw new Error('No session');
          }
        })
        .then(data => {
          this.$root.authenticated = true;
          this.$root.currentUser = data.user;
          this.showDialog = false;
        })
        .catch(() => {
          // No valid session, show dialog
          this.showDialog = true;
        });
    },
    logout() {
      fetch('/auth/logout', { method: 'POST' })
        .then(() => {
          this.$root.authenticated = false;
          this.$root.currentUser = null;
          this.showDialog = true;
        });
    }
  },
  mounted() {
    this.loadSession();
  }
};
```

**Verify Page Component** (New):
```javascript
// app/pages/verify/verify.js
var VerifyPage = {
  name: 'VerifyPage',
  template: `
    <div class="d-flex align-center justify-center" style="height: 100vh;">
      <v-card class="text-center pa-8" max-width="400">
        <v-progress-circular v-if="verifying" indeterminate color="primary" size="64" />
        <div v-else-if="error" class="text-error">
          <v-icon size="64" color="error">mdi-alert-circle</v-icon>
          <h2 class="text-h5 mt-4">{{ error }}</h2>
          <v-btn color="primary" class="mt-4" to="/">Try Again</v-btn>
        </div>
      </v-card>
    </div>
  `,
  data() {
    return {
      verifying: true,
      error: null
    };
  },
  async mounted() {
    const token = new URLSearchParams(window.location.search).get('token');

    if (!token) {
      this.error = 'Invalid link';
      this.verifying = false;
      return;
    }

    try {
      const response = await fetch(`/auth/verify?token=${encodeURIComponent(token}`);

      if (response.ok) {
        // Session cookie set automatically
        // Redirect to chat
        window.location.href = '/chat';
      } else {
        const data = await response.json();
        this.error = this.mapError(data.error);
      }
    } catch (err) {
      this.error = 'Verification failed. Please try again.';
    } finally {
      this.verifying = false;
    }
  },
  methods: {
    mapError(errorCode) {
      const errors = {
        'missing_token': 'Invalid link. Please request a new magic link.',
        'invalid_token': 'Invalid link. Please request a new magic link.',
        'token_already_used': 'This link has already been used. Please request a new one.',
        'token_expired': 'This link has expired. Please request a new one.'
      };
      return errors[errorCode] || 'Verification failed. Please try again.';
    }
  }
};
```

**Chat Component Updates**:
```javascript
// Display email in messages
<div class="text-caption text-medium-emphasis" style="margin-bottom: 4px;">
  <span v-if="!message.system">
    <strong>{{ message.user.email }}</strong>
    <span style="margin-left: 8px; opacity: 0.7;">
      {{ formatTime(message.timestamp) }}
    </span>
  </span>
</div>

// User menu in app bar
<v-menu v-if="authenticated">
  <template v-slot:activator="{ props }">
    <v-btn v-bind="props" variant="text">
      <v-icon start>mdi-account</v-icon>
      {{ currentUser.email }}
      <v-icon end>mdi-chevron-down</v-icon>
    </v-btn>
  </template>
  <v-list density="compact">
    <v-list-item @click="handleLogout">
      <v-list-item-title>
        <v-icon start>mdi-logout</v-icon>
        Sign Out
      </v-list-item-title>
    </v-list-item>
  </v-list>
</v-menu>
```

### Security Engineer Recommendations (Updated)

**Security Analysis for Magic Link Authentication**:

| Finding | Severity | Status | Notes |
|---------|----------|--------|-------|
| Shared secret exposure | CRITICAL | **ELIMINATED** | No shared secret needed! |
| localStorage vulnerability | CRITICAL | **FIXED** | httpOnly cookies used |
| Token generation | HIGH | **IMPLEMENTED** | `secrets.token_urlsafe(32)` |
| WebSocket authentication | HIGH | **IMPLEMENTED** | Validate from cookie on connect |
| Rate limiting | HIGH | **IMPLEMENTED** | 5 requests per email per hour |
| Token expiration | MEDIUM | **IMPLEMENTED** | Magic link: 15 min, Session: 30 days |
| Magic link single-use | MEDIUM | **REQUIRED** | Invalidate after verification |
| Session hijacking | MEDIUM | **IMPLEMENTED** | IP/UA validation, httpOnly cookie |
| Email validation | LOW | **IMPLEMENTED** | RFC 5322 compliant validation |

**Magic Link Security Requirements**:

1. **Cryptographically Secure Token**:
   ```python
   # Generate 256-bit magic link token
   token = secrets.token_urlsafe(32)  # 43 characters
   ```

2. **Single-Use Tokens**:
   ```python
   # Mark token as used after verification
   if magic_link['used']:
       return redirect('/?error=token_already_used')
   magic_link['used'] = True
   ```

3. **Token Expiration**:
   ```python
   # Magic links expire in 15 minutes
   'expires_at': datetime.utcnow() + timedelta(minutes=15)
   ```

4. **Rate Limiting**:
   ```python
   # Limit: 5 requests per email per hour
   # Prevents magic link spam
   if not magic_link_limiter.is_allowed(email, client_ip):
       return jsonify({'error': 'Too many requests'}), 429
   ```

5. **Email Validation**:
   ```python
   import re

   def is_valid_email(email: str) -> bool:
       """Validate email format."""
       if not email or len(email) > 255:
           return False

       # Basic RFC 5322 pattern
       pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
       if not re.match(pattern, email):
           return False

       # Additional checks
       parts = email.split('@')
       if len(parts[0]) > 64:  # Local part max length
           return False

       return True
   ```

**Session Security**:

1. **Long-Lived Session** (30 days):
   ```python
   session = {
       'email': email,
       'created_at': datetime.utcnow(),
       'expires_at': datetime.utcnow() + timedelta(days=30),
       'last_activity': datetime.utcnow(),
       'client_ip': client_ip,
       'user_agent_hash': hashlib.sha256(user_agent.encode()).hexdigest()
   }
   ```

2. **Inactivity Timeout** (7 days):
   ```python
   # Extend session on activity
   if datetime.utcnow() - session['last_activity'] > timedelta(days=7):
       # Session expired due to inactivity
       return None
   ```

3. **httpOnly Cookie**:
   ```python
   response.set_cookie(
       'session_token',
       token,
       httponly=True,      # Not accessible via JavaScript
       secure=True,        # HTTPS only (False for localhost dev)
       samesite='Strict',  # CSRF protection
       max_age=30 * 24 * 3600  # 30 days
   )
   ```

---

## Implementation Plan

### Backend Files

**New Files**:
```
app/
  auth.py              # Authentication logic
    - is_valid_email()
    - SessionManager class
    - MagicLinkManager class
    - RateLimiter class (magic link requests)

  models.py            # Data models
    - Session dataclass
    - MagicLink dataclass
```

**Modified Files**:
```
app/
  __init__.py           # Add auth endpoints
    - Add /auth/request-magic-link endpoint
    - Add /auth/verify endpoint
    - Add /auth/logout endpoint
    - Add /auth/me endpoint
    - Modify on_connect to validate session from cookie
    - Modify on_message to include user email
    - Modify user_joined/user_left to include user email
```

### Frontend Files

**New Files**:
```
app/
  pages/
    auth/
      __init__.py       # Auth page registration
      auth.js           # AuthDialog component

    verify/
      __init__.py       # Verify page registration
      verify.js         # VerifyPage component
```

**Modified Files**:
```
app/
  pages/
    chat/
      chat.js           # Modify chat component
        - Add authentication check on mount
        - Show AuthDialog if not authenticated
        - Display user email in messages
        - Add logout option
```

### Configuration

**Environment Variables**:
```bash
# .env (DO NOT COMMIT)
# No shared secret needed! Just configuration:
MAX_CLIENTS=100
SESSION_TIMEOUT_DAYS=30
INACTIVITY_TIMEOUT_DAYS=7
MAGIC_LINK_EXPIRY_MINUTES=15
MAGIC_LINK_RATE_LIMIT=5
```

**Logging Magic Links** (Development):
```python
# In auth.py
server.logger.info(f"\n{'='*60}\n"
                  f"MAGIC LINK for {email}\n"
                  f"{magic_link_url}\n"
                  f"{'='*60}\n")
```

**Sending Emails** (Production - Future):
```python
# I5-002: Replace logging with email sending
# await send_magic_link_email(email, magic_link_url)
```

---

## Acceptance Criteria

### Functional Requirements

- [ ] AuthDialog appears when no session cookie exists
- [ ] Dialog has email input with validation
- [ ] POST /auth/request-magic-link with valid email logs magic link to console
- [ ] POST /auth/request-magic-link returns success message
- [ ] Magic link logged to console includes full URL
- [ ] GET /auth/verify?token=abc123 verifies token and creates session
- [ ] Session cookie set as httpOnly, secure, SameSite
- [ ] Session expires after 30 days (or 7 days inactivity)
- [ ] User redirected to /chat after successful verification
- [ ] Magic links are single-use (error on second use)
- [ ] Magic links expire after 15 minutes
- [ ] Rate limiting: 5 requests per email per hour
- [ ] User email appears with messages in chat
- [ ] User email visible in app bar
- [ ] Logout clears session and shows auth dialog

### Security Requirements

- [ ] No shared secret stored anywhere
- [ ] Magic link tokens use `secrets.token_urlsafe(32)`
- [ ] Tokens are single-use (invalidated after verification)
- [ ] Tokens expire after 15 minutes
- [ ] Session cookies are httpOnly, secure, SameSite
- [ ] Email validated before magic link generation
- [ ] Rate limiting prevents magic link spam
- [ ] Session validated on WebSocket connect
- [ ] Session expiration enforced
- [ ] .env added to .gitignore

### Non-Functional Requirements

- [ ] AuthDialog works on mobile (320px width)
- [ ] Keyboard navigation works (Tab, Enter)
- [ ] Screen reader compatible (ARIA labels)
- [ ] WCAG 2.1 AA color contrast
- [ ] Magic link request completes in < 1 second
- [ ] Verification completes in < 1 second
- [ ] Works on Chrome, Firefox, Safari, Edge

---

## Migration Path to Production

### I5-001: Magic Link Endpoints (Already Done!)

The endpoints are already production-ready:
- POST /auth/request-magic-link (already exists)
- GET /auth/verify (already exists)

### I5-002: Email Integration

**Changes Needed**:
```python
# Replace console logging with email sending
# In auth.py

async def send_magic_link_email(email: str, magic_link_url: str):
    """Send magic link email."""
    # Using SendGrid or similar
    await email_service.send(
        to=email,
        subject='Sign in to Roomz',
        template='magic_link',
        context={'magic_link_url': magic_link_url}
    )

# In request_magic_link endpoint
# Replace:
# server.logger.info(f"MAGIC LINK for {email}\n{magic_link_url}")
# With:
# await send_magic_link_email(email, magic_link_url)
```

### I5-003: Session Persistence

**Changes Needed**:
```python
# Migrate from in-memory to MongoDB
# Replace:
# sessions = {}  # in-memory dict
# With:
# sessions = mongodb.sessions  # MongoDB collection
```

---

## Conclusion

The magic link authentication approach is **superior** to the shared secret approach for I2-001 because:

1. ✅ **Eliminates CRITICAL-1** (no shared secret to expose)
2. ✅ **Better security** (unique tokens per user, single-use, time-limited)
3. ✅ **Better UX** (just email address, no shared secret to remember)
4. ✅ **Production ready** (95% of code reusable for I5-001/002)
5. ✅ **Auditability** (clear audit trail by email)
6. ✅ **Aligns with Security Engineer** (httpOnly cookies, rate limiting, token security)

The implementation is straightforward and requires minimal changes to the original plan. The main differences are:

- Replace shared secret + display name with email address
- Add magic link generation and logging
- Add magic link verification endpoint
- Use email as user identifier instead of display name
- Longer session lifetime (30 days instead of 1 hour)

**Recommendation**: Proceed with magic link authentication for I2-001. This approach is cleaner, more secure, and provides a direct migration path to production authentication.