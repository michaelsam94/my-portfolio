---
title: "Blue-Green Deployments"
slug: "ci-cd-deployment-strategies-blue-green"
description: "Blue-green deployments run two identical environments and switch traffic instantly. Learn setup, database migration challenges, smoke testing, and rollback procedures for zero-downtime releases."
datePublished: "2025-02-07"
dateModified: "2025-02-07"
tags: ["DevOps", "CI/CD", "Infrastructure", "Deployment"]
keywords: "blue green deployment, zero downtime deployment, traffic switching, deployment strategy, blue green rollback, production deployment"
faq:
  - q: "What is blue-green deployment?"
    a: "Blue-green maintains two identical production environments — blue (current) and green (new). Deploy the new version to green, test it, then switch traffic from blue to green in one operation. Rollback is switching back to blue. Users experience zero downtime during the switch if green is healthy."
  - q: "How is blue-green different from rolling deployment?"
    a: "Rolling deployment replaces instances gradually — old and new versions run simultaneously during rollout. Blue-green switches all traffic at once between two full environments. Blue-green gives instant rollback but requires double infrastructure. Rolling is cheaper but rollback is slower."
  - q: "How do database migrations work with blue-green?"
    a: "Database is the hard part. Use expand-contract migrations: deploy schema changes compatible with both versions first, switch traffic, then remove old schema. Never deploy breaking schema changes simultaneously with the traffic switch — the old version (blue) must still work until switch completes."
---

Deploying at 2 PM on a Tuesday shouldn't require a war room. Blue-green deployment keeps two production environments — one serving traffic, one waiting — and switches between them in seconds. If green is broken, switch back to blue before users notice. The concept is simple; the engineering is in database compatibility, health checks, and knowing when double infrastructure cost is worth instant rollback.

## How it works

```
                    ┌─────────┐
  Load Balancer ───→│  BLUE   │ ← v1.2 (current, serving traffic)
                    └─────────┘

                    ┌─────────┐
                    │  GREEN  │ ← v1.3 (deployed, tested, idle)
                    └─────────┘

        ─── switch traffic ───

                    ┌─────────┐
                    │  BLUE   │ ← v1.2 (idle, kept for rollback)
                    └─────────┘

                    ┌─────────┐
  Load Balancer ───→│  GREEN  │ ← v1.3 (now serving traffic)
                    └─────────┘
```

## Kubernetes implementation

Two deployments, one service with selector switch:

```yaml
# Blue deployment (current)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp-blue
  labels:
    app: myapp
    slot: blue
spec:
  replicas: 3
  selector:
    matchLabels:
      app: myapp
      slot: blue
  template:
    metadata:
      labels:
        app: myapp
        slot: blue
    spec:
      containers:
        - name: app
          image: registry/myapp:v1.2.0

---
# Green deployment (new)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp-green
  labels:
    app: myapp
    slot: green
spec:
  replicas: 3
  selector:
    matchLabels:
      app: myapp
      slot: green
  template:
    metadata:
      labels:
        app: myapp
        slot: green
    spec:
      containers:
        - name: app
          image: registry/myapp:v1.3.0
```

Traffic switch — update service selector:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: myapp
spec:
  selector:
    app: myapp
    slot: green  # was: blue
  ports:
    - port: 80
      targetPort: 8080
```

Or use an Ingress/ALB weighted target group:

```bash
# AWS ALB — shift 100% to green target group
aws elbv2 modify-listener \
  --listener-arn $LISTENER_ARN \
  --default-actions Type=forward,TargetGroupArn=$GREEN_TG_ARN
```

## Pre-switch validation

Before switching traffic, verify green:

```bash
# Smoke tests against green (internal endpoint)
curl -f https://green.internal.myapp.com/health
curl -f https://green.internal.myapp.com/api/v1/status

# Run integration test suite against green
pytest tests/integration/ --base-url=https://green.internal.myapp.com
```

Automate this in CI — deploy to green is gated on smoke test pass; traffic switch requires manual approval or automated canary metrics.

## Database migration strategy

Blue and green share the database. Migrations must be backward-compatible:

**Phase 1 — Expand (before deploy):**
```sql
ALTER TABLE orders ADD COLUMN status_v2 VARCHAR(20);
-- Old code ignores status_v2; new code writes both columns
```

**Phase 2 — Switch traffic to green**

**Phase 3 — Contract (after blue decommissioned):**
```sql
ALTER TABLE orders DROP COLUMN status;
ALTER TABLE orders RENAME COLUMN status_v2 TO status;
```

Never drop columns or rename tables in the same deploy as traffic switch.

## Rollback procedure

```bash
# Instant rollback — switch selector back to blue
kubectl patch service myapp -p '{"spec":{"selector":{"slot":"blue"}}}'

# Verify
kubectl get endpoints myapp
curl -f https://myapp.com/health
```

Rollback takes seconds if blue is still running. Keep blue alive for at least 24 hours after switch.

## Blue-green vs other strategies

| Strategy | Downtime | Rollback speed | Infra cost | Complexity |
|----------|----------|---------------|------------|------------|
| Blue-green | Zero | Seconds | 2× | Medium |
| Rolling | Zero | Minutes | 1× | Low |
| Canary | Zero | Seconds | 1×+ | High |
| Recreate | Yes | N/A | 1× | Lowest |

Blue-green fits when rollback speed matters more than infrastructure cost — payment systems, launch events, high-traffic periods.

## Cleanup

After green is stable (24–48 hours):
1. Scale blue to zero (or delete)
2. Rename green → blue for next cycle
3. Deploy next version to new green

Some teams automate the rename; others keep fixed blue/green slots permanently.

## Common failures

- **Switching before smoke tests pass** — users hit broken green
- **Breaking DB migration** — blue crashes after switch because schema changed
- **Session stickiness** — users on blue sessions break after switch (use shared session store)
- **Decommissioning blue too fast** — no rollback option when issue found 6 hours later

Pair with [artifact promotion](https://blog.michaelsam94.com/ci-cd-artifact-management/) — green deploys the exact artifact that passed staging.

Keep blue environment warm but scaled to minimum for 24–48 hours after switch — rollback in seconds beats explaining to customers why rollback takes twenty minutes.

## Smoke test gate before switch

Automate smoke tests against green before traffic switch:

```bash
# After deploy to green, before LB switch
curl -f https://green.internal/health
curl -f https://green.internal/api/v1/readiness
npm run e2e-smoke -- --baseUrl=https://green.internal
```

Failed smoke on green aborts switch — blue continues serving. Document abort procedure in runbook with LB API commands to revert.

## Common production mistakes

Teams get deployment strategies blue green wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

CI/CD for deployment strategies blue green breaks merges when pipeline secrets rotate without updating OIDC trust, cache keys ignore lockfile changes, and deployment gates check build success but not smoke tests.

## Debugging and triage workflow

When deployment strategies blue green misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [Martin Fowler — BlueGreenDeployment](https://martinfowler.com/bliki/BlueGreenDeployment.html)
- [AWS blue-green deployments](https://docs.aws.amazon.com/whitepapers/latest/overview-deployment-options/bluegreen-deployments.html)
- [Kubernetes deployment strategies](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/#strategy)
- [Expand-contract migration pattern](https://www.prisma.io/dataguide/types/relational/expand-and-contract-pattern)
- [LaunchDarkly — deployment strategies compared](https://launchdarkly.com/blog/blue-green-deployment/)
