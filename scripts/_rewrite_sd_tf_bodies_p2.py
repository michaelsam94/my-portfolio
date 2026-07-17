# Part 2: video streaming, notification, payment, ride sharing

POSTS["system-design-video-streaming"] = {
    "meta": {
        "title": "System Design: Video Streaming",
        "description": "Designing video streaming like Netflix or YouTube: upload pipeline, transcoding, adaptive bitrate, CDN delivery, DRM, and live vs VOD architecture.",
        "datePublished": "2025-11-29",
        "tags": ["System Design", "Media", "CDN", "Architecture"],
        "keywords": "video streaming system design, HLS DASH, adaptive bitrate, transcoding pipeline, CDN video delivery, Netflix architecture",
        "faq": [
            {
                "q": "What is adaptive bitrate streaming?",
                "a": "Adaptive bitrate (ABR) delivers video in multiple quality levels (1080p, 720p, 480p, etc.) split into small segments. The player monitors bandwidth and buffer, switching quality up or down per segment. Protocols like HLS and DASH define manifest files listing segments; the client chooses which bitrate to fetch for each chunk.",
            },
            {
                "q": "Why transcode video into multiple formats?",
                "a": "Source uploads are one resolution and codec; clients vary in screen size, bandwidth, and supported codecs. Transcoding produces encoded ladders (multiple bitrates/resolutions) and often multiple container formats (HLS for Apple, DASH for others). Without transcoding, mobile users on 3G cannot play 4K source files smoothly.",
            },
            {
                "q": "How do CDNs fit into video streaming architecture?",
                "a": "Video segments are cacheable static objects ideal for CDN edge delivery. Origin stores segments in object storage (S3); CDN caches popular content near users. For live streams, short segment TTL and origin shielding reduce load. CDN reduces latency, origin bandwidth cost, and improves playback start time.",
            },
        ],
    },
    "body": r'''
Pressing play on a training video feels instantaneous. Behind that click lies a pipeline that may have spent forty minutes transcoding the upload into twelve bitrate variants, replicated petabytes to CDN edges, and armed a client player to make bandwidth decisions every four seconds for the next hour. Video streaming system design is half media engineering, half distributed caching.

## VOD and live are siblings, not twins

**Video on demand (VOD):** upload → validate → transcode → package → store → serve. Latency tolerance measured in minutes. Encoding efficiency matters — storage and egress dominate cost.

**Live streaming:** ingest RTMP/SRT/WebRTC → real-time transcode → segment → CDN fan-out → players. Latency tolerance measured in seconds (3–30s typical; LL-HLS targets sub-3s). Redundancy and failover dominate — a dropped ingest kills the broadcast.

This deep-dive centers on VOD, which also underpins live catch-up and DVR replay.

## Upload path: keep bytes off API servers

```
Client → request presigned multipart URL
       → PUT directly to object storage (S3/GCS)
       → callback POST /videos { object_key, metadata }
       → enqueue transcode job
```

Direct-to-storage upload prevents API nodes from becoming bandwidth bottlenecks. Multipart upload resumes after network drops. On completion: virus scan, container probe (ffprobe), duration/dimension validation, reject corrupted uploads before they enter the expensive transcode farm.

## Transcoding: the cost center

Source files arrive as ProRes, H.264 4K, or phone HEVC. Players need a **bitrate ladder** — multiple encodes at different resolutions:

| Rendition | Resolution | Video bitrate | Typical use |
| --- | --- | --- | --- |
| 1080p | 1920×1080 | 5 Mbps | Desktop Wi-Fi |
| 720p | 1280×720 | 2.5 Mbps | Tablet |
| 480p | 854×480 | 1 Mbps | Mobile LTE |
| 360p | 640×360 | 600 Kbps | Constrained 3G |

Job queue (SQS, Celery, Kubernetes jobs) feeds GPU workers running FFmpeg or AWS MediaConvert. Status transitions: `uploaded → transcoding → ready → failed`. Webhook or poll updates metadata; never block the user on synchronous transcode.

**Packaging** produces HLS (`.m3u8` + `.ts` or fMP4 segments) and optionally MPEG-DASH:

```
#EXTM3U
#EXT-X-STREAM-INF:BANDWIDTH=5000000,RESOLUTION=1920x1080
1080p/playlist.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=2500000,RESOLUTION=1280x720
720p/playlist.m3u8
```

The master playlist is tiny; variant playlists list 2–6 second segments. Players download master first, pick initial rendition, adapt per segment.

Per-title encoding (Netflix approach) analyzes complexity and customizes ladders. Per-shot optimization is overkill for most products; start with fixed ladders per resolution tier.

## Playback path and signed URLs

```
Player → GET signed manifest URL from API
       → CDN edge (cache manifest + segments)
       → ABR algorithm selects next segment bitrate
       → decode, buffer, render
```

API returns time-limited signed URLs — CloudFront signed cookies, Akamai token auth, or custom HMAC query params. Prevents hotlinking and enforces entitlement.

```json
{
  "playback_url": "https://cdn.example.com/v/abc/master.m3u8?token=...",
  "expires_at": "2026-07-17T18:00:00Z",
  "drm": null
}
```

**CDN cache strategy:** segments are immutable (filename includes sequence number) — cache TTL of days or years. Manifests change during live — TTL of one segment duration. Origin shielding concentrates cache misses through one regional hub, protecting origin from thundering herds on viral content.

## Adaptive bitrate algorithm (client-side)

Players estimate throughput from recent segment download times and monitor buffer depth. Standard heuristics (BOLA, throughput-based, buffer-based) trade startup speed vs rebuffer risk. Rebuffering is the UX failure mode — users tolerate lower resolution; they abandon on spinners.

Server-side ABR (per-user manifest manipulation) exists but adds complexity. Client-side remains default for VOD.

## DRM and entitlement

Premium content requires Widevine (Chrome/Android), FairPlay (Safari/iOS), PlayReady (legacy). DRM wraps segment keys; license servers validate subscription. Architecture adds: packaging with encryption, license server integration, device security level checks.

For corporate training or internal video, signed URLs without DRM often suffice.

## Metadata, search, and recommendations

Separate video binary path from metadata service (title, description, thumbnails, chapters). Generate thumbnails via FFmpeg scene detection or fixed intervals. Store posters in CDN; API serves JSON.

View progress (resume watching) is per-user state in a fast KV store — updated every 30 seconds, not per segment.

## Live-specific additions

Dual ingest paths (primary + backup encoder), slate images on failover, DVR window storing last N hours of segments, chat and moderation as orthogonal services. LL-HLS uses partial segments for lower latency at cost of more HTTP requests.

## Cost and capacity planning

Egress dominates at scale. A 1-hour 1080p stream at 5 Mbps ≈ 2.25 GB per complete viewing. One million views ≈ 2.25 PB egress — negotiate CDN commit pricing. Transcode cost scales with upload minutes × ladder width; spot GPU instances cut bills.

Storage in S3 Intelligent-Tiering for cold catalog; delete failed transcode artifacts promptly.

## Failure modes

Transcode worker crash → retry with exponential backoff; cap retries. CDN origin timeout → player retries next segment; multi-CDN failover for tier-1 SLAs. Corrupt segment → encoder validation rejects; never publish incomplete ladder (player stuck forever buffering).

## Synthesis

Explain upload ingestion, transcode ladder, HLS packaging, CDN caching, signed URLs, ABR, and where DRM fits. Senior signal: **video is immutable segments cached at the edge; everything else is metadata and entitlement.**
''',
}

