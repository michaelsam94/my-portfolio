---
title: "IAM Policy Simulator for Agent Tool Permissions"
slug: "agent-iam-policy-simulator"
description: "Simulate IAM policies before agent tool deployments—model least-privilege for LLM-invoked AWS actions, catch Allow gaps in CI, and explain denials to operators without production trial-and-error."
datePublished: "2026-01-16"
dateModified: "2026-01-16"
tags: ["AI Agents", "IAM", "Security", "AWS"]
keywords: "IAM policy simulator, agent tool permissions, AWS IAM simulate, least privilege, LLM tool calling, policy as code"
faq:
  - q: "Why simulate IAM policies instead of testing in production?"
    a: "Agent tools invoke real infrastructure—S3 reads, Lambda invokes, Secrets Manager fetches. Production trial-and-error creates audit noise, can trigger guardrails, and teaches the model wrong retry patterns. Simulation evaluates Allow/Deny decisions against hypothetical requests without side effects."
  - q: "Can the AWS IAM Policy Simulator cover every agent tool path?"
    a: "It evaluates identity-based and resource-based policies for a given principal, action, and resource ARN. It does not simulate SCPs, permission boundaries, session policies, or VPC endpoint policies in all combinations unless you layer those checks separately. Treat simulator results as necessary but not sufficient."
  - q: "How do you keep simulated policies in sync with deployed agents?"
    a: "Generate the agent execution role policy from the same Terraform or CDK module CI deploys. Run simulation tests against a manifest of every tool action the agent registry exposes. Fail CI when a new tool is registered but no simulation case exists."
  - q: "What should operators see when an agent tool hits AccessDenied?"
    a: "Return a structured denial with simulated evaluation summary—not raw AWS XML. Include which statement blocked, suggested least-privilege fix, and a link to the policy PR. Agents should surface 'permission denied on s3:GetObject for arn:...' not hallucinate success."
---

The agent's new "analyze CloudTrail logs" tool shipped Friday. By Monday it had **AccessDenied** on half its invocations — not because the policy was missing, but because a resource-level `Deny` on the logging bucket conflicted with an identity `Allow` on `s3:*`. The on-call engineer fixed it by attaching `AdministratorAccess` to the execution role "temporarily." That is the failure mode **IAM policy simulation** exists to prevent: guessing in production instead of proving decisions beforehand.

Agents that call cloud APIs are IAM clients. Every tool definition — read object, start Step Function, query Athena — maps to an AWS action and resource ARN pattern. Simulation lets you ask "if this role calls this action on this resource, what happens?" before the LLM ever sees the tool.

## Agent IAM model

Separate concerns cleanly:

| Layer | Owns | Example |
|-------|------|---------|
| Agent runtime role | What tools may execute | `agent-runner-prod` |
| Tool registry | Action catalog + input schemas | `s3_read_object`, `lambda_invoke` |
| Per-tenant scope | Resource ARN prefixes | `arn:aws:s3:::tenant-acme-*` |
| Session policy (optional) | Ephemeral narrowing | MCP session bound to one bucket |

The execution role should be **narrower than the human who deployed the agent**. Humans have console access; agents need programmatic least privilege with no wildcards on `Resource: "*"` unless the action requires it (e.g., `sts:GetCallerIdentity`).

## Policy manifest for tools

Derive simulation cases from the tool registry — one case per (action, resource pattern, condition) tuple:

```yaml
# policies/agent-tools/manifest.yaml
execution_role: arn:aws:iam::123456789012:role/agent-runner-prod

tools:
  s3_read_object:
    actions:
      - s3:GetObject
      - s3:GetObjectVersion
    resources:
      - "arn:aws:s3:::corp-knowledge/*"
      - "arn:aws:s3:::corp-knowledge"
    conditions:
      StringEquals:
        s3:ExistingObjectTag/Classification: ["public", "internal"]

  lambda_invoke_analyzer:
    actions:
      - lambda:InvokeFunction
    resources:
      - "arn:aws:lambda:us-east-1:123456789012:function:log-analyzer-*"

  secrets_fetch:
    actions:
      - secretsmanager:GetSecretValue
    resources:
      - "arn:aws:secretsmanager:us-east-1:123456789012:secret:agent/*"
```

Each tool maps to IAM actions — not English descriptions. When product adds a tool, they add simulation cases; CI blocks merge otherwise.

## AWS IAM SimulatePrincipalPolicy

The native API evaluates policies attached to a principal:

