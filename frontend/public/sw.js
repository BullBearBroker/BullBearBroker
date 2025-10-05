self.addEventListener('push', (event) => {
  let data = {};
  try { data = event.data?.json?.() ?? {}; } catch {}
  const title = data.title || 'BullBear';
  const body = data.body || 'Ping!';
  const payload = data.payload || data;

  const broadcastToClients = async () => {
    const clients = await self.clients.matchAll({
      type: 'window',
      includeUncontrolled: true,
    });

    const message = {
      type: 'notification:dispatcher',
      title,
      body,
      payload,
      receivedAt: new Date().toISOString(),
    };

    for (const client of clients) {
      try {
        client.postMessage(message);
      } catch (error) {
        console.warn('[sw] Error enviando mensaje a cliente', error);
      }
    }

    await self.registration.showNotification(title, { body });
  };

  event.waitUntil(broadcastToClients());
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
});
