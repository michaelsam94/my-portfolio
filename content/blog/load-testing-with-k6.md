---
title: "Load Testing APIs with k6"
slug: "load-testing-with-k6"
description: "Load testing APIs with k6: scripting in JavaScript, choosing the right test type, reading latency percentiles honestly, and wiring pass/fail thresholds into CI."
datePublished: "2026-01-26"
dateModified: "2026-07-17"
tags:
keywords: "k6 load testing, performance testing, stress test, throughput, latency percentiles, load test CI"
faq:
  - q: "What is k6 and what is it used for?"
    a: "k6 is an open-source load-testing tool from Grafana Labs where you write tests as JavaScript but the engine runs in Go for high performance. It's used to simulate many concurrent virtual users hitting an API, measuring throughput, latency percentiles, and error rates so you can find performance limits and regressions before real users do."
  - q: "What's the difference between a load test, a stress test, and a soak test?"
    a: "A load test verifies behavior at expected peak traffic. A stress test pushes beyond capacity to find the breaking point and observe how the system fails. A soak test runs a moderate load for hours to expose slow problems like memory leaks and connection exhaustion. Each answers a different question, and k6 supports all three via its executors."
  - q: "Why look at p95/p99 latency instead of the average?"
    a: "Because averages hide the pain. A 50 ms average can conceal that 1% of requests take 3 seconds, and that 1% is often your most active users making the most calls. Percentiles (p95, p99) tell you what the slowest slice of users actually experiences, which is what determines whether your service feels fast or broken."
---
Averages lie about performance, and the first time a "fast" service falls over in production you learn it the expensive way. Load testing APIs with k6 is how you find the truth before your users do: you write a script that simulates realistic concurrent traffic, run it against your API, and measure throughput, error rate, and — the part that actually matters — latency percentiles. k6 is Grafana Labs' open-source tool where tests are JavaScript but the engine is Go, so a single machine can generate serious load without becoming the bottleneck itself.

I reach for k6 both to answer "will this survive Black Friday?" and to catch the quieter failure: a change that adds 80 ms to p99 and would've slipped through unnoticed. Here's how I use it.

## Scripting a test

A k6 test is a JavaScript module with a default function that represents one virtual user's behavior, plus an exported `options` object that shapes the load. The basics:

```javascript
import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  stages: [
    { duration: "1m", target: 50 },   // ramp to 50 VUs
    { duration: "3m", target: 50 },   // hold
    { duration: "1m", target: 0 },    // ramp down
  ],
  thresholds: {
    http_req_duration: ["p(95)<400", "p(99)<800"],
    http_req_failed: ["rate<0.01"],
  },
};

export default function () {
  const res = http.get("https://api.example.com/products?limit=20");
  check(res, {
    "status is 200": (r) => r.status === 200,
    "body is non-empty": (r) => r.body.length > 0,
  });
  sleep(1);   // model think-time between requests
}
```

Two parts do the heavy lifting. `stages` describes the load profile over time — ramp up, hold, ramp down — which is far more realistic than slamming full load instantly. And `thresholds` turn the test into a pass/fail check: if p95 exceeds 400 ms or the error rate tops 1%, k6 exits non-zero. That exit code is what makes k6 usable as a gate rather than just a report.

The `sleep(1)` matters more than it looks. Real users pause between actions; without think-time you're modeling a denial-of-service attack, not traffic, and you'll get pessimistic numbers that don't reflect reality.

## Pick the test type deliberately

"Load testing" is an umbrella. The four shapes I actually run answer different questions:

| Test type | Question it answers | Profile |
| --- | --- | --- |
| Smoke | Does it work under minimal load? | 1–2 VUs, short |
| Load | Does it hold up at expected peak? | Ramp to peak, hold |
| Stress | Where does it break, and how? | Ramp past capacity |
| Soak | Does it degrade over hours? | Moderate load, long |

Most teams only run load tests and skip stress and soak, which is where the interesting failures hide. Stress tests tell you your *breaking point* and — crucially — *how* it breaks: does it shed load gracefully, or does it fall into a death spiral? Soak tests catch the slow killers: memory leaks, connection-pool exhaustion, disks filling with logs. A service can pass a 5-minute load test beautifully and die after 6 hours. Ask me how I know.

## Reading the results honestly

The single most important discipline is to ignore the average and read percentiles. k6 reports `avg`, `p(90)`, `p(95)`, `p(99)`, and `max` for request duration. The average is nearly useless — it's dragged around by outliers in both directions and tells you nothing about tail behavior.

What I actually look at:

- **p95 and p99** — the experience of your slowest users. Your SLOs should be written in these terms, and your k6 thresholds should mirror your SLOs so a test failure means an SLO would be breached.
- **Error rate** — anything above your budget invalidates the latency numbers, because failed requests are often fast for the wrong reasons.
- **The shape over time** — latency that climbs steadily during a hold phase signals resource exhaustion or a leak, even if it never crosses the threshold within the test window.
- **Throughput vs. latency together** — high requests-per-second means nothing if p99 is 4 seconds. Read them as a pair.

Tail latency is also where downstream protections show their value or their absence. A stress test is the honest way to see whether your [rate limiting and backpressure](https://blog.michaelsam94.com/rate-limiting-backpressure/) actually kick in, or whether the service just accepts more than it can handle until it collapses.

## Wiring it into CI

A load test that runs once before launch is a snapshot; a load test in CI is a ratchet that prevents regressions. Because k6 exits non-zero when thresholds fail, gating a pipeline is a few lines:

```bash
k6 run --quiet --out json=results.json load-test.js
# non-zero exit from a breached threshold fails the pipeline automatically
```

I don't run a full-scale stress test on every commit — that's slow and expensive. Instead I run a scaled-down smoke-and-load test against a staging environment on each merge to catch obvious regressions, and reserve full stress and soak runs for pre-release or on a schedule. Keeping the per-commit version fast is what keeps it inside a [fast CI/CD pipeline](https://blog.michaelsam94.com/fast-cicd-pipelines/) instead of becoming the reason nobody wants to merge.

One caution: performance tests are noisy. Shared CI runners have variable neighbors, so absolute numbers drift. Set thresholds with headroom, and treat sudden *relative* jumps ("p99 doubled versus last week") as the real signal rather than chasing every few-millisecond wobble.

## The senior take

k6's real value isn't the pretty summary at the end of a run — it's making performance a thing you *test* rather than *hope for*. Encode your SLOs as thresholds, run a cheap version continuously and an expensive version deliberately, and always read the tail. The teams that get burned are the ones who load-tested the happy path at average latency and declared victory, then met p99 for the first time in production during their biggest traffic day. Test the way your worst-off users actually experience the system, and the launch is boring — which, for load testing, is the entire goal.

## Resources

- [k6 — official documentation](https://grafana.com/docs/k6/latest/)
- [k6 (GitHub)](https://github.com/grafana/k6)
- [k6 — test types explained](https://grafana.com/docs/k6/latest/testing-guides/test-types/)
- [k6 — thresholds reference](https://grafana.com/docs/k6/latest/using-k6/thresholds/)
- [Google SRE Book — Service Level Objectives](https://sre.google/sre-book/service-level-objectives/)
- [Brendan Gregg — latency and percentiles](https://www.brendangregg.com/blog/2018-02-09/kpis-not-averages.html)
