---
title: "System Design: Chat System"
slug: "system-design-chat-messaging"
description: "Design a real-time chat system handling one-to-one and group messaging, presence, read receipts, and message history at scale. Architecture patterns for WhatsApp-scale messaging."
datePublished: "2025-10-09"
dateModified: "2026-07-17"
tags: ["System Design", "Architecture", "Messaging", "Backend"]
keywords: "chat system design, real-time messaging architecture, WebSocket scaling, message queue chat, group chat system design, presence system"
faq:
  - q: "Should a chat system use WebSockets or long polling?"
    a: "WebSockets for production chat — they provide full-duplex, low-latency communication ideal for real-time message delivery and typing indicators. Long polling works as a fallback for restrictive corporate networks but adds latency and server load. Use WebSockets with a fallback transport (SSE or long poll) for clients that can't maintain persistent connections."
  - q: "How do you store message history for billions of messages?"
    a: "Partition messages by conversation ID (chat_id) across a distributed database like Cassandra or ScyllaDB. Hot conversations get dedicated partitions; cold history moves to cheaper storage tiers. Index recent messages in Redis for fast retrieval; paginate older messages from the database with cursor-based queries. Never store all messages in a single SQL table without sharding."
  - q: "How does message delivery work when a user is offline?"
    a: "The message service persists the message, publishes a push notification event, and stores the message in the recipient's inbox queue. When the user reconnects, the client syncs missed messages from the inbox using a last-seen sequence number. Push notifications (APNs/FCM) alert the user on mobile; the full message loads on app open."
faqAnswers:
  - question: "When is system design chat messaging the wrong approach?"
    answer: "When a simpler control already covers the risk, or when the operational cost exceeds the benefit for your threat and traffic model."
  - question: "What should we measure for system design chat messaging?"
    answer: "Pair a leading operational signal with a lagging user or risk outcome, reviewed on a fixed cadence with a named owner."
  - question: "How do we roll back system design chat messaging safely?"
    answer: "Keep the prior artifact or config warm, rehearse the revert once in staging, and document the one-command rollback for on-call."
---
Designing a chat system sounds simple until you account for group messages fanning out to 500 members, a user with three devices that all need the same message, and the requirement that messages arrive in order even when sent from Tokyo and read in New York. WhatsApp handles over 100 billion messages daily. The architecture that supports that scale separates message ingestion from delivery, uses sequence numbers for ordering, and treats presence as a best-effort overlay — not a blocking dependency.

## High-level architecture

```
Client ←→ WebSocket Gateway ←→ Chat Service ←→ Message Store (Cassandra)
                ↓                    ↓
           Connection Map       Message Queue (Kafka)
                ↓                    ↓
           Presence Service     Push Notification Service
                                     ↓
                               APNs / FCM
```

Clients connect to WebSocket gateways via load balancers. Gateways maintain connection state in a distributed map (Redis). The chat service handles message validation, persistence, and fan-out. Kafka decouples write path from delivery path.

## Message flow: sending a message

1. Client sends message via WebSocket: `{ chat_id, content, client_msg_id }`.
2. Gateway routes to a chat service instance (partitioned by `chat_id`).
3. Chat service assigns a server-side sequence number (monotonic per chat).
4. Message persisted to Cassandra: `INSERT INTO messages (chat_id, seq, sender, content, timestamp)`.
5. Chat service publishes delivery events to Kafka topic partitioned by `chat_id`.
6. Delivery workers consume events and push to connected recipients via their gateway instances.
7. Sender receives ACK with server `seq` — client marks message as delivered.

```python
# Simplified message send handler
async def send_message(chat_id: str, sender_id: str, content: str, client_msg_id: str):
    seq = await redis.incr(f"chat:{chat_id}:seq")
    message = Message(
        chat_id=chat_id, seq=seq, sender_id=sender_id,
        content=content, timestamp=now(), client_msg_id=client_msg_id
    )
    await cassandra.execute(
        "INSERT INTO messages (chat_id, seq, ...) VALUES (?, ?, ...)",
        (chat_id, seq, ...)
    )
    await kafka.publish("message-events", key=chat_id, value=message)
    return {"seq": seq, "status": "sent"}
```

The `client_msg_id` enables idempotency — if the client retries a send, the server deduplicates by `(chat_id, client_msg_id)`.

## Group chat fan-out

For a group with N members, fan-out multiates delivery work. Strategies:

**Write fan-out:** Store one copy of the message, deliver to N recipients at read time. Efficient storage, expensive delivery for large groups.

**Read fan-out:** Write N copies (one per recipient inbox) at send time. Fast delivery, expensive storage.

**Hybrid:** Write fan-out for groups under 100 members. For larger channels (broadcast groups, announcement channels), store once and deliver to online members only; offline members sync on reconnect.

WhatsApp uses write fan-out with per-recipient delivery queues for groups up to a few hundred members.

## WebSocket gateway scaling

Each gateway instance holds thousands of WebSocket connections. Scaling challenges:

- **Connection routing:** Sticky sessions via load balancer, or a connection registry in Redis mapping `user_id → gateway_instance`.
- **Cross-gateway delivery:** When user A on gateway-1 sends to user B on gateway-3, the delivery event routes through Kafka to gateway-3, which pushes to B's WebSocket.
- **Heartbeat and reconnection:** Clients send pings every 30 seconds. Missed heartbeats trigger disconnect cleanup. Clients reconnect with exponential backoff and sync missed messages.

