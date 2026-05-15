/**
 * AuthDialog Component and Authentication Store
 *
 * Authentication dialog for magic link flow.
 * Displays email input, sends magic link request, and shows status.
 */

app.component('AuthDialog', {
  name: 'AuthDialog',
  template: `
    <div>
      <!-- Loading indicator while checking session -->
      <v-dialog v-if="checkingSession" v-model="checkingSession" persistent max-width="480">
        <v-card>
          <v-card-text class="text-center pa-8">
            <v-progress-circular indeterminate color="primary" size="64" />
            <div class="text-body-1 mt-4">Checking authentication...</div>
          </v-card-text>
        </v-card>
      </v-dialog>

      <!-- Auth dialog shown after session check -->
      <v-dialog v-if="showDialog" v-model="showDialog" persistent max-width="480">
        <v-card>
          <v-card-title class="text-h5 pb-2">
            <v-icon start color="primary">mdi-email-lock</v-icon>
            Sign in with Email
          </v-card-title>

        <v-card-subtitle class="text-body-2">
          Enter your email address to receive a magic link
        </v-card-subtitle>

        <v-card-text>
          <v-form ref="authForm" v-model="formValid" @submit.prevent="handleRequestMagicLink" role="form" aria-label="Authentication form">
            <!-- Email Input -->
            <v-text-field
              ref="emailField"
              v-model="email"
              label="Email Address"
              type="email"
              placeholder="you@example.com"
              prepend-inner-icon="mdi-email"
              :rules="emailRules"
              :disabled="requesting"
              :error-messages="emailErrors"
              aria-label="Enter your email address"
              aria-required="true"
              :aria-invalid="emailErrors.length > 0"
              :aria-errormessage="emailErrors.length > 0 ? 'email-error' : null"
              autocomplete="email"
              density="comfortable"
              variant="outlined"
              class="mb-3"
              autofocus
            ></v-text-field>

            <!-- Success Message -->
            <v-alert v-if="magicLinkRequested" type="success" density="compact" variant="tonal" class="mb-3" role="alert" aria-live="polite">
              Magic link generated!
              <br/>
              <small>Check the server console for development, or your email inbox in production.</small>
            </v-alert>

            <!-- Error Message -->
            <v-alert v-if="authError" type="error" density="compact" variant="tonal" class="mb-3" closable @click:close="authError = null" role="alert" aria-live="polite">
              {{ authError }}
            </v-alert>
          </v-form>
        </v-card-text>

        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn
            color="primary"
            variant="flat"
            :disabled="!formValid || requesting"
            :loading="requesting"
            @click="handleRequestMagicLink"
          >
            <v-icon start>mdi-send</v-icon>
            Send Magic Link
          </v-btn>
        </v-card-actions>
      </v-card>
    </div>
  `,
  data() {
    return {
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
    showDialog() {
      return !store.checking;
    },
    checkingSession() {
      return store.checking;
    },
    connected() {
      return this.$root.connected;
    }
  },
  watch: {
    // Clear error when user starts typing a new email
    email(newVal) {
      if (newVal && this.authError) {
        this.authError = null;
      }
    }
  },
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

    async handleRequestMagicLink() {
      const { valid } = await this.$refs.authForm.validate();
      if (!valid) return;

      this.authError = null;
      this.requesting = true;

      // Set up 10-second timeout
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 10000);

      try {
        const response = await fetch('/auth/request-magic-link', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email: this.email.trim().toLowerCase() }),
          signal: controller.signal
        });

        clearTimeout(timeoutId);

        const data = await response.json();

        if (response.ok) {
          this.magicLinkRequested = true;
          this.announceToScreenReader('Magic link sent. Check the server console.');
        } else {
          this.authError = data.detail || data.error || 'Failed to request magic link';
          this.announceToScreenReader(`Error: ${this.authError}`);
        }
      } catch (error) {
        clearTimeout(timeoutId);
        if (error.name === 'AbortError') {
          this.authError = 'Request timed out. Please try again.';
          this.announceToScreenReader(this.authError);
        } else {
          this.authError = 'Network error. Please try again.';
          this.announceToScreenReader(this.authError);
        }
      } finally {
        this.requesting = false;
      }
    },
    logout() {
      store.dispatch("logout");
    }
  }
});

// an authentication store that manages the authentication state
// exposes checking and session properties, session contains the current user object
// setup_session action is called when document is ready and tries to get the current
// user object from the server
store.registerModule("auth", {
  state: {
    checking: true,
    session: null
  },
  getters: {
    checking: function (state) {
      return state.checking;
    },
    session: function(state) {
      return state.session;
    }
  },
  actions: {
    setup_session: async function (context) {
      console.debug("store.actions.setup_session");
      context.commit("checking", true);
      try {
        const response = await fetch("/auth/me");
        if (response.ok) {
          const res = await response.json();
          console.debug("  /auth/me response status: success");
          context.commit("session", res);
        } else {
          console.debug("  /auth/me response status: failed");
        }
      } catch (error) {
        console.debug("  /auth/me response status: error", error);
      } finally {
        context.commit("checking", false);
      }
    },
    logout: async function (context) {
      console.log("logging out...");
      try {
        const response = await fetch("/auth/logout", { method: "POST" });
        if (response.ok) {
          console.log("successfully logged out on the server");
        } else {
          console.debug("failed to log out on the server");
        }
      } catch (error) {
        console.debug("failed to log out on the server", error);
      }
      context.commit("session", null);
    }
  },
  mutations: {
    session: function(state, new_session) {
      console.debug("store.mutations.session", new_session);
      state.session = new_session;
    },
    checking: function (state, new_state) {
      console.debug("store.mutations.checking", new_state);
      state.checking = new_state;
    }
  }
});

// when the document is ready, setup the session
document.addEventListener("DOMContentLoaded", function() {
  store.dispatch("setup_session");
});