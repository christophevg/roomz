# UX/UI Analysis: Chat Interface (I1-001)

**Project**: Roomz - Real-time Chatroom Web Service
**Task**: I1-001 - Basic baseweb project setup
**Date**: 2026-05-14
**Analyst**: UI/UX Designer Agent

## Executive Summary

This document outlines the frontend UI design for the minimal chat interface in iteration 1. The design follows baseweb patterns and uses Vue 3 + Vuetify 4 for a responsive, real-time chat experience with WebSocket communication.

## 1. Page Structure

### 1.1 Baseweb Pages Pattern

Following the baseweb pattern from `hello-world` example:

```
web/
  app/
    pages/
      __init__.py          # Python page registration
      chat/
        __init__.py        # Chat page module
        chat.js            # Chat Vue component
```

### 1.2 Component Registration Pattern

Each page component follows the baseweb standard structure:

```javascript
var Chat = {
  name: 'Chat',
  navigation: {
    icon: "mdi-chat",
    text: "Chat",
    path: "/",
    index: 1
  },
  template: `...`
};

app.component('Chat', Chat);
Navigation.add(Chat);
```

### 1.3 Single Page for Iteration 1

For the minimal viable chat UI, a single page component suffices:
- **Page**: Chat (root path `/`)
- **Purpose**: Display chat messages, handle input, manage WebSocket connection
- **Navigation**: Single item with chat icon

## 2. Vue 3 Component Design

### 2.1 Chat Component Architecture

```javascript
var Chat = {
  name: 'Chat',
  navigation: {
    icon: "mdi-chat",
    text: "Chat",
    path: "/",
    index: 1
  },
  template: `
    <Page>
      <v-container fluid class="chat-container">
        <!-- Connection Status Banner -->
        <v-row v-if="!connected">
          <v-col cols="12">
            <v-alert type="warning" density="compact">
              Connecting to server...
            </v-alert>
          </v-col>
        </v-row>

        <!-- Messages Display Area -->
        <v-row>
          <v-col cols="12">
            <v-card class="messages-card">
              <v-card-text ref="messagesContainer" class="messages-container">
                <div
                  v-for="(message, index) in messages"
                  :key="index"
                  class="message-item"
                >
                  <div class="message-timestamp">{{ formatTime(message.timestamp) }}</div>
                  <div class="message-content">{{ message.content }}</div>
                </div>
                <div v-if="messages.length === 0" class="no-messages">
                  No messages yet. Start the conversation!
                </div>
              </v-card-text>
            </v-card>
          </v-col>
        </v-row>

        <!-- Input Area -->
        <v-row class="input-row">
          <v-col cols="12">
            <v-card class="input-card">
              <v-card-text>
                <v-form @submit.prevent="sendMessage">
                  <v-text-field
                    v-model="messageInput"
                    placeholder="Type a message..."
                    prepend-inner-icon="mdi-message-text"
                    append-inner-icon="mdi-send"
                    :disabled="!connected"
                    :loading="sending"
                    @click:append-inner="sendMessage"
                    @keyup.enter="sendMessage"
                    clearable
                    density="comfortable"
                    variant="outlined"
                    hide-details
                  ></v-text-field>
                </v-form>
              </v-card-text>
            </v-card>
          </v-col>
        </v-row>
      </v-container>
    </Page>
  `,
  data() {
    return {
      messages: [],
      messageInput: '',
      sending: false
    };
  },
  computed: {
    connected() {
      return this.$root.connected;
    }
  },
  methods: {
    formatTime(timestamp) {
      if (!timestamp) return '';
      return new Date(timestamp).toLocaleTimeString();
    },
    sendMessage() {
      if (!this.messageInput.trim() || !this.connected) return;

      const message = {
        content: this.messageInput.trim(),
        timestamp: Date.now()
      };

      this.sending = true;
      socket.emit('message', message, (ack) => {
        this.sending = false;
        if (ack && ack.success) {
          this.messageInput = '';
        }
      });
    },
    scrollToBottom() {
      this.$nextTick(() => {
        const container = this.$refs.messagesContainer;
        if (container) {
          container.scrollTop = container.scrollHeight;
        }
      });
    },
    addMessage(message) {
      this.messages.push(message);
      this.scrollToBottom();
    }
  },
  mounted() {
    // Listen for incoming messages
    socket.on('message', (message) => {
      this.addMessage(message);
    });

    // Connection established
    socket.on('connect', () => {
      console.log('Connected to chat server');
    });

    // Handle disconnection
    socket.on('disconnect', () => {
      console.log('Disconnected from chat server');
    });
  },
  beforeUnmount() {
    // Clean up listeners
    socket.off('message');
  }
};
```

### 2.2 Component State Management

| State | Purpose | Type |
|-------|---------|------|
| `messages` | Array of received messages | `Array<{content, timestamp}>` |
| `messageInput` | Current input text | `String` |
| `sending` | Sending in progress indicator | `Boolean` |
| `connected` | WebSocket connection state (from root) | `Boolean` |