POSTS["system-design-notification-system"] = {
    "meta": {
        "title": "System Design: Notification System",
        "description": "Design a multi-channel notification system delivering push, email, SMS, and in-app alerts to millions of users with templates, preferences, and delivery guarantees.",
        "datePublished": "2025-11-01",
        "tags": ["System Design", "Notifications", "Architecture", "Backend"],
        "keywords": "notification system design, push notification architecture, multi-channel notifications, email SMS delivery, notification preferences, idempotent delivery",
        "faq": [
            {
                "q": "How do you prevent duplicate notifications?",
                "a": "Assign each notification a unique idempotency key (event_id + user_id + channel). Before sending, check a deduplication store (Redis with TTL). If the key exists, skip delivery. This handles at-least-once message queue delivery that would otherwise send the same alert twice. TTL should match the deduplication window — typically 24 hours for transactional, 1 hour for high-frequency events.",
            },
            {
                "q": "How do notification preferences work at scale?",
                "a": "Store per-user, per-notification-type preferences in a fast lookup store (Redis or a dedicated service). Each notification event includes a type (order_shipped, friend_request, marketing_promo). Before delivery, the preference service checks: is this channel enabled for this type? Is the user in quiet hours? Has the user opted out of marketing? Fail open for critical transactional notifications (password reset); fail closed for marketing.",
            },
            {
                "q": "Push vs email vs SMS — when to use each channel?",
                "a": "Push for time-sensitive, action-required alerts (message received, ride arrived) — highest open rates but requires app install. Email for detailed content, receipts, and non-urgent updates — works without app, supports rich formatting. SMS for critical alerts when push may not reach (two-factor codes, delivery confirmations) — most expensive, use sparingly. Let users configure channel preferences per notification type.",
            },
        ],
    },
    "body": r'''
"We just need to send an email when the order ships" became a platform problem the week we added push notifications, SMS fallbacks for drivers, French Canadian templates, marketing opt-outs governed by CASL, and a bug where Kafka redelivery sent four identical push alerts at 2 AM. The notification system is the product's nervous system — every feature team publishes events; one team owns delivery, compliance, and user trust.

## Platform boundaries

Product services emit **notification intents**, not rendered emails. They should never import SendGrid SDKs or hold APNs certificates.

```
Event Sources → Ingestion API / Kafka → Notification Orchestrator
                                              |
                    +-------------------------+-------------------------+
                    |                         |                         |
              [Dedup store]            [Preference service]      [Template engine]
                    |                         |                         |
                    +-------------------------+-------------------------+
                                              |
                                        [Channel routers]
                    +------------+------------+------------+------------+
                    |            |            |            |            |
                  Push        Email         SMS        In-app      Webhook
                 APNs/FCM    SendGrid      Twilio      WebSocket    partner
```

Orchestrator responsibilities: validate schema, deduplicate, resolve user locale and channels, render templates, enqueue per-channel delivery jobs, record audit trail.

## Event contract

Structured events, not free-form strings:

```json
{
  "event_id": "evt_abc123",
  "type": "order_shipped",
  "user_id": "user_456",
  "data": {
    "order_id": "ord_789",
    "tracking_number": "1Z999AA10123456784",
    "estimated_delivery": "2026-07-20"
  },
  "priority": "high",
  "channels": ["push", "email"],
  "idempotency_key": "evt_abc123:user_456"
}
```

```python
async def process_event(event: NotificationEvent) -> None:
    dedup_key = f"{event.idempotency_key}:{event.type}"
    if not await redis.set(dedup_key, "1", nx=True, ex=86400):
        return

    prefs = await preference_service.get(event.user_id)
    allowed = prefs.filter_channels(event.type, event.channels)

    if not allowed and event.priority != "critical":
        return

    locale = prefs.locale or "en-US"
    rendered = await template_engine.render(event.type, event.data, locale)

    for channel in allowed:
        await delivery_queue.publish(DeliveryJob(event, channel, rendered))
```

## Preferences and quiet hours

Store preferences as `(user_id, notification_type) → {push: bool, email: bool, sms: bool, quiet_hours: ...}`.

**Fail-open** for password reset, security alert, payment failed — legal and safety requirements override marketing opt-out.

**Fail-closed** for promotional content — sending unwanted marketing email is a compliance violation (CAN-SPAM, GDPR legitimate interest tests, CASL).

Quiet hours: suppress push/SMS during user-local 22:00–08:00 unless `priority=critical`. Queue for morning delivery or downgrade to email.

Cache preferences in Redis with TTL; invalidate on settings update via pub/sub.

## Template engine

Separate content from code. Templates per `(type, channel, locale)`:

```handlebars
{{!-- order_shipped.push.hbs --}}
Your order {{order_id}} shipped! Track: {{tracking_url}}
```

Version templates (`v3/order_shipped/email/en-US.hbs`). Roll out template changes without deploying app servers. A/B test subject lines by routing percentage to template variants.

HTML email requires inline CSS, plaintext fallback, and preview text. Push requires title/body length limits per platform (APNs 4KB payload).

## Channel-specific delivery

**Push (APNs/FCM):** device token registry per user per device; handle token rotation and uninstall detection (410 Gone from APNs). Collapse multiple updates into one notification ID for chat apps.

**Email:** SPF/DKIM/DMARC configured; bounce and complaint webhooks suppress bad addresses. Separate transactional IP pool from marketing.

**SMS:** segment counting (160 chars); alphanumeric sender ID restrictions vary by country; cost 100× email — reserve for OTP and critical alerts.

**In-app:** WebSocket or poll; store unread count in Redis; mark read on fetch.

Each channel worker scales independently with its own rate limits (provider quotas).

## Retries, DLQ, and observability

At-least-once queue delivery means retries are mandatory. Exponential backoff per channel; after N failures, dead-letter queue for manual inspection.

Track metrics: `notifications_enqueued`, `delivered`, `failed`, `latency_by_channel`, `opt_out_blocks`. Distributed trace linking `event_id` → render → provider message ID.

User-facing delivery log: "We emailed you at 3:42 PM" — reduces support tickets.

## Rate limiting and batching

Digest emails: aggregate `friend_posted` events every evening instead of fifty individual pushes. Marketing campaigns: shard sends across hours to respect provider throughput.

Per-user caps: max 3 marketing pushes per day.

## Multi-tenant and white-label

B2B products need per-tenant branding, sender domains, and template overrides. Namespace templates by `tenant_id`; enforce tenant isolation in preference stores.

## Security

Never put PII in push payload visible on lock screens for sensitive types. Use "You have a new secure message" with in-app reveal.

Webhook callbacks from SendGrid/Twilio must verify signatures.

## Synthesis

Cover event schema, deduplication, preference fail-open/closed rules, template versioning, per-channel workers, and compliance. The line that lands: **notifications are an async workflow engine with legal side effects** — not a for-loop around `sendMail()`.
''',
}

