/* Only public install assets are cached. Quotes, maps, login and app pages stay online. */
const CACHE = 'ctt-public-v1';
const PUBLIC_ASSETS = [
  '/offline.html', '/manifest.webmanifest', '/pwa.js', '/icons/icon-192.png',
  '/icons/icon-512.png', '/icons/maskable-512.png', '/icons/apple-touch-icon.png', '/icons/icon.svg'
];

self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(PUBLIC_ASSETS)));
  // Let existing quotes finish; the new worker takes over after the app closes.
});

self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(
    keys.filter(key => key.startsWith('ctt-public-') && key !== CACHE).map(key => caches.delete(key))
  )).then(() => self.clients.claim()));
});

self.addEventListener('fetch', event => {
  const request = event.request;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (request.mode === 'navigate') {
    event.respondWith(fetch(request).catch(() => caches.match('/offline.html')));
  } else if (url.pathname.startsWith('/api/')) {
    // Never read or write API results in Cache Storage, including POST responses.
    event.respondWith(fetch(request).catch(() => new Response(JSON.stringify({
      error: 'You are offline. Reconnect to calculate or update a quote.'
    }), {status: 503, headers: {'Content-Type': 'application/json', 'Cache-Control': 'no-store'}})));
  } else if (request.method === 'GET' && PUBLIC_ASSETS.includes(url.pathname) && !url.search) {
    event.respondWith(fetch(request).catch(() => caches.match(url.pathname)));
  }
});
