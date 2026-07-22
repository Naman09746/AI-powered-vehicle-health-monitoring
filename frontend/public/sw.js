// ── Vehicle Health Monitor — Service Worker ────────────────────
// Network-first for API calls, cache-first for static assets.
// response.clone() is always called immediately after fetch(),
// BEFORE any response body is consumed.

const CACHE = "vhm-v2";
const STATIC_ASSETS = ["/", "/fleet", "/login", "/manifest.json", "/icons/icon-192.png", "/icons/icon-192.svg"];
const API_PATTERN = /\/api\/v1\//;

// ── Install ───────────────────────────────────────────────────
self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(CACHE).then((cache) => {
      // Pre-cache critical static assets (best-effort — don't fail install)
      return cache.addAll(STATIC_ASSETS).catch(() => {});
    })
  );
  self.skipWaiting();
});

// ── Activate ──────────────────────────────────────────────────
self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.map((k) => {
          if (k !== CACHE) return caches.delete(k);
        })
      )
    ).then(() => self.clients.claim())
  );
});

// ── Fetch ─────────────────────────────────────────────────────
self.addEventListener("fetch", (e) => {
  const { request } = e;
  const url = new URL(request.url);

  // Only handle same-origin requests
  if (url.origin !== self.location.origin) return;

  // API calls: network-first (always get fresh data)
  if (API_PATTERN.test(url.pathname)) {
    e.respondWith(networkFirstWithCacheFallback(request));
    return;
  }

  // Static assets: cache-first for speed
  if (
    request.destination === "style" ||
    request.destination === "script" ||
    request.destination === "font" ||
    request.destination === "image"
  ) {
    e.respondWith(cacheFirstWithNetworkFallback(request));
    return;
  }

  // Navigation requests: network-first (so users always see latest)
  if (request.mode === "navigate") {
    e.respondWith(networkFirstWithCacheFallback(request));
    return;
  }

  // Everything else: network-first
  e.respondWith(networkFirstWithCacheFallback(request));
});

// ── Strategies ────────────────────────────────────────────────

/**
 * Network-first — try the network, fall back to cache on failure.
 *
 * CRITICAL: response.clone() is called IMMEDIATELY after fetch()
 * resolves, before any .text()/.json()/.cache.put() call, so the
 * body stream is never "already used" when clone() runs.
 */
async function networkFirstWithCacheFallback(request) {
  try {
    const response = await fetch(request);

    // Clone BEFORE reading body — this is the bug-free ordering
    const cacheClone = response.clone();

    // Update the cache asynchronously (don't await — let the response
    // through while the cache writes in the background)
    const cache = await caches.open(CACHE);
    cache.put(request, cacheClone).catch(() => {});

    return response;
  } catch {
    // Network failed — try the cache
    const cached = await caches.match(request);
    if (cached) return cached;

    // Nothing cached either — return a basic offline page for navigations
    if (request.mode === "navigate") {
      return new Response(
        "<html><body><h1>Offline</h1><p>Please check your connection.</p></body></html>",
        { status: 503, headers: { "Content-Type": "text/html" } }
      );
    }

    return new Response("Offline", { status: 503 });
  }
}

/**
 * Cache-first — serve from cache, update from network in background.
 */
async function cacheFirstWithNetworkFallback(request) {
  const cached = await caches.match(request);
  if (cached) {
    // Refresh cache in background (fire-and-forget)
    fetch(request)
      .then((response) => {
        if (response && response.ok) {
          const clone = response.clone(); // clone before cache.put
          caches.open(CACHE).then((cache) => cache.put(request, clone));
        }
      })
      .catch(() => {});
    return cached;
  }

  try {
    const response = await fetch(request);
    if (response && response.ok) {
      const clone = response.clone(); // clone before cache.put
      const cache = await caches.open(CACHE);
      cache.put(request, clone).catch(() => {});
    }
    return response;
  } catch {
    return new Response("Offline", { status: 503 });
  }
}
