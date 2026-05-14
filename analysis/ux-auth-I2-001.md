# UX/UI Analysis: Authentication Dialog (I2-001)

**Project**: Roomz - Real-time Chatroom Web Service
**Task**: I2-001 - Secret dialog authentication
**Date**: 2026-05-14
**Analyst**: UI/UX Designer Agent

## Executive Summary

This document outlines the UI design for the authentication dialog in iteration 2. The dialog provides a simple authentication flow using a shared secret and display name, storing the session in localStorage and displaying the user's name with their messages in the chat interface.

## 1. User Flow Overview

### 1.1 Authentication Flow

```
User visits application
  -> Check localStorage for existing session
    -> If session exists: Validate with server
      -> If valid: Proceed to chat, show messages with user names
      -> If invalid: Clear storage, show auth dialog
    -> If no session: Show auth dialog
      -> User enters display name + shared secret
      -> Submit to server
      -> On success: Store session, enter chat
      -> On error: Show error message, allow retry
```

### 1.2 Session States

| State | UI Behavior |
|-------|-------------|
| No session | Show auth dialog, disable chat |
| Validating session | Show loading spinner |
| Session valid | Hide dialog, enable chat |
| Session expired/invalid | Clear storage, show auth dialog with error |
| Authentication error | Show inline error, allow retry |

### 1.3 User Experience Goals

1. **Minimal Friction**: Single dialog with two fields, no multi-step flow
2. **Clear Feedback**: Immediate feedback on validation errors
3. **Session Persistence**: Remember authentication across browser sessions
4. **Graceful Recovery**: Handle expired/invalid sessions smoothly

## 2. Dialog Component Design

### 2.1 AuthDialog Component Structure