### 2.3 Component Lifecycle

```
mounted()
  |-- socket.on('message', addMessage)
  |-- socket.on('connect', ...)
  |-- socket.on('disconnect', ...)

beforeUnmount()
  |-- socket.off('message')
```

## 3. Vuetify Components to Use

### 3.1 Core Components

| Component | Purpose | Key Props |
|-----------|---------|-----------|
| `v-container` | Root layout container | `fluid` for full width |
| `v-row` | Horizontal flex container | Responsive column layout |
| `v-col` | Column container | `cols="12"` for mobile-first |
| `v-card` | Message container card | `class="messages-card"` |
| `v-card-text` | Card content area | Scrollable area |
| `v-text-field` | Message input | `density="comfortable"`, `variant="outlined"` |
| `v-alert` | Connection status | `type="warning"`, `density="compact"` |
| `v-form` | Input form wrapper | `@submit.prevent="sendMessage"` |

### 3.2 Icons (Material Design Icons)

| Icon | Usage |
|------|-------|
| `mdi-chat` | Navigation icon |
| `mdi-message-text` | Input prepend icon |
| `mdi-send` | Send button icon |
| `mdi-cloud-check` | Connection indicator (connected) |
| `mdi-cloud-off` | Connection indicator (disconnected) |

### 3.3 Responsive Design Props

```javascript
// Mobile-first responsive columns
<v-col cols="12" sm="10" md="8" lg="6">
  <!-- Full width on mobile, centered on larger screens -->
</v-col>

// Compact density for mobile
<v-text-field density="comfortable" />

// Fluid container for full-width on mobile
<v-container fluid>
```

## 4. SocketIO Client Integration

### 4.1 Built-in SocketIO Support

Baseweb provides built-in SocketIO support:

1. **Configuration**: Set `APP_SOCKETIO=yes` environment variable
2. **Global `socket` object**: Available after `socketio.js` loads
3. **Connection state**: Reactive `connected` computed property from root app

### 4.2 WebSocket Protocol for Iteration 1

**Simple broadcast protocol (no rooms yet):**

| Event | Direction | Payload |
|-------|-----------|---------|
| `message` | Client -> Server | `{ content: string }` |
| `message` | Server -> Client | `{ content: string, timestamp: number }` |
| `connect` | Server -> Client | Connection acknowledgment |
| `disconnect` | Server -> Client | Disconnection notice |

### 4.3 Connection Handling

```javascript
// Connection state from baseweb root app
computed: {
  connected() {
    return this.$root.connected;
  }
}

// Automatic reconnection handled by Socket.IO client
// Baseweb shows connection status in app bar via mdi-cloud-check/off icons
```

### 4.4 Message Flow

```
User types message
  -> Click send button or press Enter
    -> sendMessage() method
      -> socket.emit('message', {content, timestamp})
        -> Server broadcasts to all clients
          -> socket.on('message') on each client
            -> addMessage() adds to messages array
              -> Vue reactivity updates UI
                -> scrollToBottom() scrolls to latest
```

## 5. Responsive Layout Considerations

### 5.1 Breakpoint Strategy

| Breakpoint | Width | Layout |
|------------|-------|--------|
| xs | < 600px | Full-width, stacked layout |
| sm | >= 600px | Centered with margins |
| md | >= 960px | Optimal reading width |
| lg | >= 1280px | Maximum chat width |

### 5.2 Mobile-First Design

```css
/* Key responsive behaviors */
.chat-container {
  height: calc(100vh - 64px); /* Account for app bar */
  display: flex;
  flex-direction: column;
}

.messages-card {
  flex: 1;
  overflow: hidden;
}

.messages-container {
  height: calc(100vh - 200px);
  overflow-y: auto;
  -webkit-overflow-scrolling: touch; /* Smooth scrolling on iOS */
}

.input-row {
  flex-shrink: 0;
  position: sticky;
  bottom: 0;
  background: var(--v-theme-surface);
}
```

### 5.3 Touch-Friendly Interactions

- **Input field**: `density="comfortable"` for touch-friendly size
- **Send button**: Appended icon with generous touch target
- **Scrolling**: Native scroll with momentum on mobile
- **Keyboard**: Enter key sends message (explicit `@keyup.enter`)

### 5.4 Accessibility Considerations (R69, R70)

```html
<!-- ARIA labels for screen readers -->
<v-text-field
  aria-label="Message input"
  role="textbox"
  :aria-disabled="!connected"
/>

<v-card
  role="log"
  aria-label="Chat messages"
  aria-live="polite"
>
  <!-- Messages announced as they arrive -->
</v-card>

<!-- Keyboard navigation -->
<v-btn
  @click="sendMessage"
  aria-label="Send message"
  :disabled="!connected || !messageInput.trim()"
>
  <v-icon>mdi-send</v-icon>
</v-btn>
```

## 6. Backend Integration Notes

### 6.1 Server Requirements (Coordinate with API Architect)

The Quart WebSocket server needs to provide:

| Feature | Requirement |
|---------|-------------|
| WebSocket endpoint | `/ws` for Socket.IO connections |
| CORS | Allow web client origin |
| Message broadcast | Relay received messages to all connected clients |
| Connection tracking | Maintain list of connected clients |

### 6.2 No Authentication in Iteration 1

Per TODO.md I1-001: "No authentication - open connection"
- Server accepts any WebSocket connection
- No token validation required at this stage
- Messages are anonymous (no sender identification in I1-001)

### 6.3 Future Iteration Considerations

For Iteration 2+ the UI will need:
- Authentication dialog (R58, R59)
- User display name in messages (R23, R56)
- Room selection/creation (R62, R63)
- Presence indicators (R26-R28)

## 7. File Structure

```
web/
  app.py                  # Baseweb application factory
  app/
    pages/
      __init__.py         # Page discovery/registration
      chat/
        __init__.py       # Chat page Python module
        chat.js           # Chat Vue component
    static/
      # Optional: custom CSS/JS
    templates/
      main.html           # Custom main template (optional)
```

### 7.1 app.py (Server Entry Point)

```python
from baseweb import Baseweb

app = Baseweb(
  name="Roomz",
  title="Roomz - Real-time Chat",
  socketio="yes"
)

# Pages are auto-discovered from app/pages/
# SocketIO handlers registered separately

if __name__ == "__main__":
  app.run()
```

### 7.2 pages/chat/__init__.py

```python
from pathlib import Path

# Register the chat page component
# Baseweb auto-discovers pages from this directory structure
```

## 8. Design Decisions

### 8.1 Single Page vs Multi-Page

**Decision**: Single page (`/`) for iteration 1

**Rationale**:
- Minimal viable product focuses on core chat functionality
- No rooms or authentication in I1-001
- Simplifies implementation and testing
- Easy to extend with additional pages in later iterations

### 8.2 Inline Styles vs External CSS

**Decision**: Use Vuetify props and minimal inline styles

**Rationale**:
- Baseweb pattern uses inline templates with Vue
- Vuetify provides comprehensive styling props
- Keeps component self-contained
- Custom CSS can be added to `app/static/` if needed

### 8.3 State Management

**Decision**: Local component state (no Vuex/Pinia)

**Rationale**:
- Simple message list for I1-001
- No shared state between components yet
- Vuex store available for future iterations (rooms, authentication)

### 8.4 Connection Indicator

**Decision**: Use baseweb's built-in app bar connection status

**Rationale**:
- Baseweb shows `mdi-cloud-check/off` in app bar automatically
- Consistent with baseweb applications
- Additional warning alert for disconnection state

## 9. Acceptance Criteria Mapping

| Requirement | Implementation |
|-------------|----------------|
| R54: Responsive design (desktop and mobile) | Mobile-first layout with responsive columns |
| R56: Message display with timestamps | `v-card` with scrollable messages area |
| R57: Message input with send button | `v-text-field` with append icon and Enter key |
| R66: UI loads within 3 seconds | Minimal components, no auth flow |
| R67: Browser compatibility | Vuetify 4 supports all modern browsers |
| R68: Mobile-responsive (320px minimum) | `cols="12"` ensures full-width on mobile |
| R69: Keyboard navigation | Enter key to send, Tab navigation |
| R70: Screen reader compatible | ARIA labels, semantic HTML, role="log" |

## 10. Testing Notes

### 10.1 Manual Testing Checklist

- [ ] Open `/` in browser, see chat UI
- [ ] Type message, press Enter, message appears
- [ ] Click send icon, message appears
- [ ] Open second tab, send message, appears in both
- [ ] Resize window to mobile width, layout adapts
- [ ] Check connection status indicator in app bar
- [ ] Test on Chrome, Firefox, Safari, Edge
- [ ] Test at 320px width (minimum mobile)

### 10.2 Integration Testing Notes

- Verify WebSocket connection established
- Verify message broadcast to multiple clients
- Verify automatic reconnection after server restart
- Verify scroll-to-bottom on new message

## 11. Dependencies

### 11.1 Frontend Dependencies (via baseweb)

| Dependency | Version | Purpose |
|------------|---------|---------|
| Vue | 3.x | Reactive framework |
| Vuetify | 3.x (Labs) | Material Design components |
| Vuex | 4.x | State management |
| Vue Router | 4.x | Routing |
| Socket.IO Client | 4.x | WebSocket communication |

### 11.2 Backend Dependencies

| Dependency | Purpose |
|------------|---------|
| baseweb | Web framework with SocketIO |
| Quart | Async web framework |
| python-socketio | Server-side SocketIO |

## 12. Next Steps for Engineering

1. **Create `web/` directory structure** following section 7
2. **Implement `app.py`** with baseweb configuration
3. **Create `app/pages/chat/chat.js`** component from section 2.1
4. **Configure Socket.IO server** in Quart app (coordinate with API Architect)
5. **Test WebSocket broadcast** with multiple browser tabs
6. **Verify responsive layout** on different screen sizes

---

**Document Version**: 1.0
**Last Updated**: 2026-05-14