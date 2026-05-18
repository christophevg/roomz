/**
 * Chat Component
 *
 * Real-time chat interface using Vue 3 + Vuetify 4 + SocketIO.
 * Displays messages, handles user input, and broadcasts to all connected clients.
 */

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
      <!-- Authentication Dialog -->
      <AuthDialog v-if="!authenticated" ref="authDialog"/>

      <v-layout v-if="authenticated" style="height:100vh;">
        <!-- App Bar with User Menu -->
        <v-app-bar flat color="surface">
          <v-toolbar-title><v-icon>mdi-chat</v-icon> Roomz</v-toolbar-title>
          <v-spacer></v-spacer>
          <v-menu v-if="currentUser">
            <template v-slot:activator="{ props }">
              <v-btn v-bind="props" variant="text">
                <v-icon start>mdi-account</v-icon>
                {{ currentUserDisplay }}
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
        </v-app-bar>

        <!-- Messages Display Area -->
        <v-main style="height: 100%; overflow: hidden;">
          <v-container fluid style="height: 100%; display: flex; flex-direction: column; padding: 8px;">
            <v-card style="flex: 1; display: flex; flex-direction: column;">
              <v-card-text
                ref="messagesContainer"
                style="flex: 1; overflow-y: auto; padding: 16px;"
                role="log"
                aria-label="Chat messages"
                aria-live="polite"
              >
                <div
                  v-for="(message, index) in messages"
                  :key="message.id || index"
                  style="margin-bottom: 12px; padding: 8px; border-radius: 8px;"
                  :style="{'background-color': message.system ? 'rgba(var(--v-theme-surface-variant))' : 'rgba(var(--v-theme-primary), 0.1)'}"
                >
                  <div class="text-caption text-high-emphasis" style="margin-bottom: 4px;">
                    <span v-if="!message.system">
                      <strong>{{ formatUserDisplayName(message.user) }}</strong>
                      <span style="margin-left: 8px; opacity: 0.7;">
                        {{ formatTime(message.timestamp) }}
                      </span>
                    </span>
                    <span v-else>
                      {{ formatTime(message.timestamp) }}
                    </span>
                  </div>
                  <div v-if="message.system" class="text-body-2 font-italic text-high-emphasis">
                    {{ message.content }}
                  </div>
                  <div v-else class="text-body-1">
                    {{ message.content }}
                  </div>
                </div>
                <div v-if="messages.length === 0" class="text-center text-medium-emphasis">
                  No messages yet. Start the conversation!
                </div>
              </v-card-text>
            </v-card>
          </v-container>
        </v-main>

        <!-- Input Footer -->
        <v-footer app style="padding: 8px;">
          <v-form @submit.prevent="sendMessage" style="width: 100%;">
            <v-text-field
              v-model="messageInput"
              placeholder="Type a message..."
              prepend-inner-icon="mdi-message-text"
              append-inner-icon="mdi-send"
              :disabled="!connected"
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
          </v-form>
        </v-footer>

        <!-- Connection Status Snackbar -->
        <v-snackbar
          v-model="disconnected"
          color="warning"
          :timeout="-1"
          location="top"
        >
          <v-icon start>mdi-wifi-off</v-icon>
          Connecting to server...
        </v-snackbar>
      </v-layout>
    </Page>
  `,
  data() {
    return {
      connected: false,
      messages: [],
      messageInput: '',
      sending: false,
      displayName: null  // Per-device display name
    };
  },
  computed: {
    disconnected() {
      return !this.connected;
    },
    authenticated() {
      return store.getters.session != null;
    },
    currentUser() {
      return this.authenticated ? store.getters.session.user : null;
    },
    currentUserDisplay() {
      if (!this.currentUser) return 'User';
      const email = this.currentUser.email;
      const name = this.displayName;
      if (name && name.trim()) {
        return `${name.trim()} (${email})`;
      }
      return email;
    }
  },
  methods: {
    formatTime(timestamp) {
      if (!timestamp) return '';
      return new Date(timestamp).toLocaleTimeString();
    },
    formatUserDisplayName(user) {
      if (!user) return 'Unknown';
      const email = user.email || 'Unknown';
      const displayName = user.display_name;
      if (displayName && displayName.trim()) {
        return `${displayName.trim()} (${email})`;
      }
      return email;
    },
    sendMessage() {
      if (!this.messageInput.trim() || !this.connected) return;

      const content = this.messageInput.trim();

      // Handle /name command
      if (content.startsWith('/name ')) {
        const name = content.slice(6).trim();
        this.setDisplayName(name);
        this.messageInput = '';
        return;
      }

      // Handle /name command (clear)
      if (content === '/name') {
        this.setDisplayName(null);
        this.messageInput = '';
        return;
      }

      this.sending = true;
      socket.emit('message', { content }, (ack) => {
        this.sending = false;
        if (ack && ack.status === 'ok') {
          this.messageInput = '';
        } else if (ack && ack.error) {
          console.error('Failed to send message:', ack.error);
        }
      });
    },
    setDisplayName(name) {
      if (name === null || name === '') {
        // Clear display name
        socket.emit('set_display_name', { display_name: null }, (ack) => {
          if (ack && ack.status === 'ok') {
            this.displayName = null;
            localStorage.removeItem('roomz_display_name');
            this.addSystemMessage('Display name cleared. Messages will show your email only.');
          } else {
            this.addSystemMessage(`Failed to clear display name: ${ack?.error || 'Unknown error'}`);
          }
        });
      } else {
        // Set display name
        socket.emit('set_display_name', { display_name: name }, (ack) => {
          if (ack && ack.status === 'ok') {
            this.displayName = ack.display_name;
            localStorage.setItem('roomz_display_name', ack.display_name);
            this.addSystemMessage(`Display name set to: ${ack.display_name}`);
          } else {
            this.addSystemMessage(`Failed to set display name: ${ack?.error || 'Unknown error'}`);
          }
        });
      }
    },
    addSystemMessage(content) {
      this.messages.push({
        id: `system-${Date.now()}`,
        system: true,
        content: content,
        timestamp: new Date().toISOString()
      });
      this.scrollToBottom();
    },
    scrollToBottom() {
      // TODO: also call this function when the window is resized
      this.$nextTick(() => {
        const container = this.$refs.messagesContainer;
        if (container && container.$el) {
          // Vuetify v-card-text returns a component, need to access $el
          const el = container.$el || container;
          el.scrollTop = el.scrollHeight;
        } else if (container) {
          container.scrollTop = container.scrollHeight;
        }
      });
    },
    addMessage(message) {
      this.messages.push(message);
      this.scrollToBottom();
    },
    handleLogout() {
      store.dispatch("logout");
    }
  },
  mounted() {
    // TODO: also move this to a messages Store to avoid complexity and have flexibility

    // Load display name from localStorage
    const storedName = localStorage.getItem('roomz_display_name');
    if (storedName) {
      this.displayName = storedName;
    }

    // Clean up any existing listeners first (in case of reconnection)
    socket.off('message');
    socket.off('user_joined');
    socket.off('user_left');
    socket.off('connect');
    socket.off('disconnect');
    socket.off('authenticated');
    socket.off('display_name_changed');

    // Listen for incoming messages
    socket.on('message', (message) => {
      this.addMessage(message);
    });

    // Listen for user joined events
    socket.on('user_joined', (data) => {
      const userDisplay = this.formatUserDisplayName(data.user);
      this.addMessage({
        id: `system-${Date.now()}`,
        system: true,
        content: `${userDisplay} joined`,
        timestamp: data.timestamp
      });
    });

    // Listen for user left events
    socket.on('user_left', (data) => {
      const userDisplay = this.formatUserDisplayName(data.user);
      this.addMessage({
        id: `system-${Date.now()}`,
        system: true,
        content: `${userDisplay} left`,
        timestamp: data.timestamp
      });
    });

    // Listen for authenticated event
    socket.on('authenticated', (data) => {
      console.log("Authenticated as", data.user?.email);
      // Send display name if stored
      if (this.displayName) {
        this.setDisplayName(this.displayName);
      }
    });

    // Listen for display name changed events
    socket.on('display_name_changed', (data) => {
      // Only show system message for other users' name changes
      if (data.user && data.user.email !== this.currentUser?.email) {
        const userDisplay = this.formatUserDisplayName(data.user);
        this.addMessage({
          id: `system-${Date.now()}`,
          system: true,
          content: `${userDisplay} changed their display name`,
          timestamp: data.timestamp
        });
      }
    });

    // Connection established
    socket.on('connect', () => {
      this.connected = true;
      console.log("Connected to chat server. Authenticated as", this.currentUser);
      // Send display name if stored
      if (this.displayName) {
        this.setDisplayName(this.displayName);
      }
    });

    // Handle disconnection
    socket.on('disconnect', () => {
      this.connected = false;
      console.log("Disconnected from chat server");
    });
  },
  beforeUnmount() {
    // Clean up listeners
    socket.off('message');
    socket.off('user_joined');
    socket.off('user_left');
    socket.off('connect');
    socket.off('disconnect');
    socket.off('authenticated');
    socket.off('display_name_changed');
  }
};

app.component('Chat', Chat);

// Register with baseweb's Navigation system
// This adds it to both the navigation drawer and the router
Navigation.add(Chat);