```javascript
var AuthDialog = {
  name: 'AuthDialog',
  template: `
    <v-dialog
      v-model="showDialog"
      :persistent="!isAuthenticated"
      max-width="480"
      :close-on-content-click="false"
      :close-on-back="isAuthenticated"
    >
      <v-card>
        <v-card-title class="text-h5 pb-2">
          <v-icon start color="primary">mdi-account-circle</v-icon>
          Join the Conversation
        </v-card-title>

        <v-card-subtitle class="text-body-2">
          Enter your display name and the shared secret to authenticate
        </v-card-subtitle>

        <v-card-text>
          <v-form
            ref="authForm"
            v-model="formValid"
            @submit.prevent="handleAuthenticate"
          >
            <!-- Display Name Field -->
            <v-text-field
              v-model="displayName"
              label="Display Name"
              placeholder="How others will see you"
              prepend-inner-icon="mdi-account"
              :rules="nameRules"
              :disabled="authenticating"
              :error-messages="nameErrors"
              counter="50"
              maxlength="50"
              autocomplete="username"
              density="comfortable"
              variant="outlined"
              class="mb-3"
              @update:error="handleNameError"
            ></v-text-field>

            <!-- Shared Secret Field -->
            <v-text-field
              v-model="sharedSecret"
              label="Shared Secret"
              placeholder="Enter the room access code"
              prepend-inner-icon="mdi-key"
              :type="showSecret ? 'text' : 'password'"
              :append-inner-icon="showSecret ? 'mdi-eye-off' : 'mdi-eye'"
              :rules="secretRules"
              :disabled="authenticating"
              :error-messages="secretErrors"
              autocomplete="current-password"
              density="comfortable"
              variant="outlined"
              class="mb-3"
              @click:append-inner="showSecret = !showSecret"
              @update:error="handleSecretError"
            ></v-text-field>

            <!-- Connection Status Indicator -->
            <v-alert
              v-if="!connected"
              type="warning"
              density="compact"
              variant="tonal"
              class="mb-3"
            >
              <v-icon start>mdi-wifi-off</v-icon>
              Waiting for server connection...
            </v-alert>

            <!-- Authentication Error Alert -->
            <v-alert
              v-if="authError"
              type="error"
              density="compact"
              variant="tonal"
              class="mb-3"
              closable
              @click:close="authError = null"
            >
              <v-icon start>mdi-alert-circle</v-icon>
              {{ authError }}
            </v-alert>

            <!-- Session Info (when authenticated) -->
            <v-alert
              v-if="isAuthenticated"
              type="success"
              density="compact"
              variant="tonal"
              class="mb-3"
            >
              <v-icon start>mdi-check-circle</v-icon>
              Authenticated as <strong>{{ currentUser }}</strong>
            </v-alert>
          </v-form>
        </v-card-text>

        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn
            color="primary"
            variant="flat"
            :disabled="!formValid || !connected || authenticating"
            :loading="authenticating"
            @click="handleAuthenticate"
          >
            <v-icon start>mdi-login</v-icon>
            Join Chat
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  `,
  data() {
    return {
      showDialog: true,
      displayName: '',
      sharedSecret: '',
      showSecret: false,
      formValid: false,
      authenticating: false,
      authError: null,
      nameErrors: [],
      secretErrors: [],
      // Validation rules
      nameRules: [
        v => !!v || 'Display name is required',
        v => (v && v.length >= 2) || 'Name must be at least 2 characters',
        v => (v && v.length <= 50) || 'Name must be less than 50 characters',
        v => (v && /^[a-zA-Z0-9_\-\s]+$/.test(v)) || 'Name can only contain letters, numbers, spaces, underscores, and hyphens'
      ],
      secretRules: [
        v => !!v || 'Shared secret is required'
      ]
    };
  },
  computed: {
    connected() {
      return this.$root.connected;
    },
    isAuthenticated() {
      return this.$root.authenticated;
    },
    currentUser() {
      return this.$root.currentUser;
    }
  },
  methods: {
    handleNameError(error) {
      // Clear name-specific errors when user starts typing
      if (this.nameErrors.length > 0 && this.displayName) {
        this.nameErrors = [];
      }
    },
    handleSecretError(error) {
      // Clear secret-specific errors when user starts typing
      if (this.secretErrors.length > 0 && this.sharedSecret) {
        this.secretErrors = [];
      }
    },
    async handleAuthenticate() {
      // Validate form
      const { valid } = await this.$refs.authForm.validate();
      if (!valid) return;

      // Check connection
      if (!this.connected) {
        this.authError = 'Not connected to server. Please wait...';
        return;
      }

      // Clear previous errors
      this.authError = null;
      this.authenticating = true;

      // Emit authentication request via WebSocket
      socket.emit('authenticate', {
        display_name: this.displayName.trim(),
        shared_secret: this.sharedSecret
      }, (response) => {
        this.authenticating = false;

        if (response.status === 'ok') {
          // Success: store session and update root state
          this.storeSession(response.token, response.user);
          this.$root.authenticated = true;
          this.$root.currentUser = response.user;
          this.$root.authToken = response.token;
          this.showDialog = false;
        } else {
          // Error: display appropriate message
          this.handleAuthError(response.error);
        }
      });
    },
    handleAuthError(error) {
      // Map server errors to user-friendly messages
      const errorMessages = {
        'invalid_secret': 'The shared secret you entered is incorrect.',
        'invalid_name': 'The display name is invalid or already in use.',
        'name_taken': 'This display name is already taken. Please choose another.',
        'server_error': 'An error occurred. Please try again.',
        'rate_limited': 'Too many attempts. Please wait before trying again.'
      };
      this.authError = errorMessages[error.code] || error.message || 'Authentication failed. Please try again.';

      // Set field-specific errors if applicable
      if (error.code === 'invalid_name' || error.code === 'name_taken') {
        this.nameErrors = [this.authError];
      } else if (error.code === 'invalid_secret') {
        this.secretErrors = [this.authError];
      }
    },
    storeSession(token, user) {
      // Store in localStorage for persistence
      const session = {
        token: token,
        user: user,
        authenticatedAt: Date.now()
      };
      localStorage.setItem('roomz_session', JSON.stringify(session));
    },
    loadSession() {
      // Check for existing session on mount
      const sessionData = localStorage.getItem('roomz_session');
      if (!sessionData) return null;

      try {
        const session = JSON.parse(sessionData);
        // Validate with server
        socket.emit('validate_session', { token: session.token }, (response) => {
          if (response.status === 'ok') {
            this.$root.authenticated = true;
            this.$root.currentUser = response.user;
            this.$root.authToken = session.token;
            this.showDialog = false;
          } else {
            // Session invalid, clear storage
            localStorage.removeItem('roomz_session');
          }
        });
      } catch (e) {
        // Invalid session data, clear
        localStorage.removeItem('roomz_session');
      }
    },
    logout() {
      // Clear session and show dialog
      localStorage.removeItem('roomz_session');
      this.$root.authenticated = false;
      this.$root.currentUser = null;
      this.$root.authToken = null;
      this.displayName = '';
      this.sharedSecret = '';
      this.authError = null;
      this.showDialog = true;
    }
  },
  mounted() {
    // Check for existing session
    this.loadSession();

    // Listen for authentication events
    socket.on('auth_expired', () => {
      this.authError = 'Your session has expired. Please authenticate again.';
      this.logout();
    });

    socket.on('auth_revoked', () => {
      this.authError = 'Your session has been revoked.';
      this.logout();
    });
  },
  beforeUnmount() {
    socket.off('auth_expired');
    socket.off('auth_revoked');
  }
};
```

