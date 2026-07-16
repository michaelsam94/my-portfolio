---
title: "Offline PWAs with Service Workers"
slug: "progressive-web-apps-offline-service-worker"
description: "Build offline-capable PWAs with service workers: caching strategies, Workbox, background sync, and update flows that don't strand users on stale bundles."
datePublished: "2026-04-16"
dateModified: "2026-04-16"
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

## Common production mistakes

Teams get offline service worker wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of offline service worker fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Debugging and triage workflow

When offline service worker misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [MDN Service Worker API](https://developer.mozilla.org/en-US/docs/Web/API/Service_Worker_API)
- [Workbox documentation](https://developer.chrome.com/docs/workbox/)
- [web.dev offline storage guide](https://web.dev/articles/offline-cookbook)
- [IndexedDB API (MDN)](https://developer.mozilla.org/en-US/docs/Web/API/IndexedDB_API)
- [Background Sync specification](https://wicg.github.io/background-sync/spec/)
