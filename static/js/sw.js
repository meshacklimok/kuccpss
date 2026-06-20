const CACHE = 'careernext-v6';
const OFFLINE_URL = '/offline/';

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE)
      .then(c => c.add(new Request(OFFLINE_URL, { cache: 'reload' })))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

// ── Web Push ────────────────────────────────────────────────────────────────
self.addEventListener('push', e => {
  let data = { title: 'CareerNext', body: 'New update from CareerNext', url: '/' };
  try { if (e.data) data = { ...data, ...e.data.json() }; } catch (_) {}

  e.waitUntil(
    self.registration.showNotification(data.title, {
      body:    data.body,
      icon:    '/static/images/icon-192.png',
      badge:   '/static/images/icon-192.png',
      data:    { url: data.url },
      vibrate: [200, 100, 200],
      requireInteraction: false,
    })
  );
});

self.addEventListener('notificationclick', e => {
  e.notification.close();
  const url = (e.notification.data && e.notification.data.url) || '/';
  e.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(list => {
      for (const c of list) {
        if (c.url === url && 'focus' in c) return c.focus();
      }
      return clients.openWindow(url);
    })
  );
});

self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET') return;
  const url = new URL(e.request.url);

  // Static assets: cache-first for load speed
  if (url.pathname.startsWith('/static/')) {
    e.respondWith(
      caches.match(e.request).then(cached => {
        const network = fetch(e.request).then(resp => {
          if (resp.ok) caches.open(CACHE).then(c => c.put(e.request, resp.clone()));
          return resp;
        });
        return cached || network;
      })
    );
    return;
  }

  // Page navigations: network-only; serve offline page if connection is lost
  if (e.request.mode === 'navigate') {
    e.respondWith(
      fetch(e.request).catch(() => caches.match(OFFLINE_URL))
    );
    return;
  }

  // Everything else: straight to network
  e.respondWith(
    fetch(e.request).catch(() => new Response('', { status: 503 }))
  );
});
