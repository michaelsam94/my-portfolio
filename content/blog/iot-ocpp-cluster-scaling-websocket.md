---
title: "Scaling OCPP WebSocket Clusters"
slug: "iot-ocpp-cluster-scaling-websocket"
description: "Scale OCPP 1.6 WebSocket servers horizontally: sticky sessions, shared state, connection routing, heartbeat management, and handling 10K+ charger connections."
datePublished: "2025-08-27"
dateModified: "2025-08-27"
tags: ["IoT", "Embedded", "Backend", "Architecture"]
keywords: "OCPP WebSocket scaling, OCPP cluster, charging station WebSocket, horizontal scaling OCPP, sticky sessions WebSocket, OCPP 1.6 server"
faq:
  - q: "Why is scaling OCPP WebSocket servers challenging?"
    a: "OCPP 1.6 uses persistent WebSocket connections — one per charger. Each connection is stateful (active transactions, charger status, pending commands). Scaling horizontally requires routing the same charger to the same server instance (sticky sessions) or externalizing all state to a shared store (Redis/database)."
  - q: "How do I route OCPP WebSocket connections in a cluster?"
    a: "Use the charger ID (from the WebSocket URL path, e.g., /ocpp/CS001) as the routing key. Configure your load balancer (nginx, HAProxy, AWS ALB) for sticky sessions based on URL path or a cookie. Alternatively, use a connection registry in Redis where each server registers its connected chargers."
  - q: "What happens when an OCPP server instance fails?"
    a: "All chargers connected to that instance disconnect. They reconnect (OCPP mandates retry) and the load balancer routes them to a surviving instance. The new instance must recover state from the shared store — open transactions, last known status. Transactions in progress need reconciliation."
---

One OCPP server handling 500 chargers works fine. At 5,000 chargers across three regions, a single Python process chokes on memory and file descriptors. At 50,000, you need a cluster — and OCPP's stateful WebSocket connections make clustering harder than stateless HTTP. I've scaled an OCPP platform past 10,000 concurrent connections. The architecture that worked: sticky routing by charger ID, all state in Redis, and a reconciliation job for the inevitable reconnect storm after a deploy.

## Single-server limits

Before clustering, know your single-node ceiling:

| Resource | Limit | Symptom |
|----------|-------|---------|
| File descriptors | ~65K (ulimit) | "Too many open files" |
| Memory per connection | ~50-100 KB | OOM at 10K connections |
| CPU (JSON parsing) | ~1 core per 2K msg/s | Latency spikes |
| WebSocket ping/pong | ~1 timer per connection | Timer wheel pressure |

Profile your OCPP server at expected load before designing the cluster.

## Cluster architecture

```
                    ┌─── OCPP Server 1 (chargers A-M)
Chargers ──WS──► LB ─── OCPP Server 2 (chargers N-Z)
                    └─── OCPP Server 3 (overflow)
                           │
                           ▼
                     Redis (shared state)
                     PostgreSQL (transactions)
                     Kafka (events)
```

Load balancer routes by charger ID. All servers read/write state from Redis.

## Sticky routing with nginx

OCPP WebSocket URL: `wss://ocpp.example.com/ocpp/{chargerId}`

```nginx
upstream ocpp_backend {
    hash $uri consistent;  # route by URL path (charger ID)
    server ocpp1.internal:9000;
    server ocpp2.internal:9000;
    server ocpp3.internal:9000;
}

server {
    listen 443 ssl;
    server_name ocpp.example.com;

    location /ocpp/ {
        proxy_pass http://ocpp_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 3600s;  # OCPP heartbeat is 300s max
        proxy_send_timeout 3600s;
    }
}
```

`hash $uri consistent` ensures the same charger ID always routes to the same backend — even when servers are added or removed (consistent hashing minimizes redistribution).

## Externalized state in Redis

Every OCPP server reads/writes shared state:

