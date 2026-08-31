/* EntreCenas: instalação PWA sem persistir respostas ou dados privados. */
const CACHE_NAME = "entrecenas-shell-v1";
const PUBLIC_ASSETS = [
  "/app/static/manifest.webmanifest",
  "/app/static/entrecenas-icon.svg"
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(PUBLIC_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(
      keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
    ))
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  const url = new URL(request.url);
  const isPublicAsset = request.method === "GET" &&
    url.origin === self.location.origin &&
    PUBLIC_ASSETS.includes(url.pathname);

  if (isPublicAsset) {
    event.respondWith(
      caches.match(request).then((cached) => cached || fetch(request))
    );
  }
});
