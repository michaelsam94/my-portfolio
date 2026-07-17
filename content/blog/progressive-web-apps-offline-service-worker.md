---
title: "Offline PWAs with Service Workers"
slug: "progressive-web-apps-offline-service-worker"
description: "Build offline-capable PWAs with service workers: caching strategies, Workbox, background sync, and update flows that don't strand users on stale bundles."
datePublished: "2026-04-16"
dateModified: "2026-07-17"
tags: ["Web", "PWA", "Service Workers", "Frontend"]
keywords: "PWA offline service worker, Workbox caching strategies, service worker cache, offline first PWA, progressive web app"
faq:
  - q: "What is the difference between a service worker and a web worker?"
    a: "A service worker is a proxy between your app and the network — it intercepts fetch requests and can cache responses for offline use. Web workers run scripts in background threads for computation. Service workers enable offline PWAs; web workers enable parallel processing."
  - q: "Which caching strategy should a PWA use for API data?"
    a: "Network-first with cache fallback for frequently changing API data — try network, fall back to cache when offline. Cache-first suits static assets with hashed filenames. Stale-while-revalidate works for semi-static content like product catalogs."
  - q: "How do service worker updates reach users without breaking sessions?"
    a: "New service worker installs in waiting state until all tabs close or you call skipWaiting with user consent. Prompt 'Update available — refresh' rather than force-reloading mid-form. Version cache names (v1, v2) and delete old caches on activate."
---

Airplane mode used to mean our field technician app was a brick. Service workers turned it into something that loads the job list from cache, queues form submissions, and syncs when connectivity returns. The hard part wasn't registering `navigator.serviceWorker` — it was picking caching strategies that don't serve week-old prices or lose draft inspections when the worker updates mid-shift.

## Service worker lifecycle

```
Register ──► Install (precache) ──► Activate (cleanup old caches)
                    │                        │
                    └──── Waiting ───────────┘ (until tabs close or skipWaiting)
```

```javascript
// main.js
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js').then((reg) => {
    reg.addEventListener('updatefound', () => {
      const newWorker = reg.installing;
      newWorker.addEventListener('statechange', () => {
        if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
          showUpdateBanner(); // user chooses when to refresh
        }
      });
    });
  });
}
```

Never `skipWaiting()` silently on apps with forms in progress.

## Caching strategies

| Strategy | Flow | Best for |
|----------|------|----------|
| Cache-first | Cache → network if miss | Hashed JS/CSS, fonts |
| Network-first | Network → cache fallback | API, auth-sensitive |
| Stale-while-revalidate | Cache immediately, update cache in background | Avatars, catalog images |
| Network-only | Always network | Analytics, mutations |

```javascript
// sw.js with Workbox
import { precacheAndRoute } from 'workbox-precaching';
import { registerRoute } from 'workbox-routing';
import { NetworkFirst, StaleWhileRevalidate, CacheFirst } from 'workbox-strategies';
import { ExpirationPlugin } from 'workbox-expiration';

precacheAndRoute(self.__WB_MANIFEST);

registerRoute(
  ({ request }) => request.destination === 'document',
  new NetworkFirst({ cacheName: 'pages', networkTimeoutSeconds: 3 })
);

registerRoute(
  ({ url }) => url.pathname.startsWith('/api/'),
  new NetworkFirst({
    cacheName: 'api',
    plugins: [new ExpirationPlugin({ maxEntries: 50, maxAgeSeconds: 300 })],
  })
);

registerRoute(
  ({ request }) => ['style', 'script', 'font'].includes(request.destination),
  new CacheFirst({ cacheName: 'static-v2' })
);
```

## Offline UI and data

Show connectivity state:

```javascript
window.addEventListener('online', () => syncPendingSubmissions());
window.addEventListener('offline', () => showOfflineBanner());
```

Queue mutations in IndexedDB:

```javascript
async function submitInspection(data) {
  if (!navigator.onLine) {
    await idb.put('pending', { ...data, id: crypto.randomUUID() });
    return { queued: true };
  }
  return fetch('/api/inspections', { method: 'POST', body: JSON.stringify(data) });
}

async function syncPendingSubmissions() {
  for (const item of await idb.getAll('pending')) {
    await fetch('/api/inspections', { method: 'POST', body: JSON.stringify(item) });
    await idb.delete('pending', item.id);
  }
}
```

Background Sync API (`registration.sync.register('sync-inspections')`) retries when online — Chrome-first; have fallback online listener.

## App shell pattern

Precache minimal HTML/JS skeleton; fetch content into shell:

```html
<!-- index.html shell -->
<div id="app">Loading...</div>
<script src="/app.js"></script>
```

Shell loads offline instantly; data populates when available or from cache.

## Manifest and installability

```json
{
  "name": "Field Inspect",
  "short_name": "Inspect",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#ffffff",
  "theme_color": "#1a56db",
  "icons": [{ "src": "/icon-512.png", "sizes": "512x512", "type": "image/png" }]
}
```

Install prompt requires manifest + service worker + HTTPS.

## Pitfalls

