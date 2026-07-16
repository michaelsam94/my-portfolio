---
title: "Web Push Notifications"
slug: "progressive-web-apps-push-notifications"
description: "Implement web push notifications: service worker push events, VAPID keys, permission UX, payload limits, and backend delivery with FCM or direct push."
datePublished: "2026-04-20"
dateModified: "2026-04-20"
tags: ["Web", "PWA", "Notifications", "Frontend"]
keywords: "web push notifications, VAPID keys, Push API service worker, PWA push notifications, FCM web push"
faq:
  - q: "Do PWAs need a native app to send push notifications?"
    a: "No. Web Push works through browser push services (FCM for Chrome, APNs for Safari 16.4+ installed PWAs) with a service worker receiving push events. Users must grant notification permission and install or engage with the site per browser rules."
  - q: "What are VAPID keys used for?"
    a: "Voluntary Application Server Identification — a public/private key pair identifying your application server to push services. The private key signs push requests; the public key goes in the browser subscription. Required for standards-compliant web push without vendor-specific keys."
  - q: "Why do users deny notification permission and how do you improve opt-in?"
    a: "Browsers block permission prompts triggered on page load without user gesture. Explain value first ('Get notified when your order ships'), then request on button click. Sites that prompt immediately see 80%+ denial rates."
---

Push notifications were the feature PM wanted parity with native. Web Push delivered — with caveats. Safari only fully joined in 16.4 for installed PWAs. Permission prompts blocked on first visit. Payloads capped around 4 KB. But for order updates and chat mentions, web push beats asking users to install an App Store app they'll delete in a week.

## Architecture overview

```
Your server ──► Push service (FCM/Mozilla) ──► Browser ──► Service Worker ──► Notification
     │                                              │
     └── subscription endpoint + keys from client ──┘
```

Client subscribes once; server stores subscription JSON; server sends HTTPS POST to push endpoint with encrypted payload.

## Generate VAPID keys

```bash
npx web-push generate-vapid-keys
# Public Key: BNcRd...
# Private Key: 3kT3...
```

Store private key server-side only. Public key in client subscription flow.

## Client subscription flow

```javascript
async function subscribeToPush() {
  const reg = await navigator.serviceWorker.ready;

  const permission = await Notification.requestPermission();
  if (permission !== 'granted') return null;

  const subscription = await reg.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(VAPID_PUBLIC_KEY),
  });

  await fetch('/api/push/subscribe', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(subscription),
  });

  return subscription;
}
```

Trigger from user action — "Enable notifications" button — never on load.

## Service worker push handler

```javascript
// sw.js
self.addEventListener('push', (event) => {
  let data = { title: 'Update', body: 'You have a new message' };

  if (event.data) {
    try {
      data = event.data.json();
    } catch {
      data.body = event.data.text();
    }
  }

  event.waitUntil(
    self.registration.showNotification(data.title, {
      body: data.body,
      icon: '/icon-192.png',
      badge: '/badge-72.png',
      data: { url: data.url || '/' },
      actions: data.actions || [],
    })
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const url = event.notification.data?.url || '/';
  event.waitUntil(clients.openWindow(url));
});
```

`userVisibleOnly: true` required — silent push restricted in most browsers.

## Server-side send (Node web-push)

```javascript
import webpush from 'web-push';

webpush.setVapidDetails(
  'mailto:support@acme.com',
  process.env.VAPID_PUBLIC_KEY,
  process.env.VAPID_PRIVATE_KEY
);

async function sendPush(subscription, payload) {
  try {
    await webpush.sendNotification(subscription, JSON.stringify(payload));
  } catch (err) {
    if (err.statusCode === 410 || err.statusCode === 404) {
      await removeSubscription(subscription.endpoint); // expired
    }
    throw err;
  }
}
```

Payload limit ~4 KB — send ID, fetch details on click if needed.

## Permission UX that works

