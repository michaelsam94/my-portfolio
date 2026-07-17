---
title: "Progressive Web Apps in 2026"
slug: "progressive-web-apps-2026"
description: "Where PWAs actually stand in 2026: service workers, installability, Web Push on iOS, offline strategies, and an honest take on when a PWA beats a native app."
datePublished: "2026-07-03"
dateModified: "2026-07-17"
tags: ["PWA", "Web", "Offline", "Mobile"]
keywords: "PWA, progressive web apps, service workers, installable web apps, offline web, Web Push, web app manifest"
faq:
  - q: "Can PWAs send push notifications on iOS in 2026?"
    a: "Yes. Since iOS 16.4, installed PWAs (added to the Home Screen) can receive Web Push notifications. The catch is they only work for installed PWAs, not tabs, and the user must add the app to the Home Screen and grant permission — so the install prompt UX matters more on iOS."
  - q: "Are PWAs still relevant with native apps everywhere?"
    a: "Yes, for the right use case. PWAs win on reach (no app store, instant load, one codebase across platforms) and update speed. Native still wins for deep OS integration, heavy graphics, and features the web can't reach. The decision is workload-specific, not ideological."
  - q: "What makes a web app installable as a PWA?"
    a: "A valid web app manifest with a name, icons, start URL, and display mode, served over HTTPS, plus a registered service worker. Browsers use these signals to offer an install prompt. Meeting the installability criteria is what turns a website into an installable app."
---

Every few years someone declares PWAs dead, and every few years they quietly gain another capability that used to be native-only. The 2026 reality: progressive web apps are a mature, capable platform for a large class of applications, held back less by technology than by app-store politics and a few stubborn gaps. If your app is content, commerce, productivity, or communication — and doesn't need deep OS hooks — a PWA in 2026 is a genuinely strong default.

I say that as someone who ships native mobile for a living. The interesting question isn't "PWA or native" as a tribe; it's where the line honestly sits now, and it has moved.

## The three pillars, still

A PWA is a normal website that adds three things: a **web app manifest**, a **service worker**, and **HTTPS**. Those turn a site into something installable, offline-capable, and app-like.

The manifest tells the browser how to present the installed app:

```json
{
  "name": "Acme Field Reports",
  "short_name": "Reports",
  "start_url": "/?source=pwa",
  "display": "standalone",
  "background_color": "#0b0b0b",
  "theme_color": "#0b0b0b",
  "icons": [
    { "src": "/icons/192.png", "sizes": "192x192", "type": "image/png" },
    { "src": "/icons/512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable" }
  ]
}
```

Meet the installability criteria — valid manifest, service worker, served over HTTPS — and the browser offers to add it to the home screen, where it launches without browser chrome and behaves like a native app.

## Service workers are where the power is

The service worker is a background script that sits between your app and the network, intercepting requests. It's what makes offline, caching, and push possible. The mental model that trips people up: it's a *separate* thread with its own lifecycle, not part of your page.

A pragmatic offline strategy for most apps is **stale-while-revalidate** for content and **cache-first** for static assets:

```js
self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.destination === "document" || request.destination === "") {
    event.respondWith(
      caches.open("pages").then(async (cache) => {
        const cached = await cache.match(request);
        const network = fetch(request).then((res) => {
          cache.put(request, res.clone());
          return res;
        }).catch(() => cached);          // fall back to cache offline
        return cached || network;         // serve cache fast, update in bg
      })
    );
  }
});
```

Don't hand-roll this in production — Workbox handles the routing, cache expiration, and versioning correctly, and cache invalidation is exactly the kind of thing you get subtly wrong by hand. For genuinely offline-first apps that sync when connectivity returns, the caching layer is only half the story; the data-sync layer is the hard part, and it borrows the same thinking as [offline-first sync](https://blog.michaelsam94.com/offline-first-flutter-sync/) and [local-first apps with CRDTs](https://blog.michaelsam94.com/local-first-apps-crdts/).

## Web Push finally works (mostly) everywhere

The single biggest change for PWAs in recent years is that iOS caught up. Since iOS 16.4, installed PWAs can receive Web Push notifications. That closed the gap that used to end most "should we build a PWA?" conversations on mobile.

The caveats are worth stating plainly, because they shape the UX:

