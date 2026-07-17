---
title: "System Design: Notification System"
slug: "system-design-notification-system"
description: "Design a multi-channel notification system delivering push, email, SMS, and in-app alerts to millions of users with templates, preferences, and delivery guarantees."
datePublished: "2025-11-01"
dateModified: "2026-07-17"
tags: ["System Design", "Notifications", "Architecture", "Backend"]
keywords: "notification system design, push notification architecture, multi-channel notifications, email SMS delivery, notification preferences, idempotent delivery"
faq:
  - q: "How do you prevent duplicate notifications?"
    a: "Assign each notification a unique idempotency key (event_id + user_id + channel). Before sending, check a deduplication store (Redis with TTL). If the key exists, skip delivery. This handles at-least-once message queue delivery that would otherwise send the same alert twice. TTL should match the deduplication window — typically 24 hours for transactional, 1 hour for high-frequency events."
  - q: "How do notification preferences work at scale?"
    a: "Store per-user, per-notification-type preferences in a fast lookup store (Redis or a dedicated service). Each notification event includes a type (order_shipped, friend_request, marketing_promo). Before delivery, the preference service checks: is this channel enabled for this type? Is the user in quiet hours? Has the user opted out of marketing? Fail open for critical transactional notifications (password reset); fail closed for marketing."
  - q: "Push vs email vs SMS — when to use each channel?"
    a: "Push for time-sensitive, action-required alerts (message received, ride arrived) — highest open rates but requires app install. Email for detailed content, receipts, and non-urgent updates — works without app, supports rich formatting. SMS for critical alerts when push may not reach (two-factor codes, delivery confirmations) — most expensive, use sparingly. Let users configure channel preferences per notification type."
faqAnswers:
  - question: "When is system design notification system the wrong approach?"
    answer: "When a simpler control already covers the risk, or when the operational cost exceeds the benefit for your threat and traffic model."
  - question: "What should we measure for system design notification system?"
    answer: "Pair a leading operational signal with a lagging user or risk outcome, reviewed on a fixed cadence with a named owner."
  - question: "How do we roll back system design notification system safely?"
    answer: "Keep the prior artifact or config warm, rehearse the revert once in staging, and document the one-command rollback for on-call."
---
Our order-shipped notification was simple in development: send an email. In production, it needed to check whether the user prefers push over email, whether they're in a quiet-hours window, whether they already received this notification from a retry, render the template in the user's language, and deliver through APNs, FCM, SendGrid, or Twilio depending on channel — all within five seconds of the shipping event. The notification system became its own platform, decoupled from every product feature that triggers alerts.

## Architecture overview

```
Event Sources → Notification Service → Template Engine → Channel Router
                                         ↓                    ↓
                                   Preference Service    ┌── Push (APNs/FCM)
                                                         ├── Email (SendGrid/SES)
                                                         ├── SMS (Twilio)
                                                         └── In-App (WebSocket)
```

Product services publish notification events to a message queue. The notification service consumes events, resolves templates, checks preferences, routes to channels, and tracks delivery status.

## Event ingestion

Product services emit structured notification events:

```json
{
  "event_id": "evt_abc123",
  "type": "order_shipped",
  "user_id": "user_456",
  "data": {
    "order_id": "ord_789",
    "tracking_number": "1Z999AA10123456784",
    "estimated_delivery": "2025-11-08"
  },
  "priority": "high",
  "channels": ["push", "email"]
}
```

The notification service validates, deduplicates, and enqueues for processing:

```python
async def handle_notification_event(event: NotificationEvent):
    dedup_key = f"{event.event_id}:{event.user_id}"
    if await redis.exists(dedup_key):
        return  # Already processed

    await redis.setex(dedup_key, 86400, "1")

    preferences = await preference_service.get(event.user_id, event.type)
    channels = [c for c in event.channels if preferences.is_enabled(c)]

    if not channels:
        return

    for channel in channels:
        await delivery_queue.enqueue(
            DeliveryTask(event=event, channel=channel)
        )
```

## Template engine

Templates separate content from delivery logic:

```html
<!-- order_shipped.email.hbs -->
<h1>Your order is on its way!</h1>
<p>Hi {{user.name}},</p>
<p>Order #{{order_id}} has shipped.</p>
<p>Tracking: <a href="{{tracking_url}}">{{tracking_number}}</a></p>
<p>Estimated delivery: {{estimated_delivery}}</p>
```

```json
// order_shipped.push.json
{
  "title": "Order Shipped!",
  "body": "Order #{{order_id}} is on its way. Track: {{tracking_number}}",
  "data": { "order_id": "{{order_id}}", "action": "track" }
}
```

Templates support localization (render with user's locale), A/B variants, and dynamic content injection from event data. Store templates in a versioned repository; deploy template changes independently from code.

## Channel delivery

Each channel has a dedicated worker with retry logic:

```python
class PushDeliveryWorker:
    async def deliver(self, task: DeliveryTask):
        rendered = await template_engine.render(
            task.event.type, "push", task.event.data,
            locale=task.user.locale
        )

        device_tokens = await device_service.get_tokens(task.event.user_id)
        for token in device_tokens:
            try:
                if token.platform == "ios":
                    await apns.send(token.value, rendered)
                elif token.platform == "android":
                    await fcm.send(token.value, rendered)
                await delivery_log.record(task, token, status="delivered")
            except InvalidTokenError:
                await device_service.remove_token(token)
            except TransientError:
                await retry_queue.enqueue(task, delay=exponential_backoff)
```

**Push (APNs/FCM):** Low latency, high engagement. Handle invalid token cleanup (users who uninstalled). Batch sends where possible.

**Email (SendGrid/SES):** Async delivery, supports HTML. Track bounces and complaints to maintain sender reputation. Unsubscribe links required for marketing.

**SMS (Twilio):** Expensive ($0.01-0.05 per message). Reserve for critical alerts. Respect opt-out lists (TCPA compliance).

**In-app:** Store in a notification inbox table. Deliver via WebSocket for real-time badge updates. Persist for users who were offline.

## User preferences

```sql
CREATE TABLE notification_preferences (
    user_id UUID,
    notification_type TEXT,
    channel TEXT,
    enabled BOOLEAN DEFAULT true,
    PRIMARY KEY (user_id, notification_type, channel)
);

CREATE TABLE quiet_hours (
    user_id UUID PRIMARY KEY,
    start_time TIME,
    end_time TIME,
    timezone TEXT
);
```

Preference checks happen before every delivery attempt. Critical notifications (security alerts, payment confirmations) bypass quiet hours and channel opt-outs. Marketing notifications require explicit opt-in.

## Rate limiting and batching

Prevent notification fatigue and provider rate limits:

- **Per-user rate limit:** Max 10 push notifications per hour (configurable).
- **Digest batching:** Low-priority notifications (social likes, activity updates) batch into hourly or daily digests.
- **Provider rate limits:** APNs allows ~4000/sec per connection. FCM has project-level quotas. Queue and throttle accordingly.

```python
async def should_deliver(user_id: str, notification_type: str) -> bool:
    count = await redis.incr(f"rate:{user_id}:{hour_bucket()}")
    if count == 1:
        await redis.expire(f"rate:{user_id}:{hour_bucket()}", 3600)
    return count <= MAX_NOTIFICATIONS_PER_HOUR
```

## Delivery tracking and analytics

Track every delivery attempt:

```sql
CREATE TABLE delivery_log (
    id UUID,
    event_id TEXT,
    user_id UUID,
    channel TEXT,
    status TEXT,  -- queued, sent, delivered, failed, bounced
    provider_id TEXT,
    sent_at TIMESTAMP,
    delivered_at TIMESTAMP
);
```

Metrics: delivery rate by channel, time-to-deliver p99, bounce rate, opt-out rate. Alert on delivery rate drops — often indicates provider issues or invalid token buildup.

Treat production rollout as a measured change: ship with observability, validate rollback, and review metrics 24 hours after deploy — patterns that look obvious in docs fail when skipped under release pressure.

## Delivery guarantees and provider quirks

APNs and FCM have different failure semantics. APNs returns permanent failures for uninstalled apps — remove dead tokens from your device registry. FCM supports topic subscriptions for broadcast but adds delivery latency. Email providers throttle by domain reputation — warm up sending domains gradually after migration. SMS is expensive; reserve for OTP and critical alerts. Log delivery status per channel with provider message IDs for support lookup when users claim they never received an alert.

## Quiet hours and frequency caps

Respect user quiet hours per timezone — batch non-urgent pushes until morning unless the user opted into real-time alerts. Frequency caps prevent notification fatigue: max three marketing pushes per week, unlimited for security and transaction channels. Unsubscribe on email must not disable OTP SMS; channel preferences are independent dimensions in the user profile store.

## Resources

- [Apple Push Notification service documentation](https://developer.apple.com/documentation/usernotifications)
- [Firebase Cloud Messaging architecture](https://firebase.google.com/docs/cloud-messaging/fcm-architecture)
- [Amazon SES best practices](https://docs.aws.amazon.com/ses/latest/dg/best-practices.html)
- [Twilio SMS delivery architecture](https://www.twilio.com/docs/messaging)
- [Courier.dev — notification infrastructure patterns](https://www.courier.com/docs)

## system design notification system rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## system design notification system rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## system design notification system rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## system design notification system rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## Trade-offs I keep revisiting for system design notification system

System design interviews and production systems diverge: system design notification system in production needs SLOs, abuse controls, and multi-region failure stories. Sketch the data model and consistency requirements before drawing boxes.

For system design notification system:
- Separate read and write scaling paths early if fan-out or search is involved
- Idempotency keys on payments, bookings, and message delivery
- Backpressure at every queue; unbounded buffers are delayed outages
- Hot-key and thundering-herd mitigations (jitter, singleflight, cache stampedes)

Write the load-test plan that would disprove your capacity claims — QPS, payload sizes, and regional failover RTO.

| Signal | Target | Alarm |
|--------|--------|-------|
| Coverage % | Team-defined SLO | Page on burn rate |
| Mean time to detect | Baseline − noise | Ticket if sustained |
| Escapes to prod | Budget cap | Weekly review |

## Ownership and on-call for system design notification system

Reviewers should challenge assumptions encoded in system design notification system: defaults copied from tutorials, timeouts that exceed upstream SLAs, and authz checks applied only on the primary UI path. Require a short threat or failure note in the PR when the change touches a trust boundary.

Concrete probes:
1. Scenario C for system design notification system: traffic 3× baseline — prove autoscaling or shedding keeps the golden journey healthy.
2. Scenario A for system design notification system: partial dependency outage — prove clients degrade gracefully and retries do not amplify load.
3. Scenario B for system design notification system: bad config shipped — prove rollback within the declared RTO without data corruption.

## Cross-team contracts for system design notification system

Roll out system design notification system behind a flag or weighted route when possible. Start with internal users or a low-risk geography. Watch the signals in the table for at least one full business cycle before calling the migration done. Keep the previous path warm until error budgets stabilize.

Document the owner, the dashboard, and the single command that reverts the change. If that sentence is hard to write, the design is not ready for production traffic.

## Multi-tenant concerns in system design notification system

Detail 1 (584): for system design notification system, define the contract between producers and consumers explicitly — payload shape, timeout, and idempotency key. When multi-tenant concerns in system design notification system becomes painful, it is usually because that contract was implicit.

I keep a short matrix: who can break system design notification system, how we detect it within five minutes, and who is paged. Update the matrix when ownership moves. Add one synthetic check that exercises the failure path, not only the happy path. Prefer checks that run continuously over quarterly manual reviews that everyone skips under deadline pressure.

If you only remember one thing about system design notification system: optimize for reversible decisions. Reversibility beats cleverness when the incident channel is busy and the blast radius is unclear.

## Compliance evidence for system design notification system

Detail 2 (249): for system design notification system, define the contract between producers and consumers explicitly — payload shape, timeout, and idempotency key. When compliance evidence for system design notification system becomes painful, it is usually because that contract was implicit.

I keep a short matrix: who can break system design notification system, how we detect it within five minutes, and who is paged. Update the matrix when ownership moves. Add one synthetic check that exercises the failure path, not only the happy path. Prefer checks that run continuously over quarterly manual reviews that everyone skips under deadline pressure.

If you only remember one thing about system design notification system: optimize for reversible decisions. Reversibility beats cleverness when the incident channel is busy and the blast radius is unclear.