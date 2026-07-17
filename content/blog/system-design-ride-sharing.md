---
title: "System Design: Ride Sharing"
slug: "system-design-ride-sharing"
description: "Design a ride-sharing platform matching riders with drivers in real time using geospatial indexing, ETA calculation, surge pricing, and trip lifecycle management."
datePublished: "2025-11-13"
dateModified: "2026-07-17"
tags: ["System Design", "Ride Sharing", "Architecture", "Backend"]
keywords: "ride sharing system design, Uber architecture, geospatial matching, driver rider matching, surge pricing, real-time location tracking"
faq:
  - q: "How does ride matching work in real time?"
    a: "When a rider requests a ride, the matching service queries a geospatial index (geohash or quadtree) for available drivers within a radius, calculates ETA for each candidate, and selects the nearest driver with acceptable ETA. The query must complete in under 2 seconds — riders abandon after 3-4 seconds of waiting. Start with a small radius (1 km) and expand if no drivers found."
  - q: "How do you track driver locations at scale?"
    a: "Drivers send GPS updates every 3-4 seconds via WebSocket or MQTT. A location ingestion service writes to a geospatial index (Redis GEO, Google S2) and a time-series store for trip replay. Only index available (on-trip vs idle) drivers for matching. Location data for active trips is streamed to riders via WebSocket. Historical locations are downsampled for storage."
  - q: "How does surge pricing work?"
    a: "Surge activates when demand (ride requests) exceeds supply (available drivers) in a geospatial cell. The surge multiplier (1.2x to 3.0x) is calculated per cell based on the demand/supply ratio. Higher prices incentivize more drivers to move to the area and reduce rider demand. Surge maps update every few minutes. The multiplier is locked when a rider requests — it doesn't change mid-request."
faqAnswers:
  - question: "When is system design ride sharing the wrong approach?"
    answer: "When a simpler control already covers the risk, or when the operational cost exceeds the benefit for your threat and traffic model."
  - question: "What should we measure for system design ride sharing?"
    answer: "Pair a leading operational signal with a lagging user or risk outcome, reviewed on a fixed cadence with a named owner."
  - question: "How do we roll back system design ride sharing safely?"
    answer: "Keep the prior artifact or config warm, rehearse the revert once in staging, and document the one-command rollback for on-call."
---
Matching a rider in downtown San Francisco with the nearest available driver — out of 2,000 drivers in the metro area, each sending GPS coordinates every four seconds — is a geospatial query problem with a two-second deadline. Get it wrong and the rider waits eight minutes for a driver three miles away while someone closer idle-blocks on a stale location index.

Ride-sharing system design centers on real-time location indexing, sub-second matching, trip state management, and dynamic pricing that balances supply and demand across geographic cells.

## Architecture overview

```
Rider App ←→ API Gateway ←→ Matching Service ←→ Geospatial Index (Redis GEO)
Driver App ←→ Location Service → Location Ingestion → Geospatial Index
                                ↓
                          Trip Service → Payment Service
                                ↓
                          Notification Service (push updates)
```

Drivers stream location updates. Riders request trips. The matching service queries the geospatial index, assigns a driver, and the trip service manages the lifecycle from pickup to dropoff to payment.

## Location ingestion and indexing

Drivers send location updates via persistent connection:

```json
{
  "driver_id": "drv_123",
  "lat": 37.7749,
  "lng": -122.4194,
  "heading": 270,
  "speed": 12.5,
  "status": "available",
  "timestamp": 1700000000
}
```

Location service validates, deduplicates (ignore if moved < 10 meters), and updates the geospatial index:

```python
async def update_driver_location(driver_id: str, lat: float, lng: float, status: str):
    await redis.geoadd("drivers:available", (lng, lat, driver_id))
    await redis.hset(f"driver:{driver_id}", mapping={
        "lat": lat, "lng": lng, "status": status,
        "updated_at": time.time()
    })

    if status != "available":
        await redis.zrem("drivers:available", driver_id)
```

Redis GEO supports `GEORADIUS` queries — find all drivers within N kilometers of a point:

```python
async def find_nearby_drivers(lat: float, lng: float, radius_km: float = 2.0):
    results = await redis.georadius(
        "drivers:available", lng, lat, radius_km, unit="km",
        withdist=True, sort="ASC", count=20
    )
    return [
        {"driver_id": r[0], "distance_km": r[1]}
        for r in results
        if await is_fresh(r[0])  # ignore stale locations (> 30s old)
    ]
```