```javascript
// Client reconnection with sync
ws.onopen = () => {
  ws.send(JSON.stringify({
    type: "sync",
    last_seq: localStore.getLastSeq(chatId)
  }));
};
```

## Message ordering and consistency

Messages within a chat must appear in sequence order. Across chats, ordering doesn't matter. Per-chat sequence numbers (stored in Redis, incremented atomically) guarantee ordering without global coordination.

For "sent" → "delivered" → "read" status progression, use a state machine per message per recipient:

```
sent → delivered → read
```

Each transition is an event stored alongside the message. Clients update UI optimistically and reconcile with server state on sync.

## Presence system

Track online/offline/last-seen status separately from messaging — presence is best-effort:

- Gateway sets `user:online` in Redis with TTL on connect.
- TTL refreshes on heartbeat; expiry means offline.
- Last-seen updated on disconnect.
- Presence changes published to subscribed contacts via lightweight events.

Don't block message delivery on presence checks. Deliver to connected devices; queue for offline users regardless.

## Data model

```sql
-- Cassandra tables (partition key → clustering key)
CREATE TABLE messages (
    chat_id UUID,
    seq BIGINT,
    sender_id UUID,
    content TEXT,
    timestamp TIMESTAMP,
    client_msg_id TEXT,
    PRIMARY KEY (chat_id, seq)
) WITH CLUSTERING ORDER BY (seq DESC);

CREATE TABLE user_chats (
    user_id UUID,
    chat_id UUID,
    last_seq BIGINT,
    unread_count INT,
    PRIMARY KEY (user_id, chat_id)
);
```

Recent messages load from the `messages` table by `chat_id`. User's chat list loads from `user_chats` with unread counts maintained by counters.

## A concrete playbook for system design chat messaging

Interview and production designs for chat messaging share a spine: requirements → API → data model → scale bottlenecks → failure modes. The difference in production is operational ownership and cost.

### Capacity sketch

Write down expected QPS, payload size, read/write ratio, and growth. For chat messaging, identify the hottest path and ensure it can be cached, sharded, or async-offloaded. Avoid designing for theoretical peak without a load-test plan.

### Consistency choices

State whether the system is strongly consistent on the write path or eventually consistent for secondary views. Users forgive slightly stale counters; they do not forgive lost payments or double bookings. Match the store to the invariant.

### Multi-region notes

If chat messaging needs geo presence, decide active-active vs active-passive, how IDs are allocated without collision, and what “redirect to nearest region” means during partition. Document the RPO/RTO.

### Abuse and security

Public endpoints attract scraping and spam. Rate-limit creates, authenticate mutating APIs, and plan takedown for abusive content. Shortlink, upload, and messaging surfaces are especially attractive to attackers.

## Validation scenarios for system design chat messaging

Before calling system design chat messaging done, exercise these scenarios in a staging environment that mirrors production identity, data volume, and failure injection:

1. **Happy path** with production-like payload sizes.
2. **Auth failure** — expired token, missing scope, revoked session.
3. **Dependency down** — timeout the primary collaborator; confirm degraded mode or clear error.
4. **Replay / duplicate** — submit the same event or request twice; confirm idempotency.
5. **Rollback** — disable the flag or revert the deploy; confirm state converges.

Capture traces for each scenario and store them next to the runbook for system design chat messaging.

## Ownership and interfaces

Name the producing and consuming teams for system design chat messaging. Publish the API/event contract with versioning rules. If you need a breaking change, run dual-write or dual-read long enough for consumers to migrate. Silent breakages erode trust faster than slow features.

## Cost, risk, and sequencing for system design chat messaging

Sequence delivery so the riskiest assumption is tested first. If system design chat messaging depends on a new data model, migrate a shadow path before cutting reads. If it depends on a new vendor, run a canary with synthetic traffic and a kill switch.

Budget engineering weeks for observability and docs — not only feature code. A system you cannot explain to on-call is not production-ready. Keep the Resources section pointed at primary specs so future changes track upstream behavior rather than outdated secondary summaries about system design chat messaging.

| Gate | Evidence |
|------|----------|
| Functional | Automated tests green on the critical path |
| Operable | Dashboard + alert + runbook linked |
| Secure | Threat model notes + authz tests |
| Reversible | Flag or rollback rehearsed |

## Implementation detail #1 for system design chat messaging

Focus area 1: schema validation at trust boundaries.

For system design chat messaging, write an acceptance test that fails if this focus area regresses. Keep the test next to the production code, not in a separate unowned suite. Include a short comment linking to the incident or design note that motivated the check.

| Check | Expected |
|-------|----------|
| Focus 1 happy path | Pass |
| Focus 1 failure injection | Controlled error, no cascade |
| Focus 1 after rollback | Stable prior behavior |

## Resources

- [WhatsApp architecture (Meta engineering blog)](https://engineering.fb.com/)
- [Discord's real-time infrastructure](https://discord.com/blog/how-discord-stores-trillions-of-messages)
- [WebSocket scaling patterns](https://ably.com/topic/websocket-architecture)
- [Apache Cassandra data modeling for messaging](https://cassandra.apache.org/doc/latest/cassandra/developing/data-modeling/)
- [System Design Interview — Alex Xu, Chapter on Chat Systems](https://www.amazon.com/System-Design-Interview-insiders-Second/dp/B08CMF2CQF)
## Fan-out writes

Per-user inboxes make reads O(1) in busy threads.