### 2.2 Component State

| State | Type | Purpose |
|-------|------|---------|
| `showDialog` | Boolean | Controls dialog visibility |
| `displayName` | String | User's display name input |
| `sharedSecret` | String | Shared secret input |
| `showSecret` | Boolean | Toggle password visibility |
| `formValid` | Boolean | Form validation state |
| `authenticating` | Boolean | Loading state during auth |
| `authError` | String/null | Authentication error message |
| `nameErrors` | Array | Field-specific name errors |
| `secretErrors` | Array | Field-specific secret errors |

### 2.3 Validation Rules

**Display Name Validation:**
- Required field
- Minimum 2 characters
- Maximum 50 characters
- Allowed characters: letters, numbers, spaces, underscores, hyphens
- No profanity filter in I2-001 (future iteration)

**Shared Secret Validation:**
- Required field
- No client-side validation of format (server validates)
- Password field with visibility toggle

### 2.4 Root State Management

The root Vue app (`this.$root`) needs new state properties:

```javascript
// In baseweb app initialization (app.js or similar)
app.data = {
  connected: false,
  authenticated: false,  // NEW: Authentication status
  currentUser: null,     // NEW: Current user display name
  authToken: null        // NEW: Session token
};
```

## 3. Integration with Chat Component

### 3.1 Modified Chat Component

The existing chat component needs modifications to display user names:

```javascript
// Updated message display in Chat component
<div
  v-for="(message, index) in messages"
  :key="message.id || index"
  style="margin-bottom: 12px; padding: 8px; border-radius: 8px;"
  :style="{'background-color': getMessageBackground(message)}"
>
  <div class="text-caption text-medium-emphasis" style="margin-bottom: 4px;">
    <span v-if="!message.system">
      <strong>{{ message.user || 'Anonymous' }}</strong>
      <span style="margin-left: 8px; opacity: 0.7;">
        {{ formatTime(message.timestamp) }}
      </span>
    </span>
    <span v-else>
      {{ formatTime(message.timestamp) }}
    </span>
  </div>
  <div v-if="message.system" class="text-body-2 font-italic">
    {{ message.content }}
  </div>
  <div v-else class="text-body-1">
    {{ message.content }}
  </div>
</div>
```

### 3.2 Message Structure Update

**Server Message Format (I2-001):**

```javascript
{
  id: 'string',
  user: 'string',      // Display name of sender
  content: 'string',
  timestamp: number,
  system: boolean      // Optional: system message flag
}
```

### 3.3 Authentication State Display

**App Bar Integration:**

```javascript
// Add user menu to app bar (in main layout or toolbar)
<v-menu v-if="authenticated">
  <template v-slot:activator="{ props }">
    <v-btn v-bind="props" variant="text">
      <v-icon start>mdi-account</v-icon>
      {{ currentUser }}
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
<v-btn v-else variant="text" @click="showAuthDialog = true">
  <v-icon start>mdi-login</v-icon>
  Sign In
</v-btn>
```

### 3.4 Message Input State

**Disabled State When Not Authenticated:**

```javascript
<v-text-field
  v-model="messageInput"
  placeholder="Type a message..."
  prepend-inner-icon="mdi-message-text"
  append-inner-icon="mdi-send"
  :disabled="!connected || !authenticated"
  :loading="sending"
  @click:append-inner="sendMessage"
  @keyup.enter="sendMessage"
  aria-label="Message input"
  role="textbox"
  clearable
  density="comfortable"
  variant="outlined"
  hide-details
></v-text-field>
```

