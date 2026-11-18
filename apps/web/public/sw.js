/* Static shell only. Account pages, API responses and mutations never enter CacheStorage. */
const CACHE = 'funilo-static-v2';
const ASSETS = [
  '/offline.html', '/offline.js', '/offline.css',
  '/fonts/Vazirmatn-Regular.ttf', '/fonts/Vazirmatn-Bold.ttf',
  '/icons/icon.svg', '/icons/icon-192.png', '/icons/icon-512.png',
  '/icons/maskable-512.png', '/icons/apple-touch-icon.png'
];
const STATIC_PATHS = new Set(ASSETS);

self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(ASSETS)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key.startsWith('funilo-static-') && key !== CACHE).map(key => caches.delete(key)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', event => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method !== 'GET' || url.origin !== self.location.origin || url.pathname.startsWith('/api/')) return;
  if (request.mode === 'navigate') {
    event.respondWith(fetch(request).catch(async () => {
      const cached = await caches.open(CACHE).then(cache => cache.match('/offline.html'));
      return cached || new Response('<!doctype html><html lang="fa" dir="rtl"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>مودیگو</title><p>اینترنت قطع شده؛ برای ادامه دوباره وصل شو.</p></html>', {
        status: 503, headers: {'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store'}
      });
    }));
    return;
  }
  if (STATIC_PATHS.has(url.pathname) && !url.search) {
    event.respondWith(caches.open(CACHE).then(async cache => (await cache.match(request)) || fetch(request)));
  }
});
