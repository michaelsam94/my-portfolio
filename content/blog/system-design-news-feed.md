---
title: "System Design: News Feed"
slug: "system-design-news-feed"
description: "Design a social news feed system with fan-out on write vs read, ranking algorithms, and pagination for millions of users posting and consuming content."
datePublished: "2025-10-29"
dateModified: "2026-07-17"
tags: ["System Design", "Social", "Architecture", "Backend"]
keywords: "news feed system design, fan-out on write, fan-out on read, social feed architecture, timeline generation, feed ranking algorithm"
faq:
  - q: "Should a news feed use fan-out on write or fan-out on read?"
    a: "Fan-out on write (push) pre-computes each user's feed when a post is created — fast reads, expensive writes for users with millions of followers. Fan-out on read (pull) assembles the feed at request time — cheap writes, slower reads. Hybrid is standard: push for normal users, pull for celebrities with huge follower counts. Twitter uses push for most users and pull for accounts above a follower threshold."
  - q: "How do you rank feed items beyond chronological order?"
    a: "Production feeds use multi-signal ranking: recency, engagement velocity (likes/comments in first hour), relationship strength (interaction frequency with poster), content type preferences, and diversity (don't show five posts from the same person). Build a candidate generation stage (fetch recent posts from followed users), then a lightweight ranking model (logistic regression or small neural net) to score and sort candidates."
  - q: "How do you paginate an infinite feed efficiently?"
    a: "Use cursor-based pagination with a composite cursor (timestamp + post_id) instead of offset pagination. Offset breaks when new items are inserted during scrolling. Store the cursor client-side and pass it with each request: GET /feed?cursor=1700000000:post_abc123&limit=20. The server returns the next 20 items before that cursor plus a next_cursor for the following page."
faqAnswers:
  - question: "When is system design news feed the wrong approach?"
    answer: "When a simpler control already covers the risk, or when the operational cost exceeds the benefit for your threat and traffic model."
  - question: "What should we measure for system design news feed?"
    answer: "Pair a leading operational signal with a lagging user or risk outcome, reviewed on a fixed cadence with a named owner."
  - question: "How do we roll back system design news feed safely?"
    answer: "Keep the prior artifact or config warm, rehearse the revert once in staging, and document the one-command rollback for on-call."
---
Facebook's news feed serves 2.9 billion users, each seeing a different ordered list of posts from hundreds of friends and pages they follow. The naive approach — query all posts from followed users, sort by time, return top 20 — takes seconds per request when a user follows 500 accounts with millions of total posts. Production feeds pre-compute, cache, rank, and paginate through a pipeline designed for read-heavy, write-bursty workloads.

## Fan-out strategies

**Fan-out on write (push model):**

When user A posts, write the post ID to every follower's feed cache:

```
A posts → Post Service → Fan-out Worker → [B's feed, C's feed, D's feed, ...]
```

- Read: O(1) — fetch pre-built feed from cache.
- Write: O(followers) — expensive for celebrities.

**Fan-out on read (pull model):**

When user B requests their feed, query recent posts from all followed users and merge:

```
B requests feed → Feed Service → Query posts from {followed users} → Merge & rank → Return
```

- Read: O(following) — slow for users following many accounts.
- Write: O(1) — just store the post.

**Hybrid (production standard):**

```python
FANOUT_THRESHOLD = 10_000  # followers

async def publish_post(author_id: str, content: str):
    post = await post_service.create(author_id, content)
    follower_count = await social_graph.get_follower_count(author_id)

    if follower_count < FANOUT_THRESHOLD:
        # Push: fan-out to follower feed caches
        followers = await social_graph.get_followers(author_id)
        await fanout_worker.dispatch(post.id, followers)
    else:
        # Pull: store in celebrity's post list only
        await celebrity_posts.add(author_id, post.id)

    return post
```

Normal users get push fan-out. Celebrities (above threshold) use pull — their posts are fetched and merged at read time.

## Feed storage

