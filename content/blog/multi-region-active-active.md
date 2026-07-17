---
title: "Multi-Region Active-Active Architecture"
slug: "multi-region-active-active"
description: "Multi-region active-active architecture explained: latency routing, data replication and conflict resolution, the CAP tradeoffs, and when the complexity is worth it."
datePublished: "2026-06-23"
dateModified: "2026-07-17"
tags:
keywords: "active-active, multi-region, geo replication, failover, latency-based routing, conflict resolution, disaster recovery"
faq:
  - q: "What is an active-active multi-region architecture?"
    a: "Active-active means running your application in two or more geographic regions that all serve live production traffic simultaneously, rather than keeping one region idle as a standby. Users are routed to the nearest healthy region, and if a region fails, the others absorb its traffic — giving you both lower latency and near-instant failover."
  - q: "How is active-active different from active-passive?"
    a: "In active-passive, only the primary region serves traffic and the secondary sits warm or cold as a failover target, so you pay for capacity you rarely use and failover takes minutes. In active-active, every region serves traffic all the time, so failover is nearly instantaneous and resources aren't wasted — but data consistency across regions becomes a hard problem you must solve."
  - q: "What is the hardest part of going active-active?"
    a: "Data. Serving reads and writes in multiple regions at once means the same record can be modified in two places nearly simultaneously, so you must choose a replication and conflict-resolution strategy — and accept the consistency tradeoffs the CAP theorem imposes. The compute tier is comparatively easy; the database is where active-active projects succeed or fail."
---
Active-active is what you build when a region going down cannot be allowed to take your product with it — and when your users are spread across continents you don't want to serve all of them from Virginia. A multi-region active-active architecture runs your full application stack in two or more regions that *all* serve live traffic at once. Users hit the nearest healthy region for lower latency, and losing an entire region degrades capacity rather than causing an outage. The payoff is resilience and speed; the price, which I'll be honest about, is a genuinely hard data-consistency problem.

I've built toward this twice, and both times the compute tier was the easy 20% and the data tier was the hard 80%. Let's take the layers in order of increasing difficulty.

## Routing: getting users to the right region

The front door is DNS or anycast-based global routing. Latency-based routing (Route 53, Cloud DNS, or an anycast CDN edge) sends each user to the region that answers fastest, which usually correlates with geographic proximity. Health checks are what make it *active-active* rather than just multi-region: when a region fails its health check, it's pulled from rotation and traffic redistributes automatically.

The subtlety people miss is DNS TTL. If your TTL is 300 seconds, a region failure can leave clients pointed at a dead region for up to five minutes even after routing updates. Anycast handles this faster because failover happens at the network layer, not via DNS caches. For true low-RTO failover, I lean on anycast at the edge and treat DNS as the coarser control. This routing behavior is also worth exercising deliberately — it's a prime target for [chaos engineering](https://blog.michaelsam94.com/chaos-engineering-practical/), because "we assumed failover worked" is a sentence that precedes many outages.

## Stateless compute is the easy part

Your application servers, if they're properly stateless, are almost trivial to run active-active: deploy the same containers in each region, point them at region-local caches and databases, and let the router balance. No session affinity to a region, no local disk state — session data goes in a shared or replicated store. If your services already follow twelve-factor principles, this layer is mostly a deployment-topology change.

The one real decision is whether a region's compute talks only to its own regional data plane (lower latency, cleaner failure isolation) or can read cross-region (simpler, but you've now coupled regions). I default to region-local data access and treat cross-region calls as an explicit, rare exception, because a synchronous cross-region hop on the hot path quietly reintroduces the single-region failure you were trying to eliminate.

## The data tier: where it gets real

Here's the crux. The moment two regions both accept writes, the same logical record can be modified in both places within the replication window. CAP theorem stops being an interview question and becomes a design constraint you live with daily: during a network partition between regions, you choose consistency or availability, not both.

Your realistic options:

