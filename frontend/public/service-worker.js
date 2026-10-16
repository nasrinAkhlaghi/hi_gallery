const SHELL_CACHE = "hi-gallery-shell-v1";
const STATIC_CACHE = "hi-gallery-static-v1";
const CACHE_PREFIX = "hi-gallery-";
const MAX_STATIC_ASSETS = 60;

self.addEventListener("install", (event) => {
  event.waitUntil(self.skipWaiting());
});

self.addEventListener("activate", (event) => {
  const currentCaches = new Set([SHELL_CACHE, STATIC_CACHE]);

  event.waitUntil(
    caches
      .keys()
      .then((names) =>
        Promise.all(
          names
            .filter((name) => name.startsWith(CACHE_PREFIX) && !currentCaches.has(name))
            .map((name) => caches.delete(name)),
        ),
      )
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  const url = new URL(request.url);

  if (
    request.method !== "GET" ||
    url.origin !== self.location.origin ||
    url.pathname === "/api" ||
    url.pathname.startsWith("/api/")
  ) {
    return;
  }

  if (request.mode === "navigate") {
    event.respondWith(
      (async () => {
        try {
          const response = await fetch(request);
          if (response.ok && response.type === "basic") {
            const shellCache = await caches.open(SHELL_CACHE);
            await shellCache.put("/", response.clone());
          }
          return response;
        } catch {
          return (await caches.match("/")) ?? Response.error();
        }
      })(),
    );
    return;
  }

  if (["script", "style", "image", "font"].includes(request.destination)) {
    event.respondWith(
      (async () => {
        try {
          const response = await fetch(request);
          if (response.ok && response.type === "basic") {
            const staticCache = await caches.open(STATIC_CACHE);
            await staticCache.put(request, response.clone());
            const cachedRequests = await staticCache.keys();
            if (cachedRequests.length > MAX_STATIC_ASSETS) {
              await staticCache.delete(cachedRequests[0]);
            }
          }
          return response;
        } catch {
          return (await caches.match(request)) ?? Response.error();
        }
      })(),
    );
  }
});
