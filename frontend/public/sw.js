self.addEventListener('push', (event) => {
  let data = {};
  try { data = event.data?.json?.() ?? {}; } catch {}
  const title = data.title || 'BullBear';
  const body = data.body || 'Ping!';
  event.waitUntil(
    self.registration.showNotification(title, { body })
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
});