## 4. User Feedback States

### 4.1 Connection States

| State | Visual Feedback |
|-------|-----------------|
| Not connected to server | Warning alert in dialog, "Waiting for server connection..." |
| Connected, not authenticated | Auth dialog visible, join button enabled |
| Authenticating | Loading spinner on button, fields disabled |
| Authentication failed | Error alert with specific message, fields enabled for retry |
| Authenticated | Success alert briefly shown, dialog closes |
| Session expired | Error alert "Session expired", dialog reopens |

### 4.2 Validation Feedback

**Real-time Validation:**
- Field shows error immediately on blur if invalid
- Clear error when user starts typing
- Submit button disabled until form valid

**Server Validation Errors:**
- Display as inline alert above submit button
- Field-specific errors shown under relevant input
- Preserve user input on error

### 4.3 Loading States

```javascript
// Button loading state
<v-btn
  :loading="authenticating"
  :disabled="!formValid || !connected || authenticating"
>
  <v-icon start>mdi-login</v-icon>
  Join Chat
</v-btn>

// Loading overlay (alternative)
<v-overlay
  :model-value="authenticating"
  class="align-center justify-center"
  contained
>
  <v-progress-circular indeterminate></v-progress-circular>
</v-overlay>
```

## 5. Session Persistence

### 5.1 LocalStorage Schema

```javascript
// Key: 'roomz_session'
{
  token: 'string',        // Session token from server
  user: 'string',         // Display name
  authenticatedAt: number // Timestamp
}
```

### 5.2 Session Lifecycle

```
[Page Load]
    |
    v
[Check localStorage]
    |
    +---> [No session] ---> [Show auth dialog]
    |
    +---> [Session exists]
              |
              v
         [Validate with server]
              |
              +---> [Valid] ---> [Enter chat, hide dialog]
              |
              +---> [Invalid/Expired] ---> [Clear storage] ---> [Show auth dialog]
```

### 5.3 Session Validation

**On Page Load:**
```javascript
mounted() {
  // Existing session validation
  this.loadSession();

  // Also validate on reconnection
  socket.on('connect', () => {
    if (this.$root.authToken) {
      socket.emit('validate_session', { token: this.$root.authToken }, (response) => {
        if (response.status !== 'ok') {
          this.logout();
        }
      });
    }
  });
}
```

### 5.4 Logout Implementation

```javascript
methods: {
  handleLogout() {
    // Notify server
    if (this.$root.authToken) {
      socket.emit('logout', { token: this.$root.authToken });
    }

    // Clear local state
    localStorage.removeItem('roomz_session');
    this.$root.authenticated = false;
    this.$root.currentUser = null;
    this.$root.authToken = null;

    // Show auth dialog
    this.showDialog = true;
  }
}
```

## 6. Responsive Design

### 6.1 Dialog Sizing

```css
/* Mobile-first responsive dialog */
.v-dialog {
  margin: 16px;
}

@media (min-width: 600px) {
  .v-dialog {
    max-width: 480px;
    margin: auto;
  }
}
```

### 6.2 Touch-Friendly Interactions

- **Input fields**: `density="comfortable"` for adequate touch targets
- **Password visibility toggle**: Large touch target on eye icon
- **Submit button**: Minimum 44px height for touch
- **Error dismiss**: Closeable alerts with touch-friendly close button

### 6.3 Keyboard Navigation

- **Tab order**: Display name -> Secret -> Join button
- **Enter key**: Submit from either input field
- **Escape key**: No action (dialog is persistent when not authenticated)
- **Focus management**: Auto-focus on display name field when dialog opens

```javascript
mounted() {
  this.$nextTick(() => {
    this.$refs.displayName?.focus();
  });
}
```

## 7. Accessibility

### 7.1 ARIA Labels

```html
<v-form
  ref="authForm"
  role="form"
  aria-label="Authentication form"
>
  <v-text-field
    aria-label="Enter your display name"
    aria-required="true"
    aria-invalid="nameErrors.length > 0"
    :aria-errormessage="nameErrors.length > 0 ? 'name-error' : null"
  />
  <v-text-field
    aria-label="Enter the shared secret"
    aria-required="true"
    aria-invalid="secretErrors.length > 0"
    type="password"
    :aria-describedby="showSecret ? null : 'secret-help'"
  />
  <v-btn
    aria-label="Join chat"
    :aria-disabled="!formValid || authenticating"
  >
    Join Chat
  </v-btn>
</v-form>
```

