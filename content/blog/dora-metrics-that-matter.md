---
title: "DORA Metrics Without the Vanity"
slug: "dora-metrics-that-matter"
description: "DORA metrics without the vanity: what deployment frequency, lead time, change failure rate, and MTTR really measure — and how to use them without gaming them."
datePublished: "2026-01-23"
dateModified: "2026-01-23"
tags: ["DevOps", "SRE", "Metrics"]
keywords: "DORA metrics, deployment frequency, lead time, change failure rate, MTTR, delivery performance"
faq:
  - q: "What are the four DORA metrics?"
    a: "The four DORA metrics are deployment frequency, lead time for changes, change failure rate, and time to restore service (often called MTTR). They come from the DevOps Research and Assessment program and together measure both delivery throughput and delivery stability, which research links to overall organizational performance."
  - q: "Are DORA metrics team-level or individual metrics?"
    a: "Strictly team- and system-level. DORA metrics describe the delivery capability of a team's software system, not the productivity of any person. Using them to rank or evaluate individuals is the fastest way to get them gamed and to destroy the trust that makes them useful in the first place."
  - q: "What's a realistic target for the four metrics?"
    a: "It depends on your context, but the research's 'elite' band is roughly: deploy on demand (multiple times a day), lead time under an hour, change failure rate under 15%, and restore time under an hour. Most teams should aim to improve their own trend rather than chase elite numbers they don't need."
---

DORA metrics get quoted in every engineering all-hands and misused in most of them. The four metrics — deployment frequency, lead time for changes, change failure rate, and time to restore service — measure how well a team's software delivery *system* performs, balancing throughput against stability. Used honestly, they tell you whether your engineering process is getting faster and safer over time. Used as a scoreboard, they become another number to game, and you end up worse off than having no metrics at all.

I've watched both outcomes. The difference is never the metrics themselves; it's what leadership does with them. Let me walk through what each one actually captures, then the failure modes.

## The two throughput metrics

**Deployment frequency** and **lead time for changes** measure velocity — how quickly value moves from a developer's laptop to production.

Deployment frequency is exactly what it sounds like: how often you ship to production. The reason it correlates with good outcomes isn't that shipping is inherently virtuous — it's that frequent deploys *force* small batches, and small batches are easier to test, review, and roll back. A team deploying 20 times a day has necessarily solved automation, testing, and rollback. A team deploying once a month usually hasn't.

Lead time for changes measures the time from a commit merging to that code running in production. It's the clock on your delivery pipeline. If lead time is measured in days, the bottleneck is almost always process — manual approvals, slow builds, a release train that leaves twice a week. This is where investment in [fast CI/CD pipelines](https://blog.michaelsam94.com/fast-cicd-pipelines/) pays off directly and measurably; shave the pipeline and lead time drops with it.

## The two stability metrics

The throughput metrics only mean something when paired with stability, or you'd "optimize" by shipping garbage fast.

**Change failure rate** is the percentage of deployments that cause a failure in production requiring remediation — a rollback, a hotfix, a patch. It's your quality signal. A rising deployment frequency with a flat-or-falling change failure rate is the dream: you're getting faster *and* safer. A rising failure rate is the system telling you your speed is outrunning your safety nets.

**Time to restore service** (commonly MTTR) measures how long it takes to recover once something breaks. This one is underrated. It reframes reliability from "never fail" — impossible — to "recover fast," which is achievable and honest. A low restore time reflects good observability, tested rollbacks, and a healthy [incident response process](https://blog.michaelsam94.com/incident-management-postmortems/). It's arguably the most operationally meaningful of the four.

Here's the balance in one view:

| Metric | Measures | Improves via |
| --- | --- | --- |
| Deployment frequency | Throughput | Automation, small batches |
| Lead time for changes | Throughput | Pipeline speed, less handoff |
| Change failure rate | Stability | Testing, review, feature flags |
| Time to restore (MTTR) | Stability | Observability, rollbacks, on-call |

The two columns are a system of checks. Push throughput without watching stability and one of the stability numbers will punish you. That tension is the entire point.

## The vanity trap

Now the part people skip. Every one of these metrics can be gamed, and the moment they're used to evaluate individuals or hit a target, they *will* be:

- Inflate **deployment frequency** by splitting one real change into ten trivial deploys.
- Improve **lead time** by merging huge batches less often so the average looks tidy.
- Suppress **change failure rate** by relabeling incidents as "planned maintenance."
- Improve **MTTR** by closing incidents fast on paper and reopening them quietly.

Goodhart's law is merciless here: when a measure becomes a target, it stops being a good measure. The defense is cultural, not technical. Keep the metrics at the team and system level, never the individual. Use them to ask questions, not to assign blame. "Our lead time doubled this quarter — what changed?" is a useful conversation. "Your lead time is worse than the other team's" is how you teach people to lie to the dashboard.

## Instrument the pipeline, not the people

Collecting DORA metrics well means deriving them from systems you already have — your CI/CD platform and your incident tooling — not from self-reported spreadsheets. A rough sketch of how to compute lead time from deploy and commit data:

```python
from datetime import datetime

def lead_time_hours(deploys):
    """Median hours from first commit to production deploy, per release."""
    times = []
    for d in deploys:
        first_commit = min(c["authored_at"] for c in d["commits"])
        deployed_at = d["deployed_at"]
        delta = (deployed_at - first_commit).total_seconds() / 3600
        times.append(delta)
    times.sort()
    n = len(times)
    return times[n // 2] if n else 0.0
```

Automating collection removes the temptation to fudge inputs and makes the trend trustworthy. And trend is what you want — the absolute number matters far less than the direction over months.

## What I actually do with them

I treat DORA metrics as a diagnostic, not a KPI. When a number moves the wrong way, it's a prompt to investigate the *system*: Is the pipeline slower? Did we add a manual gate? Is on-call burning out? The metrics rarely tell you the answer, but they reliably tell you where to look. That's genuinely valuable and completely different from stapling them to performance reviews.

They also aren't the whole picture. DORA covers delivery performance; it says nothing about whether you're building the right thing, developer experience, or long-term maintainability. Pair them with broader signals like the [SPACE framework for developer productivity](https://blog.michaelsam94.com/developer-productivity-metrics-space/) rather than treating four numbers as the definition of a good engineering org.

Measure the system, watch the trend, resist the urge to rank humans, and DORA metrics earn their place. Turn them into a leaderboard and you'll get exactly the behavior you incentivized — just not the behavior you wanted.

## Resources

- [DORA — DevOps Research and Assessment](https://dora.dev/)
- [Google Cloud — DORA's four keys](https://cloud.google.com/blog/products/devops-sre/using-the-four-keys-to-measure-your-devops-performance)
- [Accelerate (Forsgren, Humble, Kim) — book site](https://itrevolution.com/product/accelerate/)
- [DORA State of DevOps reports](https://dora.dev/research/)
- [Four Keys project (GitHub)](https://github.com/dora-team/fourkeys)
- [Martin Fowler — on measuring productivity](https://martinfowler.com/bliki/CannotMeasureProductivity.html)
