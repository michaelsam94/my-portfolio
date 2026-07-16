---
title: "Backend for Frontend (BFF): When and How"
seoTitle: "Backend for Frontend Pattern: When and How to Use It"
slug: "backend-for-frontend-bff"
description: "A BFF shapes backend data for one client — mobile, web, or admin — so domain services stay clean and your app stops making six API calls per screen load."
datePublished: "2026-05-17"
dateModified: "2026-05-19"
tags: ["Architecture", "BFF", "API Design", "Mobile", "Backend"]
keywords: "backend for frontend, BFF pattern, API gateway vs BFF, mobile backend, GraphQL BFF, Sam Newman, client-specific API, aggregation layer"
faq:
  - q: "What is a Backend for Frontend?"
    a: "A BFF is a thin backend layer tailored to one client experience — mobile app, web dashboard, admin panel. It aggregates calls to domain services and returns exactly the shape that client needs."
  - q: "How is a BFF different from an API gateway?"
    a: "An API gateway handles cross-cutting concerns — auth, rate limiting, routing. A BFF handles client-specific logic — data aggregation, response shaping, protocol translation. They complement each other; a BFF often sits behind a gateway."
  - q: "When do I not need a BFF?"
    a: "When you have one client type, a stable API shape, and no aggregation pain. A small team with a web app and five endpoints doesn't need a BFF. The pattern pays off when client needs diverge."
---

A Backend for Frontend (BFF) is a dedicated API layer that speaks the language of one client — your mobile app, your web dashboard, your admin panel — and translates behind the scenes to domain services that shouldn't care about screen layouts. Without it, your Flutter app makes six REST calls to render the home screen, your domain services sprout mobile-specific fields, and every new UI iteration becomes a backend migration. With it, the app makes one call, gets one JSON blob shaped for that screen, and your session service stays focused on sessions.