- Push on iOS works **only for installed PWAs**, not for the site open in a tab. So your install-to-home-screen flow becomes load-bearing.
- The user must explicitly add to Home Screen — iOS won't prompt automatically the way Android's install banners can.
- Permission prompts should be requested in context, after the user does something that implies they want notifications, not on first load.

On Android and desktop, Web Push has worked for years via the Push API and Notifications API, backed by a push service and VAPID keys. The API is standardized; the platform behavior is what varies.

## PWA vs native in 2026: an honest table

| Capability | PWA | Native |
|---|---|---|
| Reach / no app store | Strong | Weak (store gatekeeping) |
| Instant load, no install | Strong | Weak |
| Update speed | Deploy = shipped | Store review lag |
| Push notifications | Yes (installed) | Yes |
| Offline | Yes (service worker) | Yes |
| Deep OS integration | Limited | Full |
| Heavy graphics / AR | Improving (WebGPU) | Full |
| Background work | Constrained | Full |
| Single codebase across platforms | Strong | Weaker |

The web has closed a lot of gaps — WebGPU for graphics, the File System Access API, Web Share, badging, and more. What remains genuinely native-only is deep background execution, tight OS integration (widgets, deep contact/calendar hooks), and the most demanding real-time graphics. If your app lives there, ship native or a hybrid.

## The parts people still get wrong

**Treating the service worker as fire-and-forget.** A bad service worker can serve stale assets forever and be maddening to debug. Version your caches, clean up old ones on `activate`, and always have a way to force an update. A broken SW cached at a user's device is the PWA equivalent of a bricked deploy.

**Ignoring the install funnel.** On iOS especially, if you don't guide users to "Add to Home Screen," they never get push or the standalone experience. Design the prompt; don't assume the browser does it for you.

**Skipping the performance basics.** PWA machinery doesn't make a slow site fast. Core Web Vitals still decide whether the thing feels like an app. The service worker helps repeat visits; the first visit is on you.

**Not testing offline for real.** "Works when I toggle offline in DevTools" is not the same as flaky-network reality. Real mobile networks are the hostile case — the same problems I've written about in [handling flaky networks on mobile](https://blog.michaelsam94.com/handling-flaky-networks-mobile/) apply directly to PWAs.

## Where I'd reach for a PWA

Reach for a PWA when reach and update velocity matter more than deep OS integration: content sites, storefronts, dashboards, internal tools, communication apps. You get one codebase, instant loads, no store review, offline support, and — now — push on all major platforms. Reach for native when you need background execution, heavy graphics, or OS features the web can't touch, and consider a hybrid when you want most of the web's velocity with a few native capabilities bolted on.

The technology arrived a while ago. In 2026 the PWA decision is a product decision about your specific app's needs, not a bet on whether the platform is ready — it is.


## Web Share Target and badging in production

Register your PWA as a share target so Android users can send photos or PDFs directly into your app from the system sheet. The manifest `share_target` entry must align with routes your service worker can offline-queue — a share target that 404s when offline trains users to abandon the installed app. Test share intents with large files; mobile browsers kill SWs that block the main thread during upload prep.

The Badging API (`navigator.setAppBadge`) surfaces unread counts on home-screen icons without push. Pair badge updates with push notifications carefully: clear the badge when the user opens the inbox view, not only when they dismiss notifications. iOS support for badging on installed PWAs arrived alongside Web Push — verify current Safari release notes before assuming parity with Android.

## CrUX-driven PWA investment cases

Before committing eng weeks to install UX, pull Chrome UX Report data for your origin. If LCP and INP already pass thresholds but return-visitor rate is high, install prompts may move retention more than performance work. Conversely, a fast site with terrible offline behavior shows high bounce on `navigator.onLine === false` events in RUM — fix service worker strategy before marketing install banners.

## Resources

- [MDN — Progressive web apps](https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps)
- [web.dev — Learn PWA](https://web.dev/learn/pwa/)
- [MDN — Service Worker API](https://developer.mozilla.org/en-US/docs/Web/API/Service_Worker_API)
- [Workbox — service worker libraries](https://developer.chrome.com/docs/workbox)
- [MDN — Web Push API](https://developer.mozilla.org/en-US/docs/Web/API/Push_API)
- [W3C — Web App Manifest](https://www.w3.org/TR/appmanifest/)
