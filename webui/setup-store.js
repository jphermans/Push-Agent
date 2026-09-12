import { createStore } from "/js/AlpineStore.js";
import * as API from "/js/api.js";
import { toastFrontendError, toastFrontendSuccess, toastFrontendInfo, toastFrontendWarning } from "/components/notifications/notification-store.js";

const API_BASE = "/api/plugins/push_zero";

const PRIORITY_OPTIONS = [
  { value: "lowest", label: "Lowest (-2)" },
  { value: "low", label: "Low (-1)" },
  { value: "normal", label: "Normal (0)" },
  { value: "high", label: "High (+1)" },
  { value: "emergency", label: "Emergency (+2)" },
];

const DEFAULT_SOUNDS = [{ slug: "", label: "User default" }];

function priorityLabel(value) {
  const found = PRIORITY_OPTIONS.find((opt) => opt.value === value);
  return found ? found.label : value;
}

async function post(endpoint, payload = {}) {
  const resp = await fetch(API_BASE + "/" + endpoint, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": window.A0_CSRF || "",
    },
    credentials: "same-origin",
    body: JSON.stringify(payload),
  });
  const text = await resp.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : {};
  } catch (err) {
    data = { success: false, error: "Invalid JSON response from server." };
  }
  if (!resp.ok && (!data || !("success" in data))) {
    data = data || {};
    data.success = false;
    data.error = data.error || "HTTP " + resp.status;
  }
  return data;
}

