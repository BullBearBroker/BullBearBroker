const STATIC_CACHE = "bullbear-static-v1";
const RUNTIME_CACHE = "bullbear-runtime-v1";
const STATIC_FILE_REGEX = /\.(?:js|css|ico|png|svg|jpg|jpeg|gif|webp|avif|woff2?)$/i;

self.addEventListener("install", (event) => {
  event.waitUntil(self.skipWaiting());
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((cacheNames) =>
        Promise.all(
          cacheNames.map((cacheName) => {
            if (![STATIC_CACHE, RUNTIME_CACHE].includes(cacheName)) {
              return caches.delete(cacheName);
            }
            return undefined;
          }),
        ),
      )
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("message", (event) => {
  if (event.data && event.data.type === "SKIP_WAITING") {
    self.skipWaiting();
  }
});

const cacheFirst = async (request) => {
  const cache = await caches.open(STATIC_CACHE);
  const cachedResponse = await cache.match(request);
  if (cachedResponse) {
    return cachedResponse;
  }

  const response = await fetch(request);
  if (response && response.ok) {
    cache.put(request, response.clone());
  }

  return response;
};

const networkFirst = async (request) => {
  const cache = await caches.open(RUNTIME_CACHE);
  try {
    const response = await fetch(request);
    if (response && response.ok) {
      cache.put(request, response.clone());
    }
    return response;
  } catch (error) {
    const cachedResponse = await cache.match(request);
    if (cachedResponse) {
      return cachedResponse;
    }
    throw error;
  }
};

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") {
    return;
  }

  if (event.request.cache === "only-if-cached" && event.request.mode !== "same-origin") {
    return;
  }

  const requestUrl = new URL(event.request.url);

  if (requestUrl.origin !== self.location.origin) {
    return;
  }

  if (STATIC_FILE_REGEX.test(requestUrl.pathname)) {
    event.respondWith(cacheFirst(event.request));
    return;
  }

  if (requestUrl.pathname.startsWith("/api/")) {
    event.respondWith(networkFirst(event.request));
  }
});

self.addEventListener("push", (event) => {
  const data = (() => {
    if (!event.data) {
      return {};
    }
    try {
      return event.data.json();
    } catch (error) {
      return {};
    }
  })();

  const title =
    typeof data.title === "string" && data.title.trim().length > 0 ? data.title : "BullBear";
  const body = typeof data.body === "string" ? data.body : "Ping!";
  const payload =
    data && typeof data.payload === "object" && data.payload !== null ? data.payload : data;

  const broadcastToClients = async () => {
    const clients = await self.clients.matchAll({
      type: "window",
      includeUncontrolled: true,
    });

    const message = {
      type: "notification:dispatcher",
      title,
      body,
      payload,
      receivedAt: new Date().toISOString(),
    };

    await Promise.all(clients.map((client) => client.postMessage(message)));

    await self.registration.showNotification(title, {
      body,
      data: payload,
    });
  };

  event.waitUntil(broadcastToClients());
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const targetUrl = (event.notification.data && event.notification.data.url) || "/";
  const absoluteUrl = new URL(targetUrl, self.location.origin).href;

  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clientList) => {
      for (const client of clientList) {
        if (client.url === absoluteUrl) {
          return client.focus();
        }
      }
      return self.clients.openWindow(absoluteUrl);
    }),
  );
});
