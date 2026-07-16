---
title: "Building Presence Systems"
slug: "realtime-presence-systems"
description: "How to build user presence for real-time apps: heartbeat protocols, last-seen semantics, cursor sharing, scaling with Redis, and privacy considerations."
datePublished: "2026-01-08"
dateModified: "2026-01-08"
tags: ["Real-Time", "Backend", "Web", "Architecture"]
keywords: "presence system, online status, heartbeat, WebSocket presence, cursor sharing, last seen, Redis pub sub"
faq:
  - q: "What is a presence system?"
    a: "A presence system tracks which users are currently active in a context — a document, chat room, or app — and broadcasts join, leave, and activity updates to other participants. It typically includes online/offline status, optional metadata (cursor position, selected cell, avatar), and heartbeat-based timeout detection for disconnects."
  - q: "How do you detect when a user goes offline?"
    a: "Clients send periodic heartbeats (every 15–30 seconds) over WebSocket or HTTP. The server records last-seen timestamps. If no heartbeat arrives within a timeout window (usually 2–3 missed intervals), the server marks the user offline and notifies peers. TCP alone is unreliable — proxies and mobile backgrounding kill connections without clean close frames."
  - q: "How do you scale presence to many rooms?"
    a: "Store presence state in a fast shared store (Redis hashes or TTL keys), use pub/sub for fan-out to WebSocket servers, and scope subscriptions to room channels only. Each WebSocket node subscribes to channels for rooms it has active connections in. Avoid broadcasting global presence across all users — partition by room or tenant."
---

The green dot next to a colleague's name seems trivial until you build it wrong. Users show as online for ten minutes after closing the laptop. Cursors jump across the screen from stale positions. A 500-person standup melts your WebSocket cluster because every join broadcasts to everyone. Presence is a small feature with sharp scaling and correctness edges.

I've implemented presence three times — chat, collaborative docs, and a multiplayer whiteboard — and the architecture converges on the same shape each time: heartbeats, a shared store with TTL, room-scoped pub/sub, and explicit leave on tab close where the browser cooperates.

## Presence state model

At minimum, track per user per room:

```typescript
interface PresenceEntry {
  userId: string;
  roomId: string;
  status: "online" | "away" | "offline";
  lastSeen: number;       // epoch ms
  metadata?: {
    cursor?: { x: number; y: number };
    color?: string;
    displayName?: string;
  };
}
```

**Online** means heartbeat received within the timeout window. **Away** is optional — triggered by `document.visibilitychange` or idle detection on the client. **Offline** is inferred by the server when heartbeats stop; never trust the client to declare offline on crash.

Store as `presence:{roomId}` hash in Redis with field `userId` → JSON blob, or use individual keys with TTL:

```
SET presence:room-42:user-7 "{...}" EX 90
```

TTL keys self-cleanse when heartbeats stop — no sweeper job required. The trade-off: you lose metadata immediately on expiry rather than transitioning through explicit offline events unless you combine TTL with pub/sub notifications.

## Heartbeat protocol

Client sends every 20 seconds; server timeout at 60 seconds (three missed beats):

```javascript
// Client
const HEARTBEAT_MS = 20_000;

function startPresence(roomId, ws) {
  const interval = setInterval(() => {
    if (ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "heartbeat", roomId }));
    }
  }, HEARTBEAT_MS);

  document.addEventListener("visibilitychange", () => {
    ws.send(JSON.stringify({
      type: "status",
      away: document.hidden,
    }));
  });

  window.addEventListener("beforeunload", () => {
    ws.send(JSON.stringify({ type: "leave", roomId }));
  });

  return () => clearInterval(interval);
}
```

`beforeunload` is best-effort — mobile Safari kills tabs silently. Server-side timeout is the source of truth for offline detection.

## Fan-out architecture

```
[Client A]──┐
[Client B]──┼── [WS Server 1] ── Redis PUBLISH presence:room-42
[Client C]──┘         │
                      ├── [WS Server 2] ── subscribers in room-42
                      └── [WS Server 3]
```

When a heartbeat arrives:

1. Update Redis state for `roomId + userId`.
2. If status changed (join or away transition), publish delta to `presence:room-42`.
3. Each WebSocket server forwards to local connections subscribed to that room.

Only publish on **changes**, not every heartbeat. Heartbeats update TTL silently; peers do not need 20-second spam.

Initial join sends full snapshot:

```json
{ "type": "presence_sync", "users": [ /* all online in room */ ] }
```

Subsequent updates are deltas:

```json
{ "type": "presence_update", "join": [...], "leave": [...], "patch": [...] }
```

## Cursor and ephemeral metadata

Cursors are high-frequency, loss-tolerant data. Throttle client-side to 10–15 updates per second and skip sends if position unchanged. Many teams use a separate channel from lifecycle presence so cursor noise does not inflate join/leave processing.

For collaborative editors, broadcast cursor position as percentage of viewport rather than absolute pixels — different screen sizes otherwise misalign overlays.

## Privacy and product boundaries

Presence exposes behavioral data. Product and legal teams should decide:

- Can users hide their online status?
- Is "viewing document X" visible to everyone in the org or only editors?
- How long is last-seen retained after offline?

Implement **presence visibility levels** early. Retrofitting privacy onto a system that broadcasts everything by default is painful.

## Failure modes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Ghost users | No server timeout | TTL + heartbeat timeout |
| Flapping online/offline | Timeout too tight | Increase to 2–3x heartbeat interval |
| WS cluster overload | Global broadcasts | Room-scoped pub/sub only |
| Split presence | Sticky sessions without shared store | Centralize state in Redis |

## Scaling presence across regions

Global apps need regional presence clusters:

```
User in EU → EU WebSocket edge → EU Redis presence store
Cross-region: only notify if users share a document (CRDT sync)
```

Don't replicate full presence globally — bandwidth and consistency costs exceed benefit. Document-scoped presence syncs only between users editing the same resource.

## Presence metadata design

Keep presence payloads small (< 1 KB):

```typescript
interface PresenceState {
  userId: string;
  status: 'active' | 'idle' | 'away';
  lastActive: number;  // epoch ms
  cursor?: { blockId: string; offset: number };
  // NOT: full user profile, avatar URL, bio
}
```

Fetch profile data separately on render — presence updates every few seconds; profile changes rarely. Mixing them causes unnecessary broadcast volume.

## Load testing presence

Simulate realistic patterns before launch:

- 500 users join same document room
- 50 concurrent cursor updates/sec
- Random disconnect/reconnect (mobile network simulation)
- Measure Redis memory, WebSocket CPU, message fan-out latency

Rule of thumb: 10K concurrent connections per 4-core WebSocket server with room-scoped pub/sub. Adjust for message size and update frequency.

Pair with [realtime protocols SSE vs WebSocket](https://blog.michaelsam94.com/realtime-protocols-sse-vs-websocket/) when choosing transport for presence vs event streams.

## Common production mistakes

Teams get presence systems wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of presence systems fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Resources

- [Phoenix Presence (Elixir reference implementation)](https://hexdocs.pm/phoenix/Phoenix.Presence.html)
- [Socket.IO rooms and broadcasting](https://socket.io/docs/v4/rooms/)
- [Redis Pub/Sub documentation](https://redis.io/docs/latest/develop/interact/pubsub/)
- [Page Visibility API](https://developer.mozilla.org/en-US/docs/Web/API/Page_Visibility_API)
- [Liveblocks presence API](https://liveblocks.io/docs/api-reference/liveblocks-client#Presence)
