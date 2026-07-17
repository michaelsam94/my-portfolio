---
title: "AI Agents: Policy As Code with Open Policy Agent"
slug: "agent-policy-as-code-opa"
description: "How to enforce agent tool permissions, data access, and spend limits with OPA and Rego — from admission webhooks to runtime gates, with CI tests that catch policy regressions before deploy."
datePublished: "2026-01-22"
dateModified: "2026-01-22"
tags: ["AI", "Agent", "Policy"]
keywords: "Open Policy Agent, OPA, Rego, policy as code, agent authorization, LLM guardrails, Kubernetes admission, agent tool permissions"
faq:
  - q: "Why use OPA instead of hardcoding authorization in the agent runtime?"
    a: "Hardcoded checks drift from product intent and are hard to audit. OPA separates policy from application code so security and platform teams can review, version, and test rules independently. When a new tool or data source ships, you update Rego — not scatter conditionals across five services."
  - q: "Where should OPA sit in an agent stack?"
    a: "At every trust boundary: Kubernetes admission (what pods and secrets agents can mount), API gateways (which endpoints agents call), and inline in the orchestrator before each tool invocation. Defense in depth matters because a bypass at one layer should still fail at the next."
  - q: "How do you test Rego policies before production?"
    a: "Use OPA's `opa test` with table-driven cases: allowed actions, denied actions, and edge cases like cross-tenant access. Wire tests into CI on every policy PR. Pair unit tests with integration tests that send real admission review payloads or HTTP requests through a sidecar."
  - q: "What policies do agent systems need that traditional apps skip?"
    a: "Token budget caps per session, tool allowlists scoped by user role, PII egress rules on retrieval results, model routing constraints (no external API for classified data), and rate limits on autonomous loops that could recurse until spend explodes."
---
An agent with database write access deleted 14,000 rows because nobody wrote down what "read-only analytics" meant in code. The security review had approved the feature in a slide deck. Production had a string comparison on the tool name.

Policy as code with Open Policy Agent (OPA) is how you turn those slide-deck promises into enforceable, testable rules that survive refactors and on-call rotations.

## The gap between intent and enforcement

Agent systems multiply authorization surfaces. A single user turn might trigger: retrieval from a vector store, a SQL query, an HTTP call to a billing API, and a file write to object storage. Each hop needs a decision: allowed or denied, with a reason auditors can read six months later.

Traditional RBAC in your identity provider covers who the user is. It does not cover what the agent is about to do with that identity on step seven of an autonomous loop. Inline `if` statements in Python or TypeScript solve today's demo and become tomorrow's incident when someone adds a tool without updating every branch.

OPA externalizes those decisions. Application code asks a question — "may this agent invoke `stripe.refund` for tenant X with amount Y?" — and Rego returns allow/deny plus optional metadata (which rule fired, suggested alternative). Policies live in Git, get reviewed like code, and run the same in dev, staging, and prod.

## Policy layers worth defining early

Start with four policy families. Teams that skip any one usually backfill under pressure after an audit or outage.

**Tool invocation.** Which tools exist, who can call them, and under what conditions. A support agent might read order history but not issue refunds above $500 without human approval.

**Data egress.** What fields can leave the retrieval boundary. Customer email in a RAG chunk should not flow to an external summarization API if your DPA restricts subprocessors.

**Spend and rate.** Token budgets, max tool calls per session, and circuit breakers on runaway loops. Agents retry aggressively; without caps, a misconfigured prompt can burn a monthly inference budget in an hour.

**Infrastructure placement.** Which models run on-prem vs. cloud, which secrets mount into agent pods, and which network paths are valid. Kubernetes admission with OPA Gatekeeper or Kyverno (which can delegate to OPA) blocks non-compliant deployments before they schedule.

Document each family with an owner. Platform usually owns infrastructure and spend; product owns tool semantics; security owns egress and classification rules.

## Rego that matches real agent payloads

Rego looks unfamiliar until you model one concrete decision. Here is a policy that allows `database.query` only for read-only SQL patterns and denies writes, DDL, and cross-schema access:

```rego
package agent.tools

import rego.v1

default allow := false

allow if {
    input.action == "database.query"
    input.user.role in {"analyst", "support"}
    not contains_write(input.params.sql)
    same_tenant(input.user.tenant_id, input.params.tenant_id)
}

contains_write(sql) if {
    lowered := lower(sql)
    regex.match(`(?i)\b(insert|update|delete|drop|truncate|alter)\b`, lowered)
}

same_tenant(user_tenant, query_tenant) if {
    user_tenant == query_tenant
}
```

Test it with OPA's test runner — this is non-negotiable for production policy:

```rego
# agent_tools_test.rego
package agent.tools

test_analyst_read_allowed if {
    allow with input as {
        "action": "database.query",
        "user": {"role": "analyst", "tenant_id": "t-100"},
        "params": {"sql": "SELECT id FROM orders LIMIT 10", "tenant_id": "t-100"},
    }
}

test_delete_denied if {
    not allow with input as {
        "action": "database.query",
        "user": {"role": "analyst", "tenant_id": "t-100"},
        "params": {"sql": "DELETE FROM orders WHERE id = 1", "tenant_id": "t-100"},
    }
}
```