```python
# scripts/simulate_agent_policies.py
import boto3
import yaml
from dataclasses import dataclass

iam = boto3.client("iam")

@dataclass
class SimCase:
    action: str
    resource: str
    context: dict | None = None
    expect: str  # "allowed" | "denied"

def simulate(role_arn: str, cases: list[SimCase]) -> list[dict]:
    policy_source_arn = role_arn
    results = []

    # Batch in groups of 100 (API limit)
    for i in range(0, len(cases), 100):
        batch = cases[i : i + 100]
        response = iam.simulate_principal_policy(
            PolicySourceArn=policy_source_arn,
            ActionNames=[c.action for c in batch],
            ResourceArns=[c.resource for c in batch],
            ContextEntries=flatten_context(batch),
        )
        for case, eval_result in zip(batch, response["EvaluationResults"]):
            decision = eval_result["EvalDecision"]  # allowed, explicitDeny, implicitDeny
            passed = (decision == "allowed") == (case.expect == "allowed")
            results.append({
                "action": case.action,
                "resource": case.resource,
                "decision": decision,
                "expect": case.expect,
                "passed": passed,
                "matched_statements": eval_result.get("MatchedStatements", []),
            })
    return results

def flatten_context(cases: list[SimCase]) -> list[dict]:
    entries = []
    for idx, case in enumerate(cases):
        if not case.context:
            continue
        for key, value in case.context.items():
            entries.append({
                "ContextKeyName": key,
                "ContextKeyType": "string",
                "ContextKeyValues": [str(value)],
            })
    return entries
```

Run on every Terraform apply plan in CI against the **planned** policy document using `simulate_custom_policy` when the role does not exist yet:

```python
def simulate_custom_policy(policy_doc: dict, cases: list[SimCase]) -> list[dict]:
    response = iam.simulate_custom_policy(
        PolicyInputList=[json.dumps(policy_doc)],
        ActionNames=[c.action for c in cases],
        ResourceArns=[c.resource for c in cases],
    )
    return parse_results(response, cases)
```

## Positive and negative test cases

Simulation must prove both **allowed paths work** and **forbidden paths deny**:

```yaml
# policies/agent-tools/simulation-cases.yaml
cases:
  - name: read_public_knowledge_object
    action: s3:GetObject
    resource: arn:aws:s3:::corp-knowledge/runbooks/outage.md
    context:
      s3:ExistingObjectTag/Classification: internal
    expect: allowed

  - name: deny_other_tenant_bucket
    action: s3:GetObject
    resource: arn:aws:s3:::tenant-other-private/data.csv
    expect: denied

  - name: deny_delete_on_read_only_tool
    action: s3:DeleteObject
    resource: arn:aws:s3:::corp-knowledge/runbooks/outage.md
    expect: denied

  - name: invoke_analyzer_in_scope
    action: lambda:InvokeFunction
    resource: arn:aws:lambda:us-east-1:123456789012:function:log-analyzer-prod
    expect: allowed

  - name: invoke_unrelated_lambda
    action: lambda:InvokeFunction
    resource: arn:aws:lambda:us-east-1:123456789012:function:payment-processor
    expect: denied
```

Negative cases catch overly broad `Allow` statements — the silent security debt of most agent rollouts.

## CI gate integration

```yaml
# .github/workflows/iam-simulate.yml
name: IAM Policy Simulation
on:
  pull_request:
    paths:
      - "infra/iam/**"
      - "policies/agent-tools/**"

jobs:
  simulate:
    runs-on: ubuntu-latest
    permissions:
      id-token: write
      contents: read
    steps:
      - uses: actions/checkout@v4
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::123456789012:role/ci-iam-simulator
      - run: pip install boto3 pyyaml
      - run: python scripts/simulate_agent_policies.py --manifest policies/agent-tools/manifest.yaml --cases policies/agent-tools/simulation-cases.yaml --fail-fast
```

The CI role needs only `iam:SimulatePrincipalPolicy` and `iam:SimulateCustomPolicy` on the policies under test — not admin access.

## Explaining denials to operators and agents

When runtime hits `AccessDenied`, wrap AWS errors with simulation output captured at deploy time or re-run live:

```typescript
// agent-runtime/tool-executor.ts
import { IAMClient, SimulatePrincipalPolicyCommand } from "@aws-sdk/client-iam";

export async function explainDenial(
  roleArn: string,
  action: string,
  resource: string
): Promise<string> {
  const iam = new IAMClient({});
  const result = await iam.send(
    new SimulatePrincipalPolicyCommand({
      PolicySourceArn: roleArn,
      ActionNames: [action],
      ResourceArns: [resource],
    })
  );
  const evalResult = result.EvaluationResults?.[0];
  const decision = evalResult?.EvalDecision ?? "unknown";
  const statements = evalResult?.MatchedStatements?.map((s) => s.SourcePolicyId) ?? [];

  return [
    `Decision: ${decision}`,
    `Action: ${action}`,
    `Resource: ${resource}`,
    `Matched policies: ${statements.join(", ") || "none"}`,
    decision !== "allowed"
      ? "Suggested fix: add least-privilege Allow or adjust resource ARN scope in policies/agent-tools/manifest.yaml"
      : "",
  ].join("\n");
}
```