POSTS["system-design-payment-system"] = {
    "meta": {
        "title": "System Design: Payment System",
        "description": "Design a payment processing system with authorization, capture, refunds, idempotency, and PCI compliance for handling financial transactions at scale.",
        "datePublished": "2025-11-05",
        "tags": ["System Design", "Payments", "Architecture", "Fintech"],
        "keywords": "payment system design, payment processing architecture, idempotency payments, PCI compliance, authorization capture, ledger system design",
        "faq": [
            {
                "q": "What is the difference between authorization and capture in payments?",
                "a": "Authorization reserves funds on the customer's payment method without transferring them — like holding a hotel deposit. Capture actually moves the money to the merchant. For physical goods, authorize at checkout and capture at shipment. For digital goods, authorize and capture in one step. Authorization holds typically expire after 7 days (varies by card network). Uncaptured authorizations must be voided or they hold customer funds unnecessarily.",
            },
            {
                "q": "How do payment systems ensure exactly-once charging?",
                "a": "Idempotency keys on every payment request. The client generates a unique key per payment attempt (UUID or order ID). The payment service stores the key with the result. Retries with the same key return the stored result without re-processing. This handles network timeouts where the client doesn't know if the payment succeeded. Keys expire after 24 hours; new attempts need new keys.",
            },
            {
                "q": "Should I store credit card numbers in my database?",
                "a": "Never store raw card numbers, CVV, or magnetic stripe data — this requires full PCI DSS Level 1 compliance (expensive audits, strict infrastructure). Use a payment processor (Stripe, Adyen) with tokenization: the processor stores the card, you store a token (pm_abc123) that references it. Your servers never touch raw card data. For custom flows, use hosted payment fields or SAQ A-EP compliant iframe solutions.",
            },
        ],
    },
    "body": r'''
A double charge is not a bug report — it is a chargeback, a Twitter thread, and a finance team reconciliation emergency. Payment systems operate at zero tolerance for ambiguity: every dollar must be accounted for, every API call must be idempotent, and raw card data must never touch application logs. You are building a distributed state machine wrapped around processors you do not control.

## Layered architecture

```
Client → Payment API (auth, validation)
              ↓
         Payment Service (state machine)
              ↓
         Processor adapter (Stripe/Adyen/Braintree)
              ↓
         Card networks / ACH rails
              ↓
         Ledger service (append-only financial record)
              ↓
         Reconciliation jobs (processor settlements vs ledger)
```

Your payment service owns business state. The processor owns network authorization. The ledger owns auditability. Never conflate the three.

## Payment state machine

```
created → authorized → captured → settled
              ↓            ↓
           voided      refunded (partial/full)
              ↓
           failed
```

Illegal transitions must hard-fail — never capture a voided payment.

```python
async def authorize(
    payment_id: str,
    amount_cents: int,
    payment_method_token: str,
    idempotency_key: str,
) -> Payment:
    cached = await idempotency_store.get(idempotency_key)
    if cached:
        return cached

    payment = await store.get(payment_id)
    if payment.state != State.CREATED:
        raise InvalidTransition(payment.state, "authorize")

    result = await processor.authorize(
        amount=amount_cents,
        token=payment_method_token,
        idempotency_key=idempotency_key,
    )

    payment = payment.transition(
        to=State.AUTHORIZED if result.ok else State.FAILED,
        processor_ref=result.ref,
        failure_reason=result.error,
    )
    await store.save(payment)
    await ledger.record_authorization(payment)
    await idempotency_store.put(idempotency_key, payment, ttl=86400)
    return payment
```

## Authorization vs capture timing

**Digital goods:** authorize + capture in one step — customer expects immediate charge.

**Physical goods:** authorize at order placement (hold inventory value), capture at shipment. Authorization holds expire (~7 days Visa/Mastercard); extend or re-auth if fulfillment delays.

**Marketplaces:** split payments — platform fee + seller payout via separate transfer APIs (Stripe Connect). Ledger tracks payable balances per seller.

## Idempotency everywhere

Network timeouts create the classic dilemma: client timed out, server charged. Idempotency keys solve this at payment creation, capture, refund, and webhook handling.

Store `(idempotency_key → response, status_code)` for 24 hours minimum. Stripe pioneered the header pattern; replicate it internally for your own APIs.

Webhooks also deduplicate by `event_id` — processors retry delivery for days.

## Ledger design

Append-only `ledger_entries` table — never UPDATE balances in place:

```
| id | payment_id | type      | amount_cents | currency | created_at |
|----|------------|-----------|--------------|----------|------------|
| 1  | pay_1      | auth_hold | 5000         | USD      | ...        |
| 2  | pay_1      | capture   | 5000         | USD      | ...        |
| 3  | pay_1      | refund    | -2000        | USD      | ...        |
```

Derived balance = sum(entries). Disputes and chargebacks add reversal entries months later.

Double-entry bookkeeping for finance integration: debit customer liability, credit merchant receivable, etc.

## PCI scope reduction

Never log PAN/CVV. Use hosted fields or tokenization:

```
Browser → Stripe.js → token pm_xxx → your API
Your API → Stripe charges pm_xxx
```

Your servers never see raw card numbers — SAQ A or A-EP instead of full Level 1 audit. Vault tokens at processor; store only `payment_method_id` and last-four brand.

## Refunds, disputes, and partial captures

Refunds reference original capture; partial refunds supported. Idempotency on refund requests prevents double-refund on retry.

Disputes (chargebacks) arrive via webhook weeks later — auto-debit merchant balance, notify seller, collect evidence.

## Multi-currency and FX

Presentment currency vs settlement currency. FX rates locked at capture time; ledger records rate source. Rounding rules per currency minor units (JPY has no cents).

## Reconciliation

Nightly job: download processor settlement report, match to ledger captures by `processor_ref`. Mismatches alert finance — common causes: timing (captured today, settled tomorrow), failed webhooks, manual processor adjustments.

## Fraud and risk

Integrate processor radar or third-party (Sift, Forter). Velocity checks, AVS/CVV results, 3D Secure for EU SCA compliance. Risk engine can block before authorize — cheaper than chargeback.

## Observability and support tooling

Admin UI: search by order_id, payment_id, last4, amount. Show state timeline with processor raw responses (redacted). Replay webhooks safely with idempotency.

Metrics: authorization rate, capture rate, decline codes breakdown, reconciliation drift.

## Synthesis

Walk state machine, idempotency, auth/capture split, ledger append-only design, PCI tokenization, reconciliation. Money is **immutable facts appended over time** — not a row you update when status changes.
''',
}