| Strategy | Consistency | Write availability | Complexity |
| --- | --- | --- | --- |
| Single-writer (one region owns writes) | Strong | Fails over on region loss | Low |
| Multi-writer + conflict resolution | Eventual | Any region writes | High |
| Sharded by region (data locality) | Strong per shard | Per-shard | Medium |
| Globally-distributed DB (Spanner/CockroachDB) | Tunable | High | Managed for you |

Single-writer is the pragmatic starting point: all writes route to a primary region, reads are served locally everywhere, and failover promotes another region. You get most of the latency and availability benefits with far less complexity, at the cost of write-path failover time.

True multi-writer active-active means embracing eventual consistency and a conflict-resolution model — last-write-wins (simple, lossy), CRDTs (correct for certain data shapes), or application-level merge logic. This is where teams underestimate the work. "Two users edited the same profile from two regions" needs a defined, tested answer, or you silently lose data.

## Conflict resolution in practice

If you go multi-writer, make conflicts explicit rather than hoping they don't happen. A version-vector or timestamp approach at the application layer looks conceptually like this:

```python
def resolve(local, remote):
    # Last-write-wins with a tiebreaker on region id for determinism.
    if remote.updated_at > local.updated_at:
        return remote
    if remote.updated_at < local.updated_at:
        return local
    return remote if remote.region_id > local.region_id else local
```

Last-write-wins is defensible for data where losing the older write is acceptable (a user's display name). It's *not* acceptable for anything additive — inventory counts, financial balances, shopping carts — where you need CRDTs or a single-writer authority. Choosing per-data-type rather than one global policy is the mark of a design that's actually thought it through. And for anything spanning multiple services, cross-region makes distributed transactions even thornier, which is why the [saga pattern for distributed transactions](https://blog.michaelsam94.com/saga-pattern-distributed-transactions/) becomes almost mandatory — two-phase commit across regions is a latency and availability trap.

## Schema changes and operational reality

Running active-active makes routine operations harder. A schema migration must now be backward-compatible across regions mid-rollout, because two versions of your app will be live in different regions simultaneously for a window. The expand-contract discipline from [zero-downtime database migrations](https://blog.michaelsam94.com/zero-downtime-database-migrations/) isn't optional here — it's the only safe way to change a schema that's being written to in multiple places.

You also inherit harder observability: you need per-region dashboards *and* a global view, plus replication-lag monitoring as a first-class SLO. Replication lag is the metric that tells you how stale a region's data is and how much you'd lose on failover; if you're not alerting on it, you're flying blind.

## When it's actually worth it

Be honest about whether you need this. Active-active roughly doubles your infrastructure spend and multiplies operational complexity. It's justified when downtime has severe regulatory or revenue consequences, when you have a genuinely global user base with latency requirements a single region can't meet, or when your SLA promises availability a single region statistically can't deliver.

For most products, a well-run active-passive setup with tested failover delivers 95% of the resilience for a fraction of the complexity, and I'll recommend it every time the requirements don't clearly demand more. Reach for active-active when the business truly cannot tolerate a regional outage — and when you've accepted that the data tier, not the servers, is the project. Go in with your consistency model chosen deliberately per data type, your replication lag monitored like a heartbeat, and your failover rehearsed rather than assumed.

## Resources

- [AWS — Multi-Region Application Architecture](https://docs.aws.amazon.com/whitepapers/latest/aws-fault-isolation-boundaries/multi-region-scenarios.html)
- [Google Cloud Spanner — architecture](https://cloud.google.com/spanner/docs/whitepapers)
- [CockroachDB — multi-region overview](https://www.cockroachlabs.com/docs/stable/multiregion-overview)
- [Jepsen — distributed systems consistency analyses](https://jepsen.io/analyses)
- [Martin Kleppmann — CRDTs and conflict resolution](https://martin.kleppmann.com/papers.html)
- [The CAP theorem (original, Brewer)](https://www.infoq.com/articles/cap-twelve-years-later-how-the-rules-have-changed/)
