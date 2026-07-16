---
title: "Handling Flaky Networks in Mobile Apps"
slug: "handling-flaky-networks-mobile"
description: "Build mobile apps that survive bad networks with optimistic UI, idempotent retries, reachability-aware sync, and WebSocket reconnection users never notice."
datePublished: "2026-06-03"
dateModified: "2026-06-03"
tags: ["Mobile", "Networking", "Flutter", "Android", "iOS"]
keywords: "flaky network, mobile offline, retry strategy, optimistic UI, network reachability, mobile sync, exponential backoff"
faq:
  - q: "Should mobile apps retry failed requests automatically?"
    a: "Yes, but only idempotent requests or those with idempotency keys. Retrying a POST that creates a payment without deduplication is how you double-charge. GETs and idempotent PUTs can retry freely with backoff."
  - q: "How do you detect offline vs slow network?"
    a: "Do not trust OS 'connected' flags alone. Combine reachability callbacks with active probes — a lightweight HEAD request or ping to your API — and treat timeouts separately from hard failures."
  - q: "What is the best retry backoff for mobile?"
    a: "Full jitter exponential backoff: base delay doubling per attempt, capped at 30–60 seconds, with random jitter so thousands of reconnecting clients do not hammer your servers simultaneously."
---

Mobile networks lie. The status bar shows full bars while TCP stalls in a tunnel. Your API returns 200 but the response arrives after the client already timed out. Users blame the app, not the carrier — so the app has to behave as if connectivity is the exception, not the rule.

The answer is not "show an error dialog." It is optimistic UI, idempotent operations, reachability-aware queues, and reconnection logic that resumes without making the user tap Retry.

## Assume disconnect, design for resume

Every network call should have three planned outcomes: success, retryable failure, and terminal failure. Retryable covers timeouts, 502/503, and connection resets. Terminal covers 400/401/404 — repeating those will not help.

```dart
Future<T> withRetry<T>(Future<T> Function() fn, {int maxAttempts = 5}) async {
  var attempt = 0;
  while (true) {
    try {
      return await fn().timeout(const Duration(seconds: 15));
    } on TimeoutException {
      attempt++;
      if (attempt >= maxAttempts) rethrow;
      await Future.delayed(_jitterBackoff(attempt));
    }
  }
}

Duration _jitterBackoff(int attempt) {
  final base = Duration(milliseconds: 500 * (1 << attempt.clamp(0, 6)));
  final jitter = Random().nextInt(base.inMilliseconds ~/ 4);
  return base + Duration(milliseconds: jitter);
}
```

Cap attempts and surface honest state when you give up. Infinite spinners erode trust faster than an error message with a Retry button.

## Optimistic UI without optimistic data loss

Show the user's action immediately; reconcile when the server confirms. A message appears in the chat list before the POST completes. A checkbox toggles before sync finishes.

The rules:

- **Revert on hard failure** — if the server rejects, roll back UI and explain why
- **Queue for retry on soft failure** — if the network drops, keep the optimistic state and sync later
- **Never duplicate side effects** — assign client-generated IDs so retries are idempotent server-side

This overlaps heavily with [offline-first sync](https://blog.michaelsam94.com/offline-first-flutter-sync/) patterns: the optimistic layer is what users see; the sync engine is what makes it true.

## Reachability is not connectivity

`ConnectivityResult.wifi` means a radio is on, not that your API is reachable. I combine platform callbacks with an application-level probe:

| Signal | Tells you | Does not tell you |
|---|---|---|
| OS network callback | Interface up/down | API reachable |
| Captive portal | Likely no real internet | App-specific routing |
| API health HEAD | Your backend responds | WebSocket alive |
| Last successful sync | Data is fresh enough | Current request will succeed |

Use probes sparingly — battery matters. Probe on foreground resume, after connectivity changes, and before draining a large offline queue. Between those moments, infer from request outcomes.

## WebSockets on mobile need their own playbook

HTTP retries do not map cleanly to WebSockets. A dropped socket needs exponential backoff reconnect, resubscription to channels, and a catch-up read for anything missed. The server-side half of this is covered in [WebSocket architecture at scale](https://blog.michaelsam94.com/websocket-architecture-at-scale/); the client half is:

1. Backoff reconnect with jitter (same as HTTP)
2. Resend subscription manifest on every connect
3. Track last-seen sequence per channel
4. Fall back to polling when WebSocket fails repeatedly

On iOS, background execution limits how long you keep a socket open. Design for disconnect on background and fast resume on foreground rather than fighting the OS.

## Timeouts, cancellation, and request coalescing

Aggressive timeouts beat hanging UI. Fifteen seconds for a user-initiated action is a reasonable ceiling; background sync can wait longer on Wi-Fi.

Cancel in-flight requests when they no longer matter — user navigated away, search query changed, filter updated. Libraries like Dio and `URLSession` support cancellation; use it.

Coalesce duplicate requests. If three widgets ask for the same profile on a cold start, one network call should serve all three. [TanStack Query-style caching](https://blog.michaelsam94.com/tanstack-query-patterns/) on mobile (Riverpod async providers, React Query equivalents) solves this on the web; the same deduplication discipline applies natively.

## Surface honest sync state

Users tolerate waiting when they understand why. Three states beat a binary online/offline badge:

- **Synced** — server confirmed
- **Pending** — queued, will send when possible
- **Conflict** — server disagrees, user must choose

Hide sync mechanics behind copy users understand: "Sending…" not "Waiting for WebSocket ACK."

Instrument client-side success rates and latency percentiles. Server [SLOs](https://blog.michaelsam94.com/designing-for-observability-slos/) that ignore client timeouts paint a rosier picture than users experience.

## Test with bad networks on purpose

Simulate before users do it for you:

- Charles Proxy / Proxyman throttling
- Android Emulator network profiles
- iOS Network Link Conditioner
- Airplane mode toggles during active operations

Run through send-message-while-offline, pay-while-switching-Wi-Fi, and background-resume-mid-sync. If those three pass, most field complaints disappear.

## Background sync and platform constraints

iOS and Android treat background networking differently, and your retry strategy has to respect both. On Android, WorkManager is the right place for deferrable sync — it respects battery savers, metered networks, and Doze mode. On iOS, `URLSession` background transfers finish even if the user backgrounds the app, but you cannot keep a long-lived WebSocket alive indefinitely.

| Platform | Best for | Avoid |
|---|---|---|
| Android WorkManager | batched uploads, retry queues | running on every frame |
| iOS background URLSession | large file sync | assuming instant delivery |
| Foreground service (Android) | user-initiated live sync | permanent background sockets |

Design your queue with priorities: user-visible actions (send message, submit form) drain before analytics batches. Exponential backoff applies per queue item, not globally — one failing endpoint should not stall unrelated sync work.

Flaky networks are the default on mobile. Apps that feel fast and trustworthy are the ones that planned for disconnect from the first screen — not the ones that added offline mode in v3.

## Resources

- [Apple — URLSession background tasks](https://developer.apple.com/documentation/foundation/urlsession)
- [Android — WorkManager](https://developer.android.com/topic/libraries/architecture/workmanager)
- [MDN — Exponential backoff](https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/503)
- [AWS Architecture Blog — Exponential Backoff and Jitter](https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/)
- [web.dev — Reliable network requests](https://web.dev/articles/reliable)