```python
class ChargerStateStore:
    def __init__(self, redis: Redis):
        self.redis = redis

    def set_connection(self, charger_id: str, server_id: str):
        self.redis.hset(f"charger:{charger_id}", mapping={
            "server_id": server_id,
            "connected_at": time.time(),
            "status": "online",
        })
        self.redis.sadd(f"server:{server_id}:chargers", charger_id)

    def remove_connection(self, charger_id: str, server_id: str):
        self.redis.hset(f"charger:{charger_id}", "status", "offline")
        self.redis.srem(f"server:{server_id}:chargers", charger_id)

    def get_active_transaction(self, charger_id: str) -> dict | None:
        data = self.redis.hgetall(f"transaction:{charger_id}:active")
        return data if data else None

    def route_command(self, charger_id: str, command: dict) -> str:
        server_id = self.redis.hget(f"charger:{charger_id}", "server_id")
        if not server_id:
            raise ChargerOfflineError(charger_id)
        self.redis.lpush(f"server:{server_id}:commands", json.dumps({
            "charger_id": charger_id,
            "command": command,
        }))
        return server_id
```

When the API needs to send `RemoteStartTransaction` to a charger, it looks up which server holds the connection and pushes the command to that server's queue.

## Heartbeat management

OCPP requires chargers to send Heartbeat every N seconds (configured via ChangeConfiguration). The server must respond promptly:

```python
HEARTBEAT_INTERVAL = 300  # seconds (OCPP default)

async def handle_heartbeat(charger_id: str):
    await redis.hset(f"charger:{charger_id}", "last_heartbeat", time.time())
    return {"currentTime": datetime.utcnow().isoformat() + "Z"}

async def heartbeat_monitor():
    while True:
        chargers = await redis.keys("charger:*")
        for key in chargers:
            last_hb = float(await redis.hget(key, "last_heartbeat") or 0)
            if time.time() - last_hb > HEARTBEAT_INTERVAL * 3:
                charger_id = key.split(":")[1]
                await mark_offline(charger_id)
                await reconcile_active_transaction(charger_id)
        await asyncio.sleep(60)
```

If no heartbeat for 3x the interval, mark offline and reconcile any active transaction.

## Handling server failure

When an OCPP server dies:

1. All its WebSocket connections drop
2. Chargers reconnect automatically (OCPP retry interval)
3. Load balancer routes to surviving servers
4. New server reads state from Redis — knows about open transactions
5. Reconciliation job handles orphaned transactions

```python
async def on_charger_reconnect(charger_id: str, server_id: str):
    state = await store.get_charger_state(charger_id)
    active_tx = await store.get_active_transaction(charger_id)

    if active_tx and state.get("status") == "offline":
        # Charger reconnected with an open transaction — verify
        await send_ocpp_call(charger_id, "TriggerMessage", {
            "requestedMessage": "MeterValues"
        })
        log.info("reconnected_with_active_tx", charger_id=charger_id, tx=active_tx)
```

## Scaling checklist

- [ ] Consistent hash routing by charger ID
- [ ] All state in Redis/PostgreSQL, zero in-process state
- [ ] Command routing via server-specific queues
- [ ] Heartbeat monitoring with offline detection
- [ ] Transaction reconciliation on reconnect
- [ ] Connection count metrics per server
- [ ] Graceful shutdown (drain connections before deploy)
- [ ] Load test with simulated chargers (ocpp-js simulator)

Treat production rollout as a measured change: ship with observability, validate rollback, and review metrics 24 hours after deploy — patterns that look obvious in docs fail when skipped under release pressure.

## Common production mistakes

Teams get ocpp cluster scaling websocket wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

IoT deployments of ocpp cluster scaling websocket fail in the field when firmware assumes stable Wi-Fi, OTA rollback is untested, and device certificates expire without automated renewal.

## Debugging and triage workflow

When ocpp cluster scaling websocket misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [OCPP 1.6 Specification](https://www.openchargealliance.org/protocols/ocpp-16/) — WebSocket requirements and heartbeat configuration
- [nginx consistent hash load balancing](https://nginx.org/en/docs/http/load_balancing.html#hash) — routing configuration
- [ocpp-js (JavaScript OCPP library)](https://github.com/mobilityhouse/ocpp-js) — includes charger simulator for load testing
- [How I Architected an EV Charging Platform](/blog/how-i-architected-an-ev-charging-platform) — full platform architecture