### 7.2 Screen Reader Announcements

```javascript
// Announce authentication state changes
methods: {
  announceToScreenReader(message) {
    const announcement = document.createElement('div');
    announcement.setAttribute('role', 'status');
    announcement.setAttribute('aria-live', 'polite');
    announcement.setAttribute('aria-atomic', 'true');
    announcement.className = 'sr-only';
    announcement.textContent = message;
    document.body.appendChild(announcement);
    setTimeout(() => document.body.removeChild(announcement), 1000);
  },

  handleAuthenticate() {
    // ...
    if (response.status === 'ok') {
      this.announceToScreenReader(`Successfully authenticated as ${this.displayName}`);
    } else {
      this.announceToScreenReader(`Authentication failed: ${this.authError}`);
    }
  }
}
```

### 7.3 Color Contrast

- All text meets WCAG 2.1 AA contrast ratio (4.5:1 for normal text, 3:1 for large text)
- Error messages use semantic colors with sufficient contrast
- Focus indicators are visible with 3:1 contrast ratio

## 8. Error Handling

### 8.1 Client-Side Errors

| Error | Display |
|-------|---------|
| Empty display name | "Display name is required" |
| Name too short | "Name must be at least 2 characters" |
| Name too long | "Name must be less than 50 characters" |
| Invalid characters | "Name can only contain letters, numbers, spaces, underscores, and hyphens" |
| Empty secret | "Shared secret is required" |

### 8.2 Server-Side Errors

| Error Code | User Message |
|------------|--------------|
| `invalid_secret` | "The shared secret you entered is incorrect." |
| `invalid_name` | "The display name is invalid or already in use." |
| `name_taken` | "This display name is already taken. Please choose another." |
| `server_error` | "An error occurred. Please try again." |
| `rate_limited` | "Too many attempts. Please wait before trying again." |

### 8.3 Network Errors

```javascript
// Connection timeout handling
methods: {
  handleAuthenticate() {
    // Set timeout for server response
    const timeout = setTimeout(() => {
      if (this.authenticating) {
        this.authenticating = false;
        this.authError = 'Server is not responding. Please check your connection.';
      }
    }, 10000); // 10 second timeout

    socket.emit('authenticate', payload, (response) => {
      clearTimeout(timeout);
      // Handle response...
    });
  }
}
```

## 9. WebSocket Protocol Updates

### 9.1 New Events (I2-001)

| Event | Direction | Payload |
|-------|-----------|---------|
| `authenticate` | Client -> Server | `{ display_name: string, shared_secret: string }` |
| `authenticate` | Server -> Client | `{ status: 'ok', token: string, user: string }` or `{ status: 'error', error: {...} }` |
| `validate_session` | Client -> Server | `{ token: string }` |
| `validate_session` | Server -> Client | `{ status: 'ok', user: string }` or `{ status: 'error' }` |
| `auth_expired` | Server -> Client | (no payload) |
| `logout` | Client -> Server | `{ token: string }` |

### 9.2 Updated Message Event

**Before (I1-001):**
```javascript
socket.emit('message', { content: 'text' });
```

**After (I2-001):**
```javascript
// Server automatically includes user from session token
socket.emit('message', { content: 'text' });

// Server broadcasts:
{
  id: 'unique-id',
  user: 'display_name',
  content: 'text',
  timestamp: 1234567890
}
```

## 10. Component Registration

### 10.1 File Structure

```
app/
  pages/
    chat/
      __init__.py
      chat.js          # Modified chat component
    auth/
      __init__.py
      auth.js          # AuthDialog component
```

### 10.2 Auth Page Registration

```javascript
// app/pages/auth/auth.js
var AuthDialog = {
  // ... component definition above
};

app.component('AuthDialog', AuthDialog);
```

### 10.3 Integration in Main Layout

```javascript
// In main template or app.js
<div id="app">
  <AuthDialog v-if="!authenticated" />
  <Chat v-else />
</div>
```

**Alternative: Conditional rendering within Chat:**

