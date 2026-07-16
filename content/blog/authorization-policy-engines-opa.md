---
title: "Policy as Code with OPA"
slug: "authorization-policy-engines-opa"
description: "Open Policy Agent evaluates Rego policies against JSON input for authorization, admission control, and compliance. Deploy OPA as a sidecar, embed in services, or use Gatekeeper on Kubernetes."
datePublished: "2024-09-25"
dateModified: "2024-09-25"
tags: ["Security", "Backend", "OPA", "Authorization"]
keywords: "Open Policy Agent, OPA Rego, policy as code, authorization engine, OPA sidecar, Gatekeeper Kubernetes"
faq:
  - q: "What is OPA used for?"
    a: "OPA (Open Policy Agent) is a general-purpose policy engine. You send JSON input (user, action, resource) and OPA evaluates Rego policies to return allow/deny decisions. Common uses: API authorization, Kubernetes admission control via Gatekeeper, CI pipeline compliance checks, and Terraform plan validation."
  - q: "Should OPA replace my application's authorization logic?"
    a: "OPA centralizes policy that changes often or spans services — role matrices, attribute-based rules, compliance constraints. Keep authentication (who are you) in your auth layer. Move authorization (what can you do) to OPA when multiple services share rules or non-engineers need to audit policy without reading application code."
  - q: "How do I test Rego policies?"
    a: "Use OPA's built-in test runner: opa test -v policies/. Write test_rego files with mock input and assert allow/deny outcomes. Run tests in CI on every policy change — Rego bugs are authorization bypasses, not cosmetic failures."
---

Hardcoded `if (user.role === 'admin')` checks spread across twelve microservices diverge within weeks. One team adds a tenant check, another forgets. Security audits require reading every handler. Open Policy Agent externalizes authorization into versioned Rego policies evaluated against structured JSON input — the same engine whether you're gating a REST endpoint, rejecting a non-compliant Kubernetes manifest, or blocking a Terraform apply.

## OPA decision flow

```
Service  →  POST /v1/data/authz/allow  →  OPA
           { "input": { user, action, resource } }
                                              ↓
                                         Rego evaluation
                                              ↓
Service  ←  { "result": true/false }     ←  OPA
```

The service asks a question; OPA answers. Policy lives outside the service binary.

## Basic Rego policy

```rego
# policies/authz.rego
package authz

import future.keywords.if
import future.keywords.in

default allow := false

allow if {
    input.user.role == "admin"
}

allow if {
    input.action == "read"
    input.resource.owner == input.user.id
}

allow if {
    input.action in {"read", "update"}
    input.resource.tenant == input.user.tenant
    input.user.role == "editor"
}
```

Query the decision:

```bash
curl -s localhost:8181/v1/data/authz/allow -d '{
  "input": {
    "user": {"id": "u1", "role": "editor", "tenant": "acme"},
    "action": "update",
    "resource": {"id": "doc1", "tenant": "acme", "owner": "u2"}
  }
}' | jq .result
# true
```

## Embedding in a Node service

```typescript
import fetch from 'node-fetch';

async function isAllowed(user: User, action: string, resource: Resource): Promise<boolean> {
  const resp = await fetch('http://localhost:8181/v1/data/authz/allow', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ input: { user, action, resource } }),
  });
  const { result } = await resp.json();
  return result === true;
}

// Express middleware
app.use('/api/documents/:id', async (req, res, next) => {
  const resource = await docStore.get(req.params.id);
  const allowed = await isAllowed(req.user, req.method.toLowerCase(), resource);
  if (!allowed) return res.status(403).json({ error: 'forbidden' });
  next();
});
```

Run OPA as a sidecar in Kubernetes or a shared cluster service — sidecars add ~1ms latency on localhost.

## Policy testing

```rego
# policies/authz_test.rego
package authz

test_admin_can_delete if {
    allow with input as {
        "user": {"role": "admin"},
        "action": "delete",
        "resource": {"id": "x"}
    }
}

test_viewer_cannot_delete if {
    not allow with input as {
        "user": {"role": "viewer", "tenant": "acme"},
        "action": "delete",
        "resource": {"tenant": "acme"}
    }
}
```

```bash
opa test -v policies/
```

