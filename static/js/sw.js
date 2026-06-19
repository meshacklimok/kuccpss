const CACHE = 'careernext-v5';
const PRECACHE = [
  '/',
  '/static/css/style.css',
  '/static/js/main.js',
];

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE).then(c => c.addAll(PRECACHE)).then(() => self.skipWaiting())
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

  // Homepage: cache-first so it works offline
  if (url.pathname === '/') {
    e.respondWith(
      caches.match('/').then(cached => {
        const network = fetch(e.request).then(resp => {
          if (resp.ok) caches.open(CACHE).then(c => c.put('/', resp.clone()));
          return resp;
        }).catch(() => cached);
        return cached || network;
      })
    );
    return;
  }

  // Static assets: cache-first
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

  // Everything else: network-first, fall back to cached homepage when offline
  e.respondWith(
    fetch(e.request).catch(() => caches.match('/'))
  );
});