Pre-built feeds stored in Redis sorted sets:

```
Key: feed:{user_id}
Type: Sorted Set
Score: timestamp (or rank score)
Member: post_id
```

```python
async def get_feed(user_id: str, cursor: str = None, limit: int = 20):
    # Fetch push-model posts from cache
    cached = await redis.zrevrangebyscore(
        f"feed:{user_id}",
        max=cursor_timestamp if cursor else "+inf",
        min="-inf",
        start=0, num=limit * 2  # over-fetch for ranking
    )

    # Fetch pull-model posts from celebrities
    celebrities = await social_graph.get_followed_celebrities(user_id)
    celebrity_posts = await fetch_recent_posts(celebrities, since=cursor_timestamp)

    # Merge, rank, and return
    candidates = cached + celebrity_posts
    ranked = rank_feed(candidates, user_id)
    return ranked[:limit]
```

Sorted sets give O(log N) insertion and range queries — efficient for feeds with thousands of cached post IDs.

## Ranking pipeline

Chronological order is the baseline. Production feeds add a ranking stage:

```python
def rank_feed(candidates: list[Post], user_id: str) -> list[Post]:
    for post in candidates:
        post.score = (
            recency_score(post.timestamp) * 0.3 +
            engagement_score(post.likes, post.comments) * 0.25 +
            relationship_score(user_id, post.author_id) * 0.25 +
            content_type_score(post.type, user_id) * 0.1 +
            diversity_penalty(post, candidates) * 0.1
        )
    return sorted(candidates, key=lambda p: p.score, reverse=True)
```

Start with heuristic weights. Graduate to ML models (gradient boosted trees, small neural nets) trained on engagement data (clicks, likes, time spent) when you have sufficient data volume.

## Social graph service

The social graph (follow/follower relationships) is a separate service:

```sql
-- Sharded by follower_id for "who do I follow?" queries
CREATE TABLE follows (
    follower_id BIGINT,
    followee_id BIGINT,
    created_at TIMESTAMP,
    PRIMARY KEY (follower_id, followee_id)
);

-- Reverse index sharded by followee_id for fan-out
CREATE TABLE followers (
    followee_id BIGINT,
    follower_id BIGINT,
    PRIMARY KEY (followee_id, follower_id)
);
```

For users with millions of followers, the followers table is sharded across multiple nodes. Fan-out workers process followers in batches to avoid overwhelming the feed cache write path.

## Handling hot posts and viral content

When a post goes viral, millions of users may see it through pull-model celebrity feeds or recommendation injection. Mitigations:

- **Separate viral post cache** with aggressive CDN caching for the post content itself.
- **Rate-limit fan-out** for rapidly gaining followers (detect bot follower spikes).
- **Feed deduplication** — if the same viral post appears through multiple paths (followed user + recommended), show it once.

## Cursor-based pagination

```python
def encode_cursor(timestamp: float, post_id: str) -> str:
    return base64.encode(f"{timestamp}:{post_id}")

def decode_cursor(cursor: str) -> tuple[float, str]:
    decoded = base64.decode(cursor)
    ts, post_id = decoded.split(":")
    return float(ts), post_id
```

Client stores `next_cursor` from each response and passes it to the next request. Stable under concurrent inserts — unlike offset pagination where page 2 shifts when new items appear at the top.

Treat production rollout as a measured change: ship with observability, validate rollback, and review metrics 24 hours after deploy — patterns that look obvious in docs fail when skipped under release pressure.

## Cold start feed for new users

Users with zero follows need curated onboarding feed — merge RECOMMENDED stream with empty follow graph. Cache separately from personalized feeds; invalidate onboarding set daily without busting per-user feed keys.

## Feed deduplication on repost

Repost same post_id from different actors — ranker dedupes by canonical post_id keeping highest engagement entry. Without dedup, timeline shows identical content three times when viral post crosses follow graph clusters.

## Integration testing notes