I built a BFF for the [EV charging platform](https://blog.michaelsam94.com/how-i-architected-an-ev-charging-platform/) because the Flutter app needed a fundamentally different data shape than the ops dashboard — and because real-time charger state needed [WebSocket fan-out](https://blog.michaelsam94.com/websocket-architecture-at-scale/) that no generic REST endpoint could provide cleanly.

## BFF vs API gateway vs monolith API

These three get conflated constantly:

```
Mobile App ──▶ BFF (mobile)  ──▶ Session Service
Web Dashboard ▶ BFF (web)    ──▶ Billing Service
Admin Panel  ──▶ BFF (admin)  ──▶ Notification Service
                    │
              API Gateway (auth, rate limit, TLS)
```

| Layer | Responsibility | Owned by |
|---|---|---|
| API Gateway | Auth, rate limiting, TLS termination, routing | Platform team |
| BFF | Aggregation, response shaping, client-specific logic | Client team (mobile team owns mobile BFF) |
| Domain service | Business logic, persistence, events | Domain team |

The BFF is **not** a place for business rules. If your BFF calculates pricing, you've pushed domain logic too far outward. It aggregates, transforms, and adapts — nothing more.

## When a BFF earns its keep

**Multiple clients, divergent needs.** The mobile app shows `{ sessionId, status, chargerName, kWh }`. The admin dashboard shows `{ sessionId, status, chargerName, kWh, userEmail, paymentMethod, tariff, siteOperator }`. Same domain, different shapes. Without a BFF, you either over-fetch on mobile or maintain `?fields=` query params that nobody documents.

**Aggregation across services.** The home screen needs active session (session service), nearby chargers (geo service), and account balance (billing service). Three calls from the client means three failure modes, three loading spinners, and latency that adds up on a 3G connection in Cairo.

**Protocol translation.** Your domain services speak gRPC internally. The mobile app needs REST + WebSocket. The BFF translates — it doesn't reimplement.

**Different auth models.** Mobile uses OAuth device flow. Admin uses SAML. The BFF handles client-specific auth and passes a normalized identity to domain services.

## What the mobile BFF looked like

One endpoint, one response, one round trip:

```typescript
// bff-mobile/routes/homeScreen.ts
app.get("/api/v1/home", async (req, res) => {
  const userId = req.user.id;

  const [session, nearbyChargers, balance] = await Promise.all([
    sessionClient.getActive(userId),
    geoClient.findNearby(req.query.lat, req.query.lng, { limit: 5 }),
    billingClient.getBalance(userId),
  ]);

  res.json({
    activeSession: session
      ? { id: session.id, status: session.status, chargerName: session.charger.name, kWh: session.meterTotal }
      : null,
    nearbyChargers: nearbyChargers.map(c => ({
      id: c.id, name: c.name, distance: c.distanceM, available: c.status === "Available",
    })),
    balance: { amount: balance.available, currency: balance.currency },
  });
});
```

The Flutter app calls `GET /api/v1/home` and renders. It doesn't know session, geo, and billing are separate services. When billing moves to a new service or geo adds a field, the BFF changes — the app doesn't.

For real-time updates, the BFF also hosted the WebSocket connection:

```typescript
// Client connects to BFF WebSocket
// BFF subscribes to internal events and pushes client-specific payloads
wsServer.on("connection", (socket, userId) => {
  eventBus.subscribe(`session.${userId}`, (event) => {
    socket.send(JSON.stringify({
      type: "sessionUpdate",
      data: { id: event.sessionId, status: event.status, kWh: event.meterTotal },
    }));
  });
});
```

The domain services publish events via the [transactional outbox](https://blog.michaelsam94.com/event-driven-outbox-pattern/); the BFF decides what the mobile client sees. Session state changes propagate in seconds, not on the next poll.

## One BFF per client type, not per client

Sam Newman (who coined the pattern) is explicit: **one BFF per frontend experience**, not one BFF per app version or per developer preference.

| Client | BFF | Why separate |
|---|---|---|
| Flutter mobile app | `bff-mobile` | Compact payloads, WebSocket, offline-tolerant |
| Web ops dashboard | `bff-web` | Rich data, pagination, export endpoints |
| Partner API | No BFF — use REST API directly | Third parties need stable, documented contracts |

If mobile and web need 80% the same data, resist the urge to merge BFFs. The 20% difference will grow, and you'll end up with `if (client === 'mobile')` branches everywhere.

## BFF anti-patterns

**Business logic in the BFF.** Calculating tariffs, enforcing session rules, validating payment — that belongs in domain services. The BFF calls services; it doesn't replace them.

**BFF as a shared library.** If `bff-mobile` and `bff-web` import from `@company/bff-common` and that library grows business logic, you've rebuilt a monolith with extra steps.

**BFF calling BFF.** Mobile BFF should not call Web BFF to get data. Both call domain services directly. BFF-to-BFF coupling creates hidden dependency chains.

**One giant BFF for everything.** A single `bff` repo with 200 endpoints serving mobile, web, admin, and internal tools is a monolith wearing a BFF label.

## Implementation choices

| Approach | Pros | Cons |
|---|---|---|
| Separate Node/Go service | Full control, team ownership | Another service to deploy and monitor |
| GraphQL server as BFF | Client-driven queries, strong typing | Resolver complexity, N+1 risk |
| Server-driven UI (SDUI) | Backend controls layout | Tight coupling, limited offline |
| Edge functions (Cloudflare Workers) | Low latency, no server | Limited compute, cold starts |

For the charging platform, a dedicated Node.js service was the right call — the team already ran Node for the OCPP middleware, WebSocket support was native, and the mobile team owned the BFF repo. New screens shipped behind [feature flags](https://blog.michaelsam94.com/feature-flags-trunk-based-development/) while the BFF endpoint evolved in the same PR as the Flutter UI.

## Testing the BFF

BFF logic is almost entirely orchestration, so test it with mocked service clients:

```typescript
test("home screen returns null session when none active", async () => {
  sessionClient.getActive.mockResolvedValue(null);
  geoClient.findNearby.mockResolvedValue([mockCharger]);
  billingClient.getBalance.mockResolvedValue({ available: 5000, currency: "EGP" });

  const res = await request(app).get("/api/v1/home").set("Authorization", token);

  expect(res.body.activeSession).toBeNull();
  expect(res.body.nearbyChargers).toHaveLength(1);
});
```

Contract tests between BFF and domain services catch drift. If the session service renames a field, the BFF's contract test fails before the mobile app does.

## Resources

- [Sam Newman — Backends For Frontends pattern](https://samnewman.io/patterns/architectural/bff/)
- [Martin Fowler — BFF overview](https://martinfowler.com/articles/bff.html)
- [Phil Calçado — The Backend for Frontend Pattern](https://philcalcado.com/2015/09/18/the_back_end_for_front_end_pattern_bff.html)
- [microservices.io — API Gateway pattern](https://microservices.io/patterns/apigateway.html)
- [Netflix — Optimizing the Netflix API with BFFs](https://netflixtechblog.com/optimizing-the-netflix-api-5c9c997fa963)
- [GraphQL as a BFF — Apollo documentation](https://www.apollographql.com/docs/graphos/schema-design/guides/frontend/backend-for-frontend)
