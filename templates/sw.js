// Minimal service worker: installability + cache-first for static assets.
const CACHE = 'wk-static-v1';
self.addEventListener('install', (e) => { self.skipWaiting(); });
self.addEventListener('activate', (e) => { e.waitUntil(clients.claim()); });
self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET' || !url.pathname.startsWith('/static/')) return;
  e.respondWith(caches.open(CACHE).then(async (c) => {
    const hit = await c.match(e.request);
    if (hit) return hit;
    const res = await fetch(e.request);
    if (res.ok) c.put(e.request, res.clone());
    return res;
  }));
});
