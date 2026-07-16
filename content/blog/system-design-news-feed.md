---
title: "System Design: News Feed"
slug: "system-design-news-feed"
description: "Design a social news feed system with fan-out on write vs read, ranking algorithms, and pagination for millions of users posting and consuming content."
datePublished: "2025-10-29"
dateModified: "2025-10-29"
tags: ["System Design", "Social", "Architecture", "Backend"]
keywords: "news feed system design, fan-out on write, fan-out on read, social feed architecture, timeline generation, feed ranking algorithm"
faq:
  - q: "Should a news feed use fan-out on write or fan-out on read?"
    a: "Fan-out on write (push) pre-computes each user's feed when a post is created — fast reads, expensive writes for users with millions of followers. Fan-out on read (pull) assembles the feed at request time — cheap writes, slower reads. Hybrid is standard: push for normal users, pull for celebrities with huge follower counts. Twitter uses push for most users and pull for accounts above a follower threshold."
  - q: "How do you rank feed items beyond chronological order?"
    a: "Production feeds use multi-signal ranking: recency, engagement velocity (likes/comments in first hour), relationship strength (interaction frequency with poster), content type preferences, and diversity (don't show five posts from the same person). Build a candidate generation stage (fetch recent posts from followed users), then a lightweight ranking model (logistic regression or small neural net) to score and sort candidates."
  - q: "How do you paginate an infinite feed efficiently?"
    a: "Use cursor-based pagination with a composite cursor (timestamp + post_id) instead of offset pagination. Offset breaks when new items are inserted during scrolling. Store the cursor client-side and pass it with each request: GET /feed?cursor=1700000000:post_abc123&limit=20. The server returns the next 20 items before that cursor plus a next_cursor for the following page."
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

## Common production mistakes

Teams get news feed wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

System design for news feed breaks at scale when hot keys, thundering herds, and cache stampedes are discovered during launch week instead of load test week.

## Debugging and triage workflow

When news feed misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [Twitter's timeline architecture (highscalability.com)](http://highscalability.com/blog/2013/7/8/the-architecture-twitter-uses-to-deal-with-150m-active-users.html)
- [Facebook's news feed ranking (Meta engineering)](https://engineering.fb.com/)
- [Redis sorted sets documentation](https://redis.io/docs/data-types/sorted-sets/)
- [Fan-out strategies comparison](https://www.youtube.com/results?search_query=news+feed+fan+out+system+design)
- [Designing Data-Intensive Applications — Ch. 11 Stream Processing](https://dataintensive.net/)