Run `opa test ./policies/`. If a PR breaks an existing allow case, CI fails before merge.

## Wiring OPA into the agent runtime

Two integration patterns dominate.

**Sidecar or local bundle.** OPA runs beside your orchestrator, policies loaded from a ConfigMap or OCI bundle. Each tool call POSTs to `http://localhost:8181/v1/data/agent/tools/allow` with the input document. Latency is typically sub-millisecond for small policies; budget 2–5 ms p99 including network on localhost.

**Embedded SDK.** Libraries like `@open-policy-agent/opa-wasm` compile Rego to WASM and evaluate in-process. Fewer moving parts, harder to hot-reload policy without redeploying the agent service.

For Kubernetes, add Gatekeeper constraints that reject Deployments where agent containers lack required labels (`data-classification: internal`) or mount disallowed secret volumes. Admission catches misconfiguration; runtime OPA catches dynamic tool requests admission never sees.

```yaml
# ConstraintTemplate excerpt — require tool-policy annotation
apiVersion: templates.gatekeeper.sh/v1
kind: ConstraintTemplate
metadata:
  name: agenttoolpolicy
spec:
  crd:
    spec:
      names:
        kind: AgentToolPolicy
  targets:
    - target: admission.k8s.gatekeeper.sh
      rego: |
        package agenttoolpolicy
        violation[{"msg": msg}] {
          input.review.object.kind == "Deployment"
          not input.review.object.metadata.annotations["agent.tools/policy-version"]
          msg := "agent deployments must declare agent.tools/policy-version"
        }
```

## Deny by default and explain why

Production policies should fail closed. If OPA is unreachable, the agent orchestrator must deny tool execution — not cache last week's allow decision and hope for the best. Pair denials with structured reasons returned to logs and optionally to the user ("Refund tool blocked: amount exceeds role limit").

Avoid logging full prompts or PII in deny traces. Log policy decision IDs, rule names, and hashed tenant identifiers. Security teams need reproducibility; privacy teams need minimization.

## CI/CD and policy lifecycle

Treat policy repos like application repos: CODEOWNERS for security, required reviews, semantic versioning on bundles. When product ships a new tool, the feature PR includes a policy PR that allows it — not a follow-up ticket that lands three sprints later.

Promotion flow that works: dev cluster loads `:main` bundle; staging pins a digest; prod pins the previous digest until staging soaks 48 hours with synthetic agent traffic hitting allow and deny paths. Rollback is repointing the bundle digest, not redeploying agent code.

## Failure modes I have seen in reviews

Policies that key on tool display names instead of stable IDs — rename breaks security. Rego that queries external HTTP during evaluation — adds latency and availability coupling; prefetch data into the input document instead. One giant policy file with no tests — nobody dares edit it. Allow lists copied from staging that include debug tools left enabled in prod.

Another subtle one: policies written for synchronous chat agents applied unchanged to batch jobs with 10,000 iterations. Rate and spend rules need different thresholds per execution mode.

## Operating policy as code day two

Dashboard OPA decision metrics: allow rate, deny rate by rule, evaluation latency, bundle load failures. Alert on deny spikes — often a deploy changed input shape, not an attack. Run quarterly game days: attempt cross-tenant retrieval, oversized refunds, and secret exfiltration paths; verify denials fire and logs suffice for an audit sample.

When regulators or enterprise customers ask "how do you control what the AI can access," point them at the policy repo, test suite, and admission audit trail. That answer beats a PDF architecture diagram every time.

## Bundling policies for multi-team ownership

Large orgs split Rego into packages: `agent.tools`, `agent.egress`, `agent.spend`, `infra.k8s`. Each package has its own test file and CODEOWNERS entry. The orchestrator sends one input document; OPA evaluates all packages and merges decisions — deny wins over allow.

Version bundles with OCI artifacts (`opa build -b ./policies -o bundle.tar.gz`) and sign them with cosign. Admission controllers and sidecars pull by digest. When security revokes a compromised rule, rotate the digest globally in under five minutes instead of redeploying twelve microservices.

For local development, run `opa run --server` with `--watch` so prompt engineers see deny reasons in real time while testing new tools against draft policy — faster feedback than discovering blocks in staging CI alone.

## Resources

- [Open Policy Agent documentation](https://www.openpolicyagent.org/docs/latest/)
- [Rego language reference](https://www.openpolicyagent.org/docs/latest/policy-language/)
- [OPA Gatekeeper for Kubernetes](https://open-policy-agent.github.io/gatekeeper/website/docs/)
- [Agent policy patterns on Kubernetes (CNCF blog)](https://www.cncf.io/blog/2023/08/14/opentelemetry-and-opa-for-cloud-native-security/)
- [Styra DAS policy authoring guide](https://docs.styra.com/das/policy-authoring)
