---
title: "System Design: Notification System"
slug: "system-design-notification-system"
description: "Design a multi-channel notification system delivering push, email, SMS, and in-app alerts to millions of users with templates, preferences, and delivery guarantees."
datePublished: "2025-11-01"
dateModified: "2025-11-01"
tags: ["System Design", "Notifications", "Architecture", "Backend"]
keywords: "notification system design, push notification architecture, multi-channel notifications, email SMS delivery, notification preferences, idempotent delivery"
faq:
  - q: "How do you prevent duplicate notifications?"
    a: "Assign each notification a unique idempotency key (event_id + user_id + channel). Before sending, check a deduplication store (Redis with TTL). If the key exists, skip delivery. This handles at-least-once message queue delivery that would otherwise send the same alert twice. TTL should match the deduplication window — typically 24 hours for transactional, 1 hour for high-frequency events."
  - q: "How do notification preferences work at scale?"
    a: "Store per-user, per-notification-type preferences in a fast lookup store (Redis or a dedicated service). Each notification event includes a type (order_shipped, friend_request, marketing_promo). Before delivery, the preference service checks: is this channel enabled for this type? Is the user in quiet hours? Has the user opted out of marketing? Fail open for critical transactional notifications (password reset); fail closed for marketing."
  - q: "Push vs email vs SMS — when to use each channel?"
    a: "Push for time-sensitive, action-required alerts (message received, ride arrived) — highest open rates but requires app install. Email for detailed content, receipts, and non-urgent updates — works without app, supports rich formatting. SMS for critical alerts when push may not reach (two-factor codes, delivery confirmations) — most expensive, use sparingly. Let users configure channel preferences per notification type."
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

## Common production mistakes

Teams get notification system wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

System design for notification system breaks at scale when hot keys, thundering herds, and cache stampedes are discovered during launch week instead of load test week.

## Debugging and triage workflow

When notification system misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [Apple Push Notification service documentation](https://developer.apple.com/documentation/usernotifications)
- [Firebase Cloud Messaging architecture](https://firebase.google.com/docs/cloud-messaging/fcm-architecture)
- [Amazon SES best practices](https://docs.aws.amazon.com/ses/latest/dg/best-practices.html)
- [Twilio SMS delivery architecture](https://www.twilio.com/docs/messaging)
- [Courier.dev — notification infrastructure patterns](https://www.courier.com/docs)
