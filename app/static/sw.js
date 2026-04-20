self.addEventListener("install", (event) => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("push", (event) => {
  const payload = event.data ? event.data.json() : {};
  const title = payload.title || "Smart Nudge";
  const options = {
    body: payload.body || "A new learning nudge is ready.",
    icon: payload.icon || "/static/icons/smart-nudge.svg",
    badge: payload.badge || "/static/icons/smart-nudge.svg",
    data: {
      url: payload.url || "/dashboard",
      tracking_token: payload.tracking_token || null,
    },
  };

  event.waitUntil(
    (async () => {
      await self.registration.showNotification(title, options);
      const clients = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
      clients.forEach((client) => {
        client.postMessage({
          type: "push-received",
          title,
          body: options.body,
          receivedAt: new Date().toISOString(),
        });
      });
    })(),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();

  const targetUrl = event.notification.data?.url || "/dashboard";
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clients) => {
      const existingClient = clients.find((client) => client.url.includes(targetUrl) && "focus" in client);
      if (existingClient) {
        return existingClient.focus();
      }
      if (self.clients.openWindow) {
        return self.clients.openWindow(targetUrl);
      }
      return undefined;
    }),
  );
});