export const store = createStore("push_zeroSetup", {
  loading: false,
  saving: false,
  testing: false,
  sending: false,
  loadingLimits: false,
  loadingSounds: false,
  didInit: false,
  configured: false,
  maskedToken: "",
  maskedUser: "",
  fields: {
    token: "",
    user: "",
    device: "",
    title: "Agent Zero",
    priority: "normal",
    sound: "",
    default_device: "",
    ttl: "",
    url: "",
    url_title: "",
    html: false,
    monospace: false,
    retry: 60,
    expire: 3600,
    callback: "",
    tags: "",
    timeout: 15,
    debug: false,
    default_callback: "",
  },
  statusMessage: "",
  statusTone: "info",
  testResults: [],
  limits: null,
  limitsError: "",
  sounds: DEFAULT_SOUNDS.slice(),
  soundFetched: false,
  priorityOptions: PRIORITY_OPTIONS,

  get isFirstRun() {
    return !this.configured;
  },

  get isConfigured() {
    return this.configured;
  },

  get hasEmergency() {
    return (this.fields.priority || "normal").toLowerCase() === "emergency";
  },

  get progressPercent() {
    const l = this.limits;
    if (!l || !l.limit || l.used == null) return 0;
    return Math.max(0, Math.min(100, Math.round((l.used / l.limit) * 100)));
  },

  get progressBlocks() {
    const total = 16;
    const filled = Math.round((this.progressPercent / 100) * total);
    return "█".repeat(filled) + "░".repeat(total - filled);
  },

  async init() {
    if (this.didInit) return;
    this.didInit = true;
    await this.refresh();
    await this.refreshSounds();
    await this.refreshLimits();
  },

  cleanup() {
    this.didInit = false;
    this.testResults = [];
    this.limits = null;
    this.limitsError = "";
    this.sounds = DEFAULT_SOUNDS.slice();
    this.soundFetched = false;
  },

  setStatus(message, tone = "info") {
    this.statusMessage = message;
    this.statusTone = tone;
  },

  async refresh() {
    this.loading = true;
    try {
      const data = await post("status");
      if (data && data.success) {
        this.configured = !!data.configured;
        this.maskedToken = data.masked_token || "";
        this.maskedUser = data.masked_user || "";
        const cfg = data.config || {};
        const defaults = cfg.defaults || {};
        const emergency = cfg.emergency || {};
        const advanced = cfg.advanced || {};
        this.fields.title = defaults.title || "Agent Zero";
        this.fields.priority = (defaults.priority || "normal").toLowerCase();
        this.fields.sound = defaults.sound || "";
        this.fields.default_device = defaults.device || "";
        this.fields.ttl = defaults.ttl || "";
        this.fields.url = defaults.url || "";
        this.fields.url_title = defaults.url_title || "";
        this.fields.html = !!defaults.html;
        this.fields.monospace = !!defaults.monospace;
        this.fields.retry = emergency.retry || 60;
        this.fields.expire = emergency.expire || 3600;
        this.fields.callback = emergency.callback || "";
        this.fields.timeout = advanced.timeout || 15;
        this.fields.debug = !!advanced.debug;
        this.fields.tags = Array.isArray(cfg.tags) ? cfg.tags.join(", ") : (cfg.tags || "");
        this.fields.default_callback = cfg.callback || "";
        if (this.configured) {
          this.setStatus("Connected to Pushover.", "success");
        } else {
          this.setStatus("Not configured yet.", "info");
        }
      } else {
        this.setStatus(data && data.error ? data.error : "Could not load Pushover status.", "error");
      }
    } catch (err) {
      this.setStatus("Could not load Pushover status: " + (err && err.message ? err.message : err), "error");
    } finally {
      this.loading = false;
    }
  },

  async save() {
    this.saving = true;
    try {
      const payload = { ...this.fields };
      const data = await post("save", payload);
      if (data && data.success) {
        this.maskedToken = data.masked_token || this.maskedToken;
        this.maskedUser = data.masked_user || this.maskedUser;
        this.configured = !!data.configured;
        // Wipe the token / user input fields so we don't leave plaintext in
        // the DOM after a successful save.
        this.fields.token = "";
        this.fields.user = "";
        toastFrontendSuccess("Pushover configuration saved.", "Pushover");
        this.setStatus("Configuration saved.", "success");
        await this.refresh();
        return true;
      }
      toastFrontendError(
        (data && data.error) || "Could not save the configuration.",
        "Pushover"
      );
      this.setStatus((data && data.error) || "Save failed.", "error");
      return false;
    } catch (err) {
      toastFrontendError("Save failed: " + (err && err.message ? err.message : err), "Pushover");
      return false;
    } finally {
      this.saving = false;
    }
  },

  async testConnection() {
    this.testing = true;
    this.testResults = [];
    try {
      const data = await post("test", {});
      this.testResults = (data && data.results) || [];
      if (data && data.success) {
        toastFrontendSuccess("Pushover connection validated.", "Pushover");
        this.setStatus("Credentials accepted by Pushover.", "success");
      } else {
        const detail = (data && data.results && data.results[0] && data.results[0].message) || (data && data.error) || "Test failed.";
        toastFrontendError(detail, "Pushover");
        this.setStatus(detail, "error");
      }
    } catch (err) {
      toastFrontendError("Test failed: " + (err && err.message ? err.message : err), "Pushover");
    } finally {
      this.testing = false;
    }
  },

  async sendTestNotification() {
    this.sending = true;
    try {
      const data = await post("test_notify", {});
      if (data && data.success) {
        toastFrontendSuccess((data && data.message) || "Test notification sent.", "Pushover");
        this.setStatus("Test notification sent.", "success");
      } else {
        const msg = (data && data.error) || "Could not send the test notification.";
        toastFrontendError(msg, "Pushover");
        this.setStatus(msg, "error");
      }
    } catch (err) {
      toastFrontendError("Send failed: " + (err && err.message ? err.message : err), "Pushover");
    } finally {
      this.sending = false;
    }
  },

  async refreshLimits() {
    this.loadingLimits = true;
    this.limitsError = "";
    try {
      const data = await post("limits", {});
      if (data && data.success) {
        this.limits = {
          limit: data.limit || null,
          used: data.used || 0,
          remaining: data.remaining || null,
          reset: data.reset || null,
        };
      } else {
        this.limits = null;
        this.limitsError = (data && data.error) || "Pushover did not return usage information.";
      }
    } catch (err) {
      this.limits = null;
      this.limitsError = (err && err.message) ? err.message : String(err);
    } finally {
      this.loadingLimits = false;
    }
  },

  async refreshSounds() {
    this.loadingSounds = true;
    try {
      const data = await post("sounds", {});
      this.soundFetched = true;
      if (data && data.success && Array.isArray(data.sounds) && data.sounds.length > 0) {
        this.sounds = data.sounds;
      } else {
        this.sounds = DEFAULT_SOUNDS.slice();
      }
    } catch (err) {
      this.sounds = DEFAULT_SOUNDS.slice();
    } finally {
      this.loadingSounds = false;
    }
  },

  async resetConfig() {
    const confirmed = window.confirm(
      "Reset Pushover?\n\nThis removes the stored Pushover configuration.\nAgent Zero will no longer be able to send notifications."
    );
    if (!confirmed) return;
    try {
      const data = await post("reset", { confirm: true });
      if (data && data.success) {
        toastFrontendSuccess("Pushover configuration cleared.", "Pushover");
        this.fields.token = "";
        this.fields.user = "";
        this.fields.device = "";
        this.configured = false;
        this.maskedToken = "";
        this.maskedUser = "";
        this.setStatus("Not configured.", "info");
        await this.refresh();
      } else {
        toastFrontendError((data && data.error) || "Reset failed.", "Pushover");
      }
    } catch (err) {
      toastFrontendError("Reset failed: " + (err && err.message ? err.message : err), "Pushover");
    }
  },

  toggleHtml() {
    if (this.fields.html) this.fields.monospace = false;
  },
  toggleMonospace() {
    if (this.fields.monospace) this.fields.html = false;
  },

  formatReset(resetValue) {
    if (resetValue == null) return "";
    if (typeof resetValue === "number") return resetValue;
    return resetValue;
  },

  statusLabel() {
    if (!this.configured) return "Not configured";
    return "Connected";
  },

  priorityDisplay(value) {
    return priorityLabel(value || "normal");
  },
});
