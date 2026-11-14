/* ============================================================
   Service Worker de la PWA.
   - Guarda el shell (HTML, CSS, JS e iconos) para abrir sin internet.
   - Nunca cachea respuestas de la API.
   ============================================================ */

const VERSION = "1.1.0";
const CACHE = `qrlector-pwa-${VERSION}`;
const SCOPE = new URL("./", self.location.href).pathname;

const ASSETS = [
  "./",
  "./index.html",
  "./css/app.css",
  "./js/api.js",
  "./js/db.js",
  "./js/scanner.js",
  "./js/app.js",
  "./js/decoder-worker.js",
  "./vendor/zxing-wasm-reader.js",
  "./vendor/zxing_reader.wasm",
  "./manifest.webmanifest",
  "./icons/favicon.svg",
  "./icons/icon-180.png",
  "./icons/icon-192.png",
  "./icons/icon-512.png",
  "./icons/maskable-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE)
      .then((cache) => cache.addAll(ASSETS))
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter((key) => key.startsWith("qrlector-pwa-") && key !== CACHE).map((key) => caches.delete(key)));
    await self.clients.claim();
  })());
});

self.addEventListener("message", (event) => {
  if (event.data?.type === "SKIP_WAITING") self.skipWaiting();
});

async function networkFirst(request) {
  const cache = await caches.open(CACHE);
  try {
    const response = await fetch(request);
    if (response && response.ok) cache.put(request, response.clone());
    return response;
  } catch {
    const cached = await cache.match(request);
    if (cached) return cached;
    return (await cache.match("./index.html")) || Response.error();
  }
}

async function staleWhileRevalidate(request) {
  const cache = await caches.open(CACHE);
  const cached = await cache.match(request);
  const network = fetch(request)
    .then((response) => {
      if (response && response.ok) cache.put(request, response.clone());
      return response;
    })
    .catch(() => null);
  return cached || (await network) || Response.error();
}

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (!url.pathname.startsWith(SCOPE)) return;

  // Un shell versionado no mezcla JS nuevo con módulos antiguos.
  event.respondWith((async () => {
    const cache = await caches.open(CACHE);
    return (await cache.match(request)) || fetch(request);
  })());
});