- **Caching authenticated API responses** — scope cache by user or don't cache private data
- **Opaque responses from CDN** — CORS limits cache inspection
- **Infinite cache growth** — ExpirationPlugin max entries
- **Old SW serving broken app** — cache bust via build hash in cache name
- **Safari quirks** — test iOS storage eviction (7-day inactive limit for non-installed PWAs historically — verify current behavior)

## Storage quota management

Monitor `navigator.storage.estimate()` — prompt users to clear cache when quota exceeded. Implement cache eviction LRU for API responses. iOS may evict storage under pressure; critical data belongs in sync queue with user-visible "pending upload" state.

## Operational notes

Test service worker update flow with Playwright — register SW, deploy v2, assert update banner appears, user refresh loads new cache. SW bugs are invisible in unit tests without browser integration coverage.

Document offline limitations in UI — users who expect full feature parity offline without indication blame the app, not the connectivity gap.

Ship offline-capable flows with explicit sync status indicators — ambiguous spinners when offline erode trust more than honest "waiting for connection" messaging with retry button.

Version service worker file name in cache busting strategy — browsers cache sw.js aggressively; configure build pipeline to inject hash into registration URL when needed.

Add E2E tests that toggle browser offline mode in Playwright — service worker regressions rarely surface in unit tests without full browser lifecycle coverage.

Version service worker cache names on deploy — stale cache names serve old assets after deployment until user hard-refreshes.

## Cache versioning strategy

```javascript
const CACHE = 'app-v3';
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    )
  );
});
```

Bump cache name on every deploy. Stale-while-revalidate for API JSON; cache-first for hashed static assets.


## Navigation preload under real latency

Navigation Preload starts fetching HTML while the service worker thread spins up — on repeat visits this shaves 100–300ms on mid-tier Android. Enable in `activate`, call `event.preloadResponse` in your navigation handler, and fall back to cache when preload fails. Without fallback, flaky preload errors surface as blank pages.

```javascript
self.addEventListener('fetch', (event) => {
  if (event.request.mode !== 'navigate') return;
  event.respondWith(async function() {
    try {
      const preload = await event.preloadResponse;
      if (preload) return preload;
    } catch (_) {}
    const cached = await caches.match('/shell.html');
    return cached || fetch(event.request);
  }());
});
```

## IndexedDB migration when schema changes

Offline queues stored in IndexedDB need versioned upgrades — bump `onupgradeneeded` when adding indexes, never delete stores silently. Migration failures brick offline submit for users who skip app updates for weeks. Log IDB errors to RUM; they rarely throw to UI unless you wrap every read.

## Cross-origin isolation and SW

Some advanced APIs need COOP/COEP headers — service worker cached responses must include same headers or isolation breaks on repeat visit. Document header requirements in precache manifest review checklist.

## Third-party script offline behavior

Analytics and chat widgets often fail offline — wrap in try/catch and degrade silently; uncaught promise rejections in SW-controlled pages confuse error monitoring. Consider deferring third-party load until online probe succeeds.

## Production rollout notes

Offline PWAs fail in production when teams treat DevTools offline toggle as sufficient validation. Run throttled 3G profiles with packet loss during QA. Field users on construction sites lose connectivity mid-upload; your service worker must resume partial uploads or queue idempotently. Document maximum offline duration before cache staleness warnings appear. Pair service worker metrics with RUM: track cache hit ratio, sync queue depth, and failed flush count separately from page views.
## Field testing checklist

Before shipping offline mode, run through this checklist on physical devices: enable airplane mode mid-form-submit, kill app during background sync, deny storage quota then retry upload, update service worker with pending outbox items, and open two tabs with different cache generations. Each scenario should leave user data intact or show explicit recoverable error — never silent loss. Record videos of failures for QA tickets; service worker bugs reproduce poorly from text steps alone.

## Workbox runtime diagnostics

Enable `workbox-core` development logging in staging builds only — log cache strategy decisions with request URL and outcome. Forward aggregated cache hit/miss ratio to analytics weekly. Sudden miss spike after deploy often means cache name typo in registerRoute callback, not network outage.

## Closing operational guidance

Document service worker scope carefully — `/sw.js` scoped to `/` controls entire origin including admin subpaths you did not intend to cache. Narrow scope or split origins for admin vs customer PWA. Register scope review in security checklist alongside CSP updates. Ship changes behind feature flags, measure before and after on real traffic, and keep rollback one deploy revert away. Ship changes behind feature flags, measure before and after on real traffic, and keep rollback one deploy revert away. Ship changes behind feature flags, measure before and after on real traffic, and keep rollback one deploy revert away.

## Resources

- [MDN Service Worker API](https://developer.mozilla.org/en-US/docs/Web/API/Service_Worker_API)
- [Workbox documentation](https://developer.chrome.com/docs/workbox/)
- [web.dev offline storage guide](https://web.dev/articles/offline-cookbook)
- [IndexedDB API (MDN)](https://developer.mozilla.org/en-US/docs/Web/API/IndexedDB_API)
- [Background Sync specification](https://wicg.github.io/background-sync/spec/)