POSTS["system-design-ride-sharing"] = {
    "meta": {
        "title": "System Design: Ride Sharing",
        "description": "Design a ride-sharing platform matching riders with drivers in real time using geospatial indexing, ETA calculation, surge pricing, and trip lifecycle management.",
        "datePublished": "2025-11-13",
        "tags": ["System Design", "Ride Sharing", "Architecture", "Backend"],
        "keywords": "ride sharing system design, Uber architecture, geospatial matching, driver rider matching, surge pricing, real-time location tracking",
        "faq": [
            {
                "q": "How does ride matching work in real time?",
                "a": "When a rider requests a ride, the matching service queries a geospatial index (geohash or quadtree) for available drivers within a radius, calculates ETA for each candidate, and selects the nearest driver with acceptable ETA. The query must complete in under 2 seconds — riders abandon after 3-4 seconds of waiting. Start with a small radius (1 km) and expand if no drivers found.",
            },
            {
                "q": "How do you track driver locations at scale?",
                "a": "Drivers send GPS updates every 3-4 seconds via WebSocket or MQTT. A location ingestion service writes to a geospatial index (Redis GEO, Google S2) and a time-series store for trip replay. Only index available (on-trip vs idle) drivers for matching. Location data for active trips is streamed to riders via WebSocket. Historical locations are downsampled for storage.",
            },
            {
                "q": "How does surge pricing work?",
                "a": "Surge activates when demand (ride requests) exceeds supply (available drivers) in a geospatial cell. The surge multiplier (1.2x to 3.0x) is calculated per cell based on the demand/supply ratio. Higher prices incentivize more drivers to move to the area and reduce rider demand. Surge maps update every few minutes. The multiplier is locked when a rider requests — it doesn't change mid-request.",
            },
        ],
    },
    "body": r'''
A rider in downtown San Francisco requests a trip. Two thousand drivers operate in the metro area, each broadcasting GPS every four seconds. The matching service has roughly two seconds before abandonment spikes — yet the nearest driver by straight-line distance may be on the wrong side of a one-way grid, while someone three minutes away is actually faster. Ride-sharing is a geospatial indexing problem glued to a real-time logistics state machine and a live market pricing engine.

## Service topology

```
Rider app ──► API gateway ──► Trip service
Driver app ──► Location ingest ──► Geospatial index (Redis GEO / S2)
                    │                      │
                    └──────► Matching service ◄────┘
                                    │
                              Dispatch / offer
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
              Notification      Payment         Pricing/surge
```

Trip service owns lifecycle: requested → matched → driver_en_route → in_progress → completed → paid. Location service owns freshness of driver positions. Matching is read-heavy on the index; trip writes are transactional.

## Location ingestion at scale

Drivers stream via WebSocket or MQTT (lower overhead than HTTP polling):

```json
{
  "driver_id": "drv_123",
  "lat": 37.7749,
  "lng": -122.4194,
  "heading": 270,
  "speed_mps": 12.5,
  "status": "available",
  "ts": 1721200000
}
```

Ingestion pipeline:

1. Validate and dedupe (ignore if moved < 10m since last write)
2. Update Redis GEO sorted set for available drivers
3. Publish to trip-specific channel if driver is on active trip (rider map)
4. Archive to time-series DB (downsampled after 30 days)

```python
async def on_location_update(msg: LocationUpdate) -> None:
    await redis.hset(f"driver:{msg.driver_id}", mapping=msg.as_dict())
    if msg.status == "available":
        await redis.geoadd("drivers:available", (msg.lng, msg.lat, msg.driver_id))
    else:
        await redis.zrem("drivers:available", msg.driver_id)
```

**Stale location kills matching.** Reject drivers whose `updated_at` > 30 seconds old. Riders hate watching a car icon freeze.

## Matching algorithm

On ride request:

1. Query `GEORADIUS` starting 1 km, expand to 2, 4, 8 km until candidates found or timeout
2. Filter: available status, correct vehicle type, not on another offer cooldown
3. Score by ETA (not distance) — call routing matrix API (OSRM, Google Distance Matrix) for top 10 candidates
4. Dispatch offer to best driver; wait 15s for accept/decline
5. If declined, offer next; if all decline, expand radius

```python
async def match_ride(ride: RideRequest) -> str | None:
    for radius_km in [1, 2, 4, 8]:
        candidates = await geo.nearby(ride.pickup, radius_km, limit=20)
        fresh = [c for c in candidates if await is_fresh(c.driver_id)]
        etas = await routing.eta_matrix(ride.pickup, [c.loc for c in fresh])
        ranked = sorted(zip(fresh, etas), key=lambda x: x[1])
        for driver, eta in ranked[:5]:
            if await dispatch.offer(driver, ride, ttl=15):
                return driver.id
    return None
```

Partition index by city or geohash prefix — global GEO set does not scale past low millions of members.

## Trip state machine and concurrency

Only one active trip per driver. Accept must be atomic:

```sql
UPDATE drivers SET status = 'on_trip', current_trip_id = $2
WHERE id = $1 AND status = 'available';
```

Zero rows → offer expired or driver taken. Use optimistic locking or Redis `WATCH/MULTI`.

Rider cancellation before pickup vs during trip has different fee rules — encode in policy service.

## Surge pricing

Divide map into hex cells (H3) or geohash precision-6. Every few minutes, compute demand/supply ratio per cell:

```
surge_multiplier = clamp(1.0 + (requests - drivers) / drivers * k, 1.0, 3.0)
```

Lock multiplier in `RideRequest` at creation — rider sees consistent price. Drivers receive surge bonus on completion.

Surge is a market signal, not punishment — transparency (show multiplier before confirm) reduces support load.

## Payments and fare calculation

Fare = base + distance×rate + time×rate + tolls + surge − promotions. Compute estimated fare at request; final fare at completion with actual GPS path (map-matched to roads to prevent GPS jitter fraud).

Payment authorization at trip start (hold estimated max); capture actual at end.

## Safety and trust

Share trip link, SOS button routing to emergency services with live location, driver/rider rating mutual blind, document verification for drivers. Background checks are offline workflows blocking `status=available`.

## Real-time rider experience

WebSocket channel `trip:{id}` pushes driver location, ETA updates, status changes. Fallback to 3s polling if socket drops.

## Analytics and supply forecasting

Heatmaps of unfulfilled requests guide driver incentives. ML forecasts demand by hour/zone — pre-positioning is ops, but data comes from your event stream.

## Synthesis

Cover location ingest freshness, GEO indexing, ETA-based matching (not distance), offer timeout loop, trip state atomicity, surge cell locking. Memorable framing: **Uber is a market maker on top of a geospatial index** — matching is the easy sentence; freshness and ETA are the hard engineering.
''',
}
