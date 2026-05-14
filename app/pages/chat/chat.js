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
      <v-layout style="height:100vh;">
        <!-- Messages Display Area -->
        <v-main style="height: 100%; overflow: hidden;">
          <v-container fluid style="height: 100%; display: flex; flex-direction: column; padding: 8px;">
            <v-card style="flex: 1; display: flex; flex-direction: column;">
              <v-card-title class="text-h6">Roomz Chat</v-card-title>
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
                  <div class="text-caption text-medium-emphasis" style="margin-bottom: 4px;">
                    {{ formatTime(message.timestamp) }}
                    <span v-if="!message.system && message.sid" style="margin-left: 8px; font-weight: bold;">
                      {{ message.sid.substring(0, 6) }}
                    </span>
                  </div>
                  <div v-if="message.system" class="text-body-2 font-italic">
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
          v-model="showDisconnected"
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
      messages: [],
      messageInput: '',
      sending: false,
      showDisconnected: false
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

      const content = this.messageInput.trim();

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
    scrollToBottom() {
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
    }
  },
  mounted() {
    // Clean up any existing listeners first (in case of reconnection)
    socket.off('message');
    socket.off('user_joined');
    socket.off('user_left');
    socket.off('connect');
    socket.off('disconnect');

    // Listen for incoming messages
    socket.on('message', (message) => {
      this.addMessage(message);
    });

    // Listen for user joined events
    socket.on('user_joined', (data) => {
      this.messages.push({
        id: `system-${Date.now()}`,
        system: true,
        content: `User joined`,
        timestamp: data.timestamp
      });
      this.scrollToBottom();
    });

    // Listen for user left events
    socket.on('user_left', (data) => {
      this.messages.push({
        id: `system-${Date.now()}`,
        system: true,
        content: `User left`,
        timestamp: data.timestamp
      });
      this.scrollToBottom();
    });

    // Connection established
    socket.on('connect', () => {
      console.log('Connected to chat server');
      this.showDisconnected = false;
    });

    // Handle disconnection
    socket.on('disconnect', () => {
      console.log('Disconnected from chat server');
      this.showDisconnected = true;
    });
  },
  beforeUnmount() {
    // Clean up listeners
    socket.off('message');
    socket.off('user_joined');
    socket.off('user_left');
    socket.off('connect');
    socket.off('disconnect');
  }
};

// Register component with app
app.component('Chat', Chat);

// Register with baseweb's Navigation system
// This adds it to both the navigation drawer and the router
Navigation.add(Chat);