For higher scale, partition the geospatial index by city or geohash prefix. San Francisco drivers index separately from Oakland drivers.

## Matching algorithm

```python
async def match_rider(rider_id: str, pickup_lat: float, pickup_lng: float):
    for radius in [1.0, 2.0, 5.0, 10.0]:  # expanding search
        candidates = await find_nearby_drivers(pickup_lat, pickup_lng, radius)
        if not candidates:
            continue

        scored = []
        for driver in candidates:
            eta = await eta_service.calculate(
                driver_lat=driver["lat"], driver_lng=driver["lng"],
                pickup_lat=pickup_lat, pickup_lng=pickup_lng
            )
            if eta < 600:  # under 10 minutes
                scored.append({**driver, "eta": eta})

        if scored:
            best = min(scored, key=lambda d: d["eta"])
            return await assign_driver(rider_id, best["driver_id"])

    return None  # no drivers available — notify rider
```

ETA calculation uses a routing engine (OSRM, Google Maps Directions API) with traffic data. Cache ETAs for common origin-destination pairs. Pre-compute ETA matrices for high-density areas during peak hours.

## Trip lifecycle

```
requested → matched → driver_en_route → arrived → in_progress → completed
    ↓          ↓            ↓
 cancelled  cancelled   cancelled (with fee)
```

```python
class TripState(Enum):
    REQUESTED = "requested"
    MATCHED = "matched"
    DRIVER_EN_ROUTE = "driver_en_route"
    ARRIVED = "arrived"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

async def assign_driver(rider_id: str, driver_id: str) -> Trip:
    trip = Trip(rider_id=rider_id, driver_id=driver_id, state=TripState.MATCHED)

    # Atomic assignment — prevent double-booking
    assigned = await redis.set(
        f"driver:lock:{driver_id}", trip.id, nx=True, ex=3600
    )
    if not assigned:
        raise DriverAlreadyAssigned()

    await trip_store.save(trip)
    await notification.push(driver_id, "New ride request", trip)
    await update_driver_location_status(driver_id, "busy")
    return trip
```

The driver lock prevents assigning the same driver to two riders simultaneously. Lock expires if the driver doesn't accept within 15 seconds.

## Surge pricing

Divide the map into geospatial cells (geohash precision 5 ≈ 4.9km × 4.9km):

```python
async def calculate_surge(cell: str) -> float:
    demand = await redis.get(f"demand:{cell}") or 0  # requests in last 5 min
    supply = await redis.zcard(f"drivers:cell:{cell}") or 1

    ratio = demand / supply
    if ratio < 1.5:
        return 1.0
    elif ratio < 2.0:
        return 1.25
    elif ratio < 3.0:
        return 1.5
    elif ratio < 5.0:
        return 2.0
    else:
        return min(3.0, 1.0 + ratio * 0.3)
```

Surge multiplier is locked at request time and stored on the trip record. Drivers in surging areas receive higher earnings, incentivizing repositioning.

## Real-time trip tracking

During an active trip, the rider app receives driver location updates via WebSocket:

```python
async def stream_trip_location(trip_id: str, websocket):
    async for location in location_stream.subscribe(f"trip:{trip_id}"):
        await websocket.send_json({
            "lat": location.lat,
            "lng": location.lng,
            "eta_to_pickup": location.eta,
            "eta_to_destination": location.destination_eta
        })
```

Location updates during trips are published to a trip-specific channel. Only the matched rider and driver receive updates — not broadcast to the geospatial index (driver is no longer "available").

## Payment and fare calculation

```python
async def calculate_fare(trip: Trip) -> Fare:
    distance_km = trip.actual_distance
    duration_min = trip.actual_duration
    base = 2.50
    per_km = 1.20
    per_min = 0.25
    surge = trip.surge_multiplier

    subtotal = (base + distance_km * per_km + duration_min * per_min) * surge
    return Fare(subtotal=subtotal, surge=surge, total=round(subtotal, 2))
```

Fare is calculated at trip completion based on actual distance and duration (GPS track), not estimated. Minimum fare applies. Cancellation fees depend on trip state when cancelled.

## Geospatial indexing at match time