Exercise the happy path plus three failure modes specific to system design news feed: dependency timeout, duplicate delivery, and partial deploy during rolling update. Automated tests should assert idempotent behavior and user-visible error messages—not only HTTP 200 from mocks.

## Documentation and on-call

Link runbook steps from the service catalog entry for system design news feed. On-call engineers should find rollback command, dashboard URL, and known false-positive alerts without searching Slack history. Update the entry when behavior or metrics change.

## Rollout checklist

Ship behind a feature flag when behavior is user-visible. Compare error rate and p95 latency for seven days against baseline captured before merge. Document rollback in the pull request so on-call can revert without author contact.

## Quick reference

Hybrid fan-out: push for normal users, pull merge for celebrity accounts above threshold. Keep a dashboard per critical user journey and review weekly during the first month after launch.

Review metrics quarterly; traffic mix shifts can invert prior wins without code changes.

## Resources

- [Twitter's timeline architecture (highscalability.com)](http://highscalability.com/blog/2013/7/8/the-architecture-twitter-uses-to-deal-with-150m-active-users.html)
- [Facebook's news feed ranking (Meta engineering)](https://engineering.fb.com/)
- [Redis sorted sets documentation](https://redis.io/docs/data-types/sorted-sets/)
- [Fan-out strategies comparison](https://www.youtube.com/results?search_query=news+feed+fan+out+system+design)
- [Designing Data-Intensive Applications — Ch. 11 Stream Processing](https://dataintensive.net/)

## Failure modes specific to system design news feed

System design interviews and production systems diverge: system design news feed in production needs SLOs, abuse controls, and multi-region failure stories. Sketch the data model and consistency requirements before drawing boxes.

For system design news feed:
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

## Migration path into system design news feed

Reviewers should challenge assumptions encoded in system design news feed: defaults copied from tutorials, timeouts that exceed upstream SLAs, and authz checks applied only on the primary UI path. Require a short threat or failure note in the PR when the change touches a trust boundary.

Concrete probes:
1. Scenario A for system design news feed: partial dependency outage — prove clients degrade gracefully and retries do not amplify load.
2. Scenario B for system design news feed: bad config shipped — prove rollback within the declared RTO without data corruption.
3. Scenario C for system design news feed: traffic 3× baseline — prove autoscaling or shedding keeps the golden journey healthy.

## Post-incident changes after system design news feed failures

Roll out system design news feed behind a flag or weighted route when possible. Start with internal users or a low-risk geography. Watch the signals in the table for at least one full business cycle before calling the migration done. Keep the previous path warm until error budgets stabilize.

Document the owner, the dashboard, and the single command that reverts the change. If that sentence is hard to write, the design is not ready for production traffic.

## Compliance evidence for system design news feed

Detail 1 (660): for system design news feed, define the contract between producers and consumers explicitly — payload shape, timeout, and idempotency key. When compliance evidence for system design news feed becomes painful, it is usually because that contract was implicit.

I keep a short matrix: who can break system design news feed, how we detect it within five minutes, and who is paged. Update the matrix when ownership moves. Add one synthetic check that exercises the failure path, not only the happy path. Prefer checks that run continuously over quarterly manual reviews that everyone skips under deadline pressure.

If you only remember one thing about system design news feed: optimize for reversible decisions. Reversibility beats cleverness when the incident channel is busy and the blast radius is unclear.

## Developer experience when changing system design news feed

Detail 2 (617): for system design news feed, define the contract between producers and consumers explicitly — payload shape, timeout, and idempotency key. When developer experience when changing system design news feed becomes painful, it is usually because that contract was implicit.

I keep a short matrix: who can break system design news feed, how we detect it within five minutes, and who is paged. Update the matrix when ownership moves. Add one synthetic check that exercises the failure path, not only the happy path. Prefer checks that run continuously over quarterly manual reviews that everyone skips under deadline pressure.

If you only remember one thing about system design news feed: optimize for reversible decisions. Reversibility beats cleverness when the incident channel is busy and the blast radius is unclear.