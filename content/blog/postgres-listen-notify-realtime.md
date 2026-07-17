---
title: "Real-Time Apps with LISTEN/NOTIFY"
slug: "postgres-listen-notify-realtime"
description: "Build real-time features with PostgreSQL LISTEN/NOTIFY: payload limits, connection handling, NOTIFY from triggers, and when to use logical decoding instead."
datePublished: "2026-03-23"
dateModified: "2026-07-17"
tags: ["PostgreSQL", "Backend", "Real-Time", "Database"]
keywords: "PostgreSQL LISTEN NOTIFY, Postgres real-time, NOTIFY trigger, logical decoding vs NOTIFY, pubsub Postgres"
faq:
  - q: "What are the payload size limits for NOTIFY?"
    a: "The payload string is limited to 8000 bytes in standard PostgreSQL builds. Send an ID or event type in NOTIFY and fetch full data separately. Never put large JSON documents in the payload."
  - q: "Is LISTEN/NOTIFY reliable message delivery?"
    a: "No — it's fire-and-forget. If no listener is connected when NOTIFY fires, the message is lost. No replay, no persistence. Use logical replication, message queues, or outbox pattern when delivery guarantees matter."
  - q: "When should I use logical decoding instead of NOTIFY?"
    a: "When you need durable event streams, multiple consumers, replay from a LSN, or CDC to external systems. NOTIFY suits low-latency same-database signaling — cache invalidation hints, WebSocket fan-out triggers — not event sourcing."
---

We needed dashboard widgets to refresh when batch jobs finished — no Kafka in this environment, just Postgres. `NOTIFY job_complete, '{"job_id": 42}'` from a trigger plus a Node listener forwarding to WebSockets worked for 200 concurrent users. It would not work for payment events requiring exactly-once delivery. LISTEN/NOTIFY is a signaling channel, not a message broker.

## Basic mechanics

```sql
-- Session A (listener)
LISTEN order_updates;

-- Session B (notifier)
NOTIFY order_updates, '{"order_id": "abc-123", "status": "shipped"}';
```

Listener receives asynchronous notification on open connection. Channel names are identifiers — lowercase recommended, max 63 bytes.

```javascript
// node-postgres listener (dedicated connection — not pooled)
const client = new Client({ connectionString: process.env.DATABASE_URL });
await client.connect();
await client.query('LISTEN order_updates');

client.on('notification', (msg) => {
  const payload = JSON.parse(msg.payload);
  websocketBroadcast('order:' + payload.order_id, payload);
});
```

**Use a dedicated connection for LISTEN** — PgBouncer transaction mode and pool return break long-lived listen sessions.

## NOTIFY from triggers

```sql
CREATE OR REPLACE FUNCTION notify_order_change()
RETURNS trigger AS $$
BEGIN
  PERFORM pg_notify(
    'order_updates',
    json_build_object(
      'order_id', NEW.id,
      'status', NEW.status,
      'op', TG_OP
    )::text
  );
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER order_change_notify
AFTER INSERT OR UPDATE ON orders
FOR EACH ROW EXECUTE FUNCTION notify_order_change();
```

Every write fires NOTIFY — high-write tables can flood listeners. Filter in trigger:

```sql
IF NEW.status IS DISTINCT FROM OLD.status THEN
  PERFORM pg_notify(...);
END IF;
```

## Payload discipline

8000 byte limit. Pattern:

```sql
PERFORM pg_notify('events', NEW.id::text);
-- Listener: SELECT * FROM events WHERE id = $1
```

Or send minimal envelope:

```json
{"t": "order.shipped", "id": "abc-123"}
```

## Scaling listeners

One NOTIFY reaches all listeners on channel — fan-out is O(listeners) inside Postgres. Hundreds of app servers each with LISTEN connection adds connection count pressure.

Architecture:

```
Postgres NOTIFY ──► 1–3 bridge pods (LISTEN) ──► Redis Pub/Sub or WebSocket hub ──► clients
```

Don't put LISTEN on every API pod — consolidate bridge services.

## Reliability boundaries

| Requirement | NOTIFY OK? |
|-------------|------------|
| Cache invalidation hint | Yes |
| Live UI refresh (best effort) | Yes |
| Payment processing | No |
| Audit log | No |
| Multi-service CDC | No |

For at-least-once: transactional outbox table + worker polling or logical replication.

```sql
-- Outbox pattern (durable)
INSERT INTO orders (...) VALUES (...);
INSERT INTO outbox (aggregate_id, event_type, payload) VALUES (...);
-- Same transaction — worker publishes to queue
```

## vs logical decoding

Logical decoding reads WAL stream — durable, replayable, consumer groups via tools (Debezium, pg_logical).

NOTIFY: microsecond latency, zero infra, no persistence.

Choose NOTIFY for "wake up and refetch" semantics. Choose logical decoding for event-driven architecture.

## Pitfalls

- Listener disconnects silently on network blip — reconnect with exponential backoff
- Missing notifications while disconnected — client must poll or accept gap
- NOTIFY inside failed transaction doesn't fire (fires on COMMIT) — good
- Security: any DB user with access can LISTEN sensitive channels — use separate role, minimal payload

## WebSocket bridge implementation sketch

Production setups rarely expose Postgres listeners directly to browsers. A small bridge service holds the dedicated LISTEN connection and forwards to your WebSocket tier:

```javascript
// bridge.js — one process per availability zone
const { Client } = require('pg');
const WebSocket = require('ws');

const pg = new Client({ connectionString: process.env.DATABASE_URL });
const wss = new WebSocket.Server({ port: 8081 });

await pg.connect();
await pg.query('LISTEN app_events');

pg.on('notification', (msg) => {
  const payload = JSON.parse(msg.payload);
  wss.clients.forEach((ws) => {
    if (ws.subscribedChannels?.has(msg.channel)) {
      ws.send(JSON.stringify({ channel: msg.channel, ...payload }));
    }
  });
});
```

Clients subscribe to channels after auth — never broadcast sensitive NOTIFY payloads to unauthenticated sockets. Reconnect the Postgres client on `error` and `end` events with jittered backoff; during outage, clients should fall back to polling every 30–60 seconds.

## Security hardening

Grant `LISTEN` only to bridge role; application roles should not listen on sensitive channels. Validate NOTIFY payload size before broadcast — oversized payloads fail silently or truncate.

## Operational notes

Load test NOTIFY rate before production — high-frequency triggers on wide tables can saturate listener CPU. Batch notifications or debounce per aggregate ID when events burst.

Monitor bridge service health separately from API health — NOTIFY pipeline can fail while HTTP returns 200, leaving users on stale WebSocket data without obvious errors.

## Production checklist

- [ ] Bridge reconnects to Postgres with jittered backoff
- [ ] Client fallback polling when WebSocket disconnects > 30s
- [ ] NOTIFY payload size validated before broadcast
- [ ] LISTEN granted only to bridge role, not app roles
- [ ] Load test NOTIFY rate against peak write throughput


## Payload size limit

NOTIFY payload max 8000 bytes — send id only, clients fetch full row via API. Pattern: NOTIFY orders_channel with NEW.id then SELECT by id.

## Connection lifecycle with poolers

LISTEN requires dedicated connection — do not share with PgBouncer transaction pool. Sidecar listener process or LISTEN on direct Postgres connection.

## Missed notifications

Listeners disconnect during network blip — reconcile with periodic poll or outbox table. NOTIFY is best-effort; critical workflows need outbox plus consumer.

## Channel namespacing

tenant_{id}_events prevents cross-tenant leakage if client subscribes wrong channel. Validate tenant in payload even when channel scoped.

## Debouncing rapid NOTIFY bursts

Bulk import firing NOTIFY per row overwhelms listeners — batch commits and send one NOTIFY with batch id; clients fetch `WHERE updated_at > $cursor`. Pattern mirrors CDC debouncing.

## LISTEN connection health check

Application heartbeat: if no NOTIFY in 5 minutes on active system, reconnect LISTEN socket — silent disconnect otherwise discovered only when stale UI reported.

## Scaling listeners horizontally

Each listener connection consumes one Postgres backend — 50 websocket servers means 50 LISTEN connections. Consolidate through Redis pub/sub bridge: one LISTEN process NOTIFY→Redis PUBLISH; app servers subscribe Redis — decouples fan-out from Postgres connection count.

## Security: who may LISTEN

Grant LISTEN on specific channel via RLS on pg_notify wrapper function SECURITY DEFINER — raw NOTIFY from untrusted role could spam channels. Application-only NOTIFY through stored procedure validates tenant before pg_notify call.

## NOTIFY payload encoding

JSON payload string must fit 8000 bytes — compress ids array or send version number only. Binary data forbidden — base64 inflates size; send blob id reference instead.

## Fallback polling interval

When NOTIFY missed, client polls every 30s as backstop — websocket push primary. Exponential backoff on poll when no changes reduces load; reset interval on received NOTIFY. Document hybrid push-poll in frontend architecture note for realtime dashboard team.

## Closing notes

Load test NOTIFY rate before peak event — listener single-threaded processing may bottleneck below Postgres NOTIFY capacity; queue depth metric alerts when processing lag exceeds one second.

## Additional guidance

Combine NOTIFY with transactional outbox for critical notifications — NOTIFY after COMMIT in same transaction as outbox insert using trigger; listener processes outbox row id from NOTIFY payload ensuring at-least-once delivery if listener crashes mid-processing without losing event entirely.

PgBouncer does not forward NOTIFY to clients connected through transaction pool — architectural constraint driving Redis bridge pattern or direct Postgres connection for listener workers documented in platform realtime architecture decision record approved by infra team.

Use transactional outbox plus NOTIFY for must-deliver events — NOTIFY alone drops messages if listener disconnected during network partition.

Bridge NOTIFY through Redis when more than ten app servers subscribe — Postgres listener connection count scales poorly compared to pub/sub fan-out pattern.

Listener process should ACK processing by deleting outbox row only after downstream websocket fan-out succeeds — at-least-once delivery without duplicate user notifications requires idempotent client message ids.

## Resources

- [PostgreSQL NOTIFY documentation](https://www.postgresql.org/docs/current/sql-notify.html)
- [PostgreSQL LISTEN documentation](https://www.postgresql.org/docs/current/sql-listen.html)
- [node-postgres notification example](https://node-postgres.com/features/notifications)
- [PostgreSQL logical decoding](https://www.postgresql.org/docs/current/logicaldecoding.html)
- [Transactional outbox pattern (microservices.io)](https://microservices.io/patterns/data/transactional-outbox.html)