Driver-rider matching queries drivers within a radius of pickup location. Geo-hash or H3 cells partition the space — query adjacent cells for candidates within radius instead of full table scan. Update driver location every 3–5 seconds during active sessions; stale locations cause missed matches. Surge pricing multipliers live in a separate fast-read store keyed by H3 cell — match latency and pricing lookup must not share the same hot database connection pool.

## Surge pricing feedback loops

Surge multipliers must update within seconds of demand/supply imbalance but display stable prices during the thirty-second confirmation window — users hate price changes mid-request. Geofence surge independently per airport, stadium, and downtown cell clusters. Cap maximum surge multiplier in product policy; uncapped surge during outages creates PR crises even when economically rational.

## Resources

- [Uber engineering blog — geospatial indexing](https://www.uber.com/blog/engineering/)
- [Redis GEO commands documentation](https://redis.io/docs/data-types/geospatial/)
- [Google S2 Geometry library](https://s2geometry.io/)
- [OSRM routing engine](http://project-osrm.org/)
- [Geohash spatial indexing](https://en.wikipedia.org/wiki/Geohash)

## system design ride sharing rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## system design ride sharing rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## system design ride sharing rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## system design ride sharing rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## system design ride sharing rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## system design ride sharing rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## system design ride sharing rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## Failure modes specific to system design ride sharing

System design interviews and production systems diverge: system design ride sharing in production needs SLOs, abuse controls, and multi-region failure stories. Sketch the data model and consistency requirements before drawing boxes.

For system design ride sharing:
- Separate read and write scaling paths early if fan-out or search is involved
- Idempotency keys on payments, bookings, and message delivery
- Backpressure at every queue; unbounded buffers are delayed outages
- Hot-key and thundering-herd mitigations (jitter, singleflight, cache stampedes)

Write the load-test plan that would disprove your capacity claims — QPS, payload sizes, and regional failover RTO.

| Signal | Target | Alarm |
|--------|--------|-------|
| Cold start p95 | Team-defined SLO | Page on burn rate |
| Throttle count | Baseline − noise | Ticket if sustained |
| Downstream timeouts | Budget cap | Weekly review |

## Ownership and on-call for system design ride sharing

Reviewers should challenge assumptions encoded in system design ride sharing: defaults copied from tutorials, timeouts that exceed upstream SLAs, and authz checks applied only on the primary UI path. Require a short threat or failure note in the PR when the change touches a trust boundary.

Concrete probes:
1. Scenario A for system design ride sharing: partial dependency outage — prove clients degrade gracefully and retries do not amplify load.
2. Scenario B for system design ride sharing: bad config shipped — prove rollback within the declared RTO without data corruption.
3. Scenario C for system design ride sharing: traffic 3× baseline — prove autoscaling or shedding keeps the golden journey healthy.

## Rollout sequence that worked for system design ride sharing

Roll out system design ride sharing behind a flag or weighted route when possible. Start with internal users or a low-risk geography. Watch the signals in the table for at least one full business cycle before calling the migration done. Keep the previous path warm until error budgets stabilize.

Document the owner, the dashboard, and the single command that reverts the change. If that sentence is hard to write, the design is not ready for production traffic.

## Compliance evidence for system design ride sharing

Detail 1 (297): for system design ride sharing, define the contract between producers and consumers explicitly — payload shape, timeout, and idempotency key. When compliance evidence for system design ride sharing becomes painful, it is usually because that contract was implicit.

I keep a short matrix: who can break system design ride sharing, how we detect it within five minutes, and who is paged. Update the matrix when ownership moves. Add one synthetic check that exercises the failure path, not only the happy path. Prefer checks that run continuously over quarterly manual reviews that everyone skips under deadline pressure.

If you only remember one thing about system design ride sharing: optimize for reversible decisions. Reversibility beats cleverness when the incident channel is busy and the blast radius is unclear.

## Developer experience when changing system design ride sharing

Detail 2 (414): for system design ride sharing, define the contract between producers and consumers explicitly — payload shape, timeout, and idempotency key. When developer experience when changing system design ride sharing becomes painful, it is usually because that contract was implicit.

I keep a short matrix: who can break system design ride sharing, how we detect it within five minutes, and who is paged. Update the matrix when ownership moves. Add one synthetic check that exercises the failure path, not only the happy path. Prefer checks that run continuously over quarterly manual reviews that everyone skips under deadline pressure.

If you only remember one thing about system design ride sharing: optimize for reversible decisions. Reversibility beats cleverness when the incident channel is busy and the blast radius is unclear.