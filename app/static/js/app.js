(function () {
  const ready = (fn) => {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", fn, { once: true });
    } else {
      fn();
    }
  };

  const qs = (selector, root = document) => root.querySelector(selector);
  const qsa = (selector, root = document) => Array.from(root.querySelectorAll(selector));
  const setStatus = (target, text, tone) => {
    if (!target) return;
    target.textContent = text;
    target.className = `status-pill status-${tone || "neutral"}`;
  };

  const base64ToUint8Array = (value) => {
    const padding = "=".repeat((4 - (value.length % 4)) % 4);
    const normalized = (value + padding).replace(/-/g, "+").replace(/_/g, "/");
    const raw = window.atob(normalized);
    const buffer = new Uint8Array(raw.length);
    for (let index = 0; index < raw.length; index += 1) {
      buffer[index] = raw.charCodeAt(index);
    }
    return buffer;
  };

  const fetchJson = async (url, options) => {
    const response = await fetch(url, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
    if (!response.ok) {
      let detail = `Request failed: ${response.status}`;
      try {
        const payload = await response.json();
        detail = payload.detail || payload.message || detail;
      } catch (error) {
        // Ignore JSON parsing failures and keep the fallback message.
      }
      throw new Error(detail);
    }
    return response.json();
  };

  const wireCopyButtons = () => {
    qsa("[data-copy]").forEach((button) => {
      button.addEventListener("click", async () => {
        const sourceSelector = button.getAttribute("data-copy");
        const target = sourceSelector ? qs(sourceSelector) : null;
        const value = target?.value ?? target?.textContent ?? "";
        if (!value) return;

        try {
          await navigator.clipboard.writeText(value.trim());
          const original = button.textContent;
          button.textContent = "Copied";
          button.classList.add("btn-success");
          window.setTimeout(() => {
            button.textContent = original;
            button.classList.remove("btn-success");
          }, 1400);
        } catch (error) {
          console.error(error);
        }
      });
    });
  };

  const wirePreviewFields = () => {
    const previewRoot = qs("[data-preview-root]");
    if (!previewRoot) return;

    const fields = {
      agent_name: previewRoot.querySelector("[data-preview-agent-name]"),
      module_title: previewRoot.querySelector("[data-preview-module-title]"),
      peak_window: previewRoot.querySelector("[data-preview-peak-window]"),
      channel: previewRoot.querySelector("[data-preview-channel]"),
      streak: previewRoot.querySelector("[data-preview-streak]"),
      dnd: previewRoot.querySelector("[data-preview-dnd]"),
    };

    const update = () => {
      const agentName = qs("[data-template-agent-name]")?.value || "Lin";
      const moduleTitle = qs("[data-template-module-title]")?.value || "Travel Insurance";
      const peakWindow = qs("[data-template-peak-window]")?.value || "09:00";
      const channel = qs("[data-template-channel]")?.value || "LINE";
      const streak = qs("[data-template-streak]")?.value || "3-day streak";
      const dnd = qs("[data-template-dnd]")?.value || "20:00";

      if (fields.agent_name) fields.agent_name.textContent = agentName;
      if (fields.module_title) fields.module_title.textContent = moduleTitle;
      if (fields.peak_window) fields.peak_window.textContent = peakWindow;
      if (fields.channel) fields.channel.textContent = channel;
      if (fields.streak) fields.streak.textContent = streak;
      if (fields.dnd) fields.dnd.textContent = dnd;
    };

    qsa("[data-template-field]").forEach((input) => {
      input.addEventListener("input", update);
      input.addEventListener("change", update);
    });

    update();
  };

  const registerPushSetup = () => {
    const button = qs("[data-push-enable]");
    const testButton = qs("[data-push-test]");
    const localTestButton = qs("[data-push-local-test]");
    const statusSelector =
      button?.getAttribute("data-status-target") ||
      testButton?.getAttribute("data-status-target") ||
      localTestButton?.getAttribute("data-status-target") ||
      "";
    const statusTarget = qs(statusSelector);
    const debugTarget = qs("[data-push-debug]");
    if (!button) return;

    const subscribeEndpoint = button.getAttribute("data-subscribe-endpoint") || "/push/subscribe";
    const vapidUrl = button.getAttribute("data-vapid-url") || "/push/vapid-public-key";

    const runSetup = async () => {
      if (!("Notification" in window) || !("serviceWorker" in navigator) || !("PushManager" in window)) {
        setStatus(statusTarget, "Push is not supported on this browser.", "warning");
        return;
      }

      try {
        const permission = await Notification.requestPermission();
        if (permission !== "granted") {
          setStatus(statusTarget, "Notification permission was not granted.", "warning");
          return;
        }

        const registration = await navigator.serviceWorker.register("/sw.js", { scope: "/" });
        const { key } = await fetchJson(vapidUrl);
        const subscription = await registration.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: base64ToUint8Array(key),
        });

        await fetchJson(subscribeEndpoint, {
          method: "POST",
          body: JSON.stringify(subscription.toJSON()),
        });

        setStatus(statusTarget, "Push is enabled and ready.", "success");
      } catch (error) {
        console.error(error);
        setStatus(statusTarget, "We could not finish push setup yet.", "error");
      }
    };

    button.addEventListener("click", runSetup);

    testButton?.addEventListener("click", async () => {
      const endpoint = testButton.getAttribute("data-test-endpoint") || "/notifications/push/test";
      try {
        await fetchJson(endpoint, { method: "POST" });
        setStatus(statusTarget, "Test push dispatched.", "success");
        if (debugTarget) debugTarget.textContent = "Debug status: server accepted the push dispatch request.";
      } catch (error) {
        console.error(error);
        setStatus(statusTarget, error.message || "Test push could not be sent yet.", "error");
        if (debugTarget) debugTarget.textContent = `Debug status: ${error.message || "Push dispatch failed."}`;
      }
    });

    localTestButton?.addEventListener("click", async () => {
      try {
        if (Notification.permission !== "granted") {
          const permission = await Notification.requestPermission();
          if (permission !== "granted") {
            throw new Error("Notification permission was not granted.");
          }
        }
        const registration = await navigator.serviceWorker.ready;
        await registration.showNotification("Smart Nudge local test", {
          body: "If you can see this, the browser can display notifications on this device.",
          icon: "/static/icons/smart-nudge.svg",
          badge: "/static/icons/smart-nudge.svg",
          data: { url: "/preferences" },
        });
        setStatus(statusTarget, "Local notification displayed.", "success");
        if (debugTarget) debugTarget.textContent = "Debug status: local notification display succeeded.";
      } catch (error) {
        console.error(error);
        setStatus(statusTarget, error.message || "Local notification could not be displayed.", "error");
        if (debugTarget) debugTarget.textContent = `Debug status: ${error.message || "Local display failed."}`;
      }
    });

    navigator.serviceWorker?.addEventListener("message", (event) => {
      const payload = event.data || {};
      if (payload.type !== "push-received") return;
      const receivedAt = payload.receivedAt ? new Date(payload.receivedAt).toLocaleTimeString() : "just now";
      setStatus(statusTarget, `Push received at ${receivedAt}.`, "success");
      if (debugTarget) {
        debugTarget.textContent = `Debug status: push event received at ${receivedAt}. If no banner appeared, Chrome or macOS likely suppressed the visible alert even though the notification API succeeded.`;
      }
    });
  };

  const wireChannelTabs = () => {
    qsa("[data-channel-tab]").forEach((tab) => {
      tab.addEventListener("click", () => {
        const group = tab.closest("[data-channel-group]");
        if (!group) return;
        qsa("[data-channel-tab]", group).forEach((item) => item.classList.remove("is-active"));
        tab.classList.add("is-active");
        const selected = tab.getAttribute("data-channel-tab");
        const target = qs("[data-channel-selected]");
        if (target) target.textContent = selected || "channel";
      });
    });
  };

  const wireLineSetup = () => {
    const codeField = qs("[data-line-link-code]");
    const refreshButton = qs("[data-line-link-refresh]");
    const statusTarget = qs("[data-line-link-status]");
    const monitorRoot = qs("[data-line-link-monitor]");
    if (!codeField && !refreshButton && !monitorRoot) return;

    const maybeLinkCode = async () => {
      const endpoint = refreshButton?.getAttribute("data-line-link-endpoint");
      if (!endpoint) return;

      try {
        const payload = await fetchJson(endpoint, { method: "POST" });
        if (codeField && payload.link_code) codeField.value = payload.link_code;
        if (statusTarget) setStatus(statusTarget, "A new link code is ready.", "success");
      } catch (error) {
        console.error(error);
        if (statusTarget) setStatus(statusTarget, "Could not refresh the LINE link code.", "error");
      }
    };

    refreshButton?.addEventListener("click", maybeLinkCode);

    const statusEndpoint = monitorRoot?.getAttribute("data-line-status-endpoint");
    const lineStatusPill = qs("#lineLinkStatus");
    const preferencesLineStatus = qs("#lineStatus");
    const alreadyLinked = monitorRoot?.getAttribute("data-line-linked") === "true";
    if (!statusEndpoint || alreadyLinked) return;

    let completed = false;
    const pollStatus = async () => {
      if (completed) return;

      try {
        const payload = await fetchJson(statusEndpoint, { method: "GET" });
        if (!payload.linked) return;

        completed = true;
        setStatus(lineStatusPill, "Linked", "success");
        setStatus(preferencesLineStatus, payload.line_status || "Linked", payload.line_status_tone || "success");
        if (statusTarget) {
          const masked = payload.masked_line_user_id ? ` (${payload.masked_line_user_id})` : "";
          statusTarget.textContent = `LINE linked successfully${masked}. Refreshing this page to show the ready state.`;
        }
        window.setTimeout(() => window.location.reload(), 1200);
      } catch (error) {
        console.error(error);
      }
    };

    window.setTimeout(pollStatus, 1500);
    window.setInterval(pollStatus, 4000);
  };

  const registerNotificationPreview = () => {
    if ("Notification" in window && Notification.permission === "default") {
      const hint = qs("[data-push-permission-hint]");
      if (hint) hint.textContent = "Browser permission has not been granted yet.";
    }
  };

  ready(() => {
    wireCopyButtons();
    wirePreviewFields();
    registerPushSetup();
    wireChannelTabs();
    wireLineSetup();
    registerNotificationPreview();
  });
})();