Feed this string to the agent as tool error context — models recover better from structured denial than from opaque exceptions. **Never** tell the agent to "try another role" or escalate permissions autonomously.

## SCPs, boundaries, and permission caps

Organization SCPs can deny even when role simulation says Allow. Maintain a second check for high-risk actions:

```python
DENY_SCP_ACTIONS = {"iam:*", "organizations:*", "account:*"}

def scp_risk_check(action: str) -> bool:
    for pattern in DENY_SCP_ACTIONS:
        if fnmatch(action, pattern):
            return True
    return False
```

Document that simulation reflects **effective identity policy** on the role, not full org effective access. For regulated agents, add a manual approval step when simulation introduces new actions on production resources.

## Session policies for multi-tenant agents

When one runtime serves multiple tenants, attach a **session policy** at assume-role time:

```python
import json
import boto3

def assume_tenant_role(tenant_id: str) -> dict:
    sts = boto3.client("sts")
    session_policy = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Action": ["s3:GetObject"],
            "Resource": [f"arn:aws:s3:::tenant-{tenant_id}-*/*"],
        }],
    }
    return sts.assume_role(
        RoleArn="arn:aws:iam::123456789012:role/agent-runner-prod",
        RoleSessionName=f"agent-{tenant_id}",
        Policy=json.dumps(session_policy),
    )["Credentials"]
```

Simulate the **intersection** of role policy and session policy — AWS evaluates both. Add cases per tenant prefix to catch cross-tenant leakage.

## Policy generation from tool registry

Reduce hand-written JSON drift by generating policies:

```python
def manifest_to_policy(manifest: dict) -> dict:
    statements = []
    for tool_name, tool in manifest["tools"].items():
        statements.append({
            "Sid": f"AgentTool_{tool_name}",
            "Effect": "Allow",
            "Action": tool["actions"],
            "Resource": tool["resources"],
            **({"Condition": tool["conditions"]} if "conditions" in tool else {}),
        })
    return {"Version": "2012-10-17", "Statement": statements}
```

Simulation tests run against generated output — single source of truth. Product defines tools; security reviews simulation cases; Terraform deploys generated policy.

## Audit trail and change management

Log every simulation run in CI with git SHA and case results. In production, log tool invocations with `(action, resource, decision, role_session)` — correlate with CloudTrail `SimulatePrincipalPolicy` if operators run ad-hoc checks.

When denial rates spike after deploy:

1. Diff simulation case failures in CI artifact
2. Compare deployed policy version tag to manifest version
3. Re-run simulation for failing `(action, resource)` pairs
4. Roll back role policy before widening permissions

## Common mistakes

**Simulating only Allow paths.** Negative cases find `s3:*` statements you forgot about.

**Using `Resource: "*"` for convenience.** Simulation passes; blast radius is unlimited. Require ARN patterns in manifest review.

**Ignoring condition keys.** Tag-based access fails in production when objects lack tags; simulation must include `ContextEntries`.

**Stale cases after tool rename.** Registry version bumps without case updates → CI green, production deny.

**Trusting simulator for KMS grants and ABAC edge cases.** Extend with custom policy unit tests for key policies and VPC endpoint restrictions.

## The takeaway

IAM policy simulation turns agent tool permissions into tested, explainable code. Derive simulation cases from the tool registry, run positive and negative tests in CI with `SimulatePrincipalPolicy` and `SimulateCustomPolicy`, generate policies from manifests, and return structured denial explanations at runtime. Agents operating cloud infrastructure need least privilege that is proven before deploy — not discovered by attaching AdministratorAccess under incident pressure.

## Resources

- [AWS — iam:SimulatePrincipalPolicy API reference](https://docs.aws.amazon.com/IAM/latest/APIReference/API_SimulatePrincipalPolicy.html)
- [AWS — iam:SimulateCustomPolicy API reference](https://docs.aws.amazon.com/IAM/latest/APIReference/API_SimulateCustomPolicy.html)
- [AWS IAM Policy Simulator console](https://policies.aws.amazon.com/)
- [Terraform — aws_iam_policy_document data source](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/iam_policy_document)
- [AWS Well-Architected — Security pillar: grant least privilege](https://docs.aws.amazon.com/wellarchitected/latest/security-pillar/identity-and-access-management.html)