Run this in CI. Policy regressions are security incidents.

## Kubernetes with Gatekeeper

Gatekeeper is OPA for Kubernetes admission:

```yaml
apiVersion: constraints.gatekeeper.sh/v1beta1
kind: K8sRequiredLabels
metadata:
  name: require-team-label
spec:
  match:
    kinds:
      - apiGroups: [""]
        kinds: ["Pod"]
  parameters:
    labels: ["team", "cost-center"]
```

Rego templates define reusable constraint logic. I've seen teams block `latest` tags and unprivileged root containers this way before pods ever schedule.

## OPA vs in-app RBAC

| Factor | In-app RBAC | OPA |
|--------|------------|-----|
| Change velocity | Requires deploy | Policy bundle update |
| Auditability | Scattered code | Central repo |
| Latency | Zero | Network hop |
| Complexity | Low for simple apps | Worth it at scale |

Start with in-app RBAC for MVPs. Move to OPA when you have three-plus services sharing authorization rules or compliance requires policy review separate from code review.

## Bundle deployment

Package policies as OPA bundles served from S3 or Git:

```bash
opa build -b policies/ -o bundle.tar.gz
opa run --server --set bundles.authz.resource=bundle.tar.gz
```

Services poll for bundle updates — policy changes roll out without redeploying apps.

## Rego policy testing

Test policies before deployment with OPA's built-in test framework:

```rego
# policies/authz/test.rego
package authz.test

import data.authz.allow

test_admin_can_delete {
    allow with input as {
        "user": {"role": "admin"},
        "action": "delete",
        "resource": "document"
    }
}

test_viewer_cannot_delete {
    not allow with input as {
        "user": {"role": "viewer"},
        "action": "delete",
        "resource": "document"
    }
}
```

```bash
opa test policies/ -v
# PASS: 2/2
```

Run `opa test` in CI on every policy PR — policy bugs are authorization bugs.

## Partial evaluation for performance

OPA compiles policies ahead of time for repeated queries with static inputs:

```bash
# Compile policy with known input shape
opa eval --partial --data policies/ \
  --input '{"user": {"role": "admin"}}' \
  'data.authz.allow'
```

Partial evaluation reduces runtime from milliseconds to microseconds for high-QPS services. Pre-compile policies at startup with known user attributes that change infrequently (role, department).

## OPA decision logging

Log every authorization decision for audit and debugging:

```yaml
# opa config
decision_logs:
  service: authz
  reporting:
    min_delay_seconds: 10
    max_delay_seconds: 20
  console: true  # for development
```

```json
{
  "decision_id": "abc123",
  "path": "authz/allow",
  "input": {"user": {"role": "viewer"}, "action": "delete"},
  "result": false,
  "timestamp": "2024-12-27T10:00:00Z"
}
```

Ship decision logs to your SIEM — unauthorized access attempts, policy evaluation errors, and latency outliers all visible in one stream.

## Failure modes

- **OPA unavailable** — fail open vs fail closed must be explicit policy
- **Policy not tested** — authorization bug deployed to production
- **High latency on every request** — no partial evaluation or caching
- **Policy sprawl** — 500 Rego files with no ownership model
- **Bundle not signed** — tampered policy bundle deployed without detection

## Production checklist

- `opa test` in CI on every policy change
- Fail-closed default when OPA unavailable
- Decision logging enabled and shipped to SIEM
- Partial evaluation for high-QPS paths
- Policy bundle signed and verified on deployment
- Policy ownership documented per domain (authz, k8s, terraform)

Cache OPA decisions for 60 seconds on read-heavy paths — policy evaluation per request adds 5-15ms that compounds at gateway scale.

## Common production mistakes

Teams get policy engines opa wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of policy engines opa fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Resources

- [Open Policy Agent documentation](https://www.openpolicyagent.org/docs/latest/)
- [Rego language reference](https://www.openpolicyagent.org/docs/latest/policy-language/)
- [OPA REST API](https://www.openpolicyagent.org/docs/latest/rest-api/)
- [Gatekeeper for Kubernetes](https://open-policy-agent.github.io/gatekeeper/website/docs/)
- [OPA policy testing guide](https://www.openpolicyagent.org/docs/latest/policy-testing/)