1. Explain benefit in UI before prompt
2. Request on explicit opt-in click
3. If denied, show settings link — can't re-prompt
4. Soft ask: "Would you like notifications?" → Yes → browser prompt

Track funnel: shown → clicked → granted → denied. Optimize copy, not frequency.

## Platform differences

| Platform | Notes |
|----------|-------|
| Chrome/Android | FCM push service; works in tab and installed PWA |
| Firefox | Mozilla autopush |
| Safari macOS/iOS 16.4+ | Requires Add to Home Screen for iOS web push |
| Edge | Chromium path via FCM |

Test matrix on real devices — simulators miss push behavior.

## Backend subscription storage

```sql
CREATE TABLE push_subscriptions (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id),
  endpoint TEXT NOT NULL UNIQUE,
  p256dh TEXT NOT NULL,
  auth TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now()
);
```

Multiple subscriptions per user (phone + laptop). Prune on 410 Gone responses.

## Compliance and respect

- Easy unsubscribe in app settings
- Don't send marketing push without explicit consent (GDPR, CAN-SPAM adjacency)
- Rate limit — notification fatigue → uninstall + deny
- No sensitive content in payload body — visible on lock screen

## Subscription refresh

Browsers rotate push subscriptions periodically. Re-subscribe on service worker update and on `pushsubscriptionchange` event. Stale subscriptions in DB waste send attempts and skew delivery metrics.

## Operational notes

A/B test notification copy through same web push infrastructure — measure click-through without native app experimentation frameworks. Keep variant payloads under size limit.

Segment push topics by notification category — order updates versus marketing — so users can disable promotions without missing transactional alerts.

Test web push on installed PWA versus browser tab on iOS — behavior differs; QA matrix must cover both entry points before marketing announces mobile push support.

Respect quiet hours per user timezone in push scheduler — transactional alerts at 3 AM destroy opt-in rates faster than promotional over-send.

## VAPID keys and rotation

Web Push requires VAPID key pair:

```javascript
const webpush = require("web-push");
webpush.setVapidDetails(
  "mailto:ops@example.com",
  process.env.VAPID_PUBLIC_KEY,
  process.env.VAPID_PRIVATE_KEY
);
```

Rotate keys by supporting dual public keys during transition — old subscriptions signed with previous key still validate until users re-subscribe.

## Delivery failure handling

| HTTP status | Action |
|-------------|--------|
| 201 | Success |
| 404, 410 | Delete subscription from DB |
| 429 | Retry with exponential backoff |
| 5xx | Retry up to 3 times, then dead-letter |

```javascript
try {
  await webpush.sendNotification(subscription, payload);
} catch (err) {
  if (err.statusCode === 410) {
    await db.deleteSubscription(subscription.endpoint);
  }
}
```

Track delivery rate per campaign — sudden drops often mean expired VAPID keys or Apple push gateway changes.

## iOS PWA push specifics

Safari 16.4+ supports web push for installed PWAs only — not Safari tabs. UX flow:

1. Prompt install to home screen first
2. Request notification permission after install
3. Handle `notificationclick` to deep-link into app route

Test on real iOS devices — simulator push support is limited.

Pair with [progressive web apps offline service worker](https://blog.michaelsam94.com/progressive-web-apps-offline-service-worker/) for complete PWA notification infrastructure.

## Common production mistakes

Teams get push notifications wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of push notifications fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Resources

- [MDN Push API](https://developer.mozilla.org/en-US/docs/Web/API/Push_API)
- [web-push npm library](https://github.com/web-push-libs/web-push)
- [web.dev push notifications guide](https://web.dev/articles/push-notifications-overview)
- [Apple Safari web push for PWAs](https://developer.apple.com/documentation/usernotifications/sending-web-push-notifications-in-web-apps-and-browsers)
- [RFC 8030 — HTTP Web Push](https://www.rfc-editor.org/rfc/rfc8030)