```javascript
// In Chat component template
<Page>
  <AuthDialog v-if="!authenticated" />
  <v-layout v-else style="height:100vh;">
    <!-- Existing chat layout -->
  </v-layout>
</Page>
```

## 11. Testing Checklist

### 11.1 Functional Testing

- [ ] Dialog appears when no session exists
- [ ] Dialog does not appear when valid session exists
- [ ] Display name validation works (min length, max length, characters)
- [ ] Secret field required validation works
- [ ] Password visibility toggle works
- [ ] Submit button disabled when form invalid
- [ ] Submit button disabled when not connected
- [ ] Loading state shows during authentication
- [ ] Success: dialog closes, user enters chat
- [ ] Error: error message displays, form remains
- [ ] Session stored in localStorage
- [ ] Session restored on page reload
- [ ] Session cleared on logout
- [ ] Session expiration handled gracefully
- [ ] User name appears with messages
- [ ] User name visible in app bar/menu

### 11.2 Accessibility Testing

- [ ] Tab order is correct
- [ ] Enter key submits form
- [ ] Screen reader announces errors
- [ ] Screen reader announces success
- [ ] Focus management works (focus on name field)
- [ ] Color contrast passes WCAG 2.1 AA
- [ ] Works with keyboard only (no mouse)

### 11.3 Responsive Testing

- [ ] Dialog looks good at 320px width
- [ ] Dialog looks good at 375px width (mobile)
- [ ] Dialog looks good at 768px width (tablet)
- [ ] Dialog looks good at 1024px+ width (desktop)
- [ ] Touch targets are adequate (44px minimum)
- [ ] Virtual keyboard doesn't obscure submit button

### 11.4 Integration Testing

- [ ] WebSocket authentication flow works
- [ ] Invalid secret returns appropriate error
- [ ] Invalid name returns appropriate error
- [ ] Rate limiting enforced by server
- [ ] Message includes user name after authentication
- [ ] Session validation on reconnection works
- [ ] Logout clears session on server

## 12. Dependencies

### 12.1 Vuetify Components

| Component | Purpose |
|-----------|---------|
| `v-dialog` | Modal dialog container |
| `v-card` | Dialog content container |
| `v-card-title` | Dialog header |
| `v-card-subtitle` | Dialog subtitle |
| `v-card-text` | Form container |
| `v-card-actions` | Button container |
| `v-form` | Form wrapper with validation |
| `v-text-field` | Input fields |
| `v-btn` | Submit button |
| `v-alert` | Error/success messages |
| `v-icon` | Icons |
| `v-spacer` | Layout spacing |
| `v-progress-circular` | Loading indicator |

### 12.2 Server Requirements (Coordinate with API Architect)

| Requirement | Notes |
|-------------|-------|
| `authenticate` event handler | Validates secret, creates session |
| `validate_session` event handler | Validates token, returns user info |
| `logout` event handler | Invalidates session token |
| Session token generation | Cryptographically secure |
| Hardcoded or env-based secret | For I2-001 only (iteration 2) |
| `auth_expired` event | Notify client of expired session |

## 13. Future Iterations

### 13.1 I5-001: Magic Link Authentication

The auth dialog will be extended to support:
- Email input field (replacing shared secret temporarily)
- "Request magic link" button
- "Link sent" confirmation state
- Magic link verification page

### 13.2 I4-001: Room Selection

After authentication, room selection UI:
- Room list component
- Join/leave room buttons
- Room creation form

### 13.3 Enhancements

- Remember last used display name (localStorage)
- "Remember me" checkbox for extended sessions
- Avatar selection/upload
- User profile settings

## 14. Acceptance Criteria Mapping

| Requirement | Implementation |
|-------------|----------------|
| Authentication dialog in web UI | AuthDialog component with v-dialog |
| Input for display name | v-text-field with validation rules |
| Input for shared secret | v-text-field with password type and visibility toggle |
| Show connection status | Warning alert when disconnected |
| Display user name with messages | Message structure includes `user` field, displayed in message header |
| Session persistence | localStorage with validation on load |
| Acceptance: Enter secret and display name, see your name appear with your messages | Full flow documented in section 3 |

---

**Document Version**: 1.0
**Last Updated**: 2026-05-14
**Next Review**: After I2-001 implementation