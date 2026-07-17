---
title: "AI Agents: Workload Identity Federation"
slug: "agent-workload-identity-federation"
description: "Grant agent runtimes short-lived cloud credentials without long-lived keys: OIDC federation, Kubernetes service accounts, AWS IRSA/GCP WIF, and scoped IAM for tool access."
datePublished: "2025-10-19"
dateModified: "2026-07-17"
tags: ["AI Agents", "Security", "Cloud", "Identity"]
keywords: "workload identity federation agent, OIDC AWS IRSA agent tools, GCP workload identity, agent cloud credentials"
faq:
  - q: "Why not store AWS access keys in agent tool environment variables?"
    a: "Long-lived keys in agent pods leak via logs, heap dumps, and compromised sandboxes. Federation exchanges Kubernetes or cloud OIDC tokens for short-lived STS credentials scoped to the exact tool role — rotation is automatic."
  - q: "How do you scope IAM for agent tools per tenant?"
    a: "Session tags or external ID in AssumeRole trust — map tenant_id to IAM policy conditions on S3 prefixes `s3://bucket/${aws:PrincipalTag/tenant_id}/*`. Never share one broad role across all tenants."
  - q: "Does workload identity apply to serverless agent workers?"
    a: "Yes — Lambda execution roles, Cloud Run service accounts, and Fly.io OIDC to cloud providers all follow the same pattern: runtime identity → federated token → cloud API access."
  - q: "What about agents calling third-party SaaS APIs?"
    a: "Federation is for your cloud resources. SaaS uses OAuth client credentials or vault-stored tokens with rotation — separate from IRSA/WIF but same principle: no eternal secrets in agent memory."
---

Agent tool runners need S3 read access for RAG, Secrets Manager for API keys, and maybe DynamoDB for session state. Embedding `AKIA...` in the orchestrator config means every sandbox escape or log scrape becomes cloud admin theater. **Workload identity federation** binds credentials to the running workload identity — Kubernetes service account, Lambda ARN, Cloud Run revision — and mints **short-lived** tokens via OIDC trust, no static keys on disk.

## Identity chain

```
Agent tool pod (K8s)
  serviceAccount: agent-tool-runner
  OIDC JWT (aud=sts.amazonaws.com)
         │
         ▼
   AWS STS AssumeRoleWithWebIdentity
         │
         ▼
   Temp creds (15min–1hr)
   Role: agent-tool-tenant-scoped
         │
         ▼
   S3 GetObject s3://kb/tenant_42/*
```

Same pattern on GCP (Workload Identity Federation) and Azure (Federated Identity Credentials).

## AWS IRSA setup sketch

Trust policy on IAM role:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "Federated": "arn:aws:iam::123456789012:oidc-provider/oidc.eks.region.amazonaws.com/id/EXAMPLE"
    },
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringEquals": {
        "oidc.eks.region.amazonaws.com/id/EXAMPLE:sub": "system:serviceaccount:agents:tool-runner",
        "oidc.eks.region.amazonaws.com/id/EXAMPLE:aud": "sts.amazonaws.com"
      }
    }
  }]
}
```

Pod annotation:

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: tool-runner
  namespace: agents
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::123456789012:role/agent-tool-runner
```

SDK picks up creds automatically — no env vars.

## Tenant-scoped session tags

Multi-tenant agent platform — one role, ABAC via tags:

```python
import boto3

def s3_client_for_tenant(tenant_id: str):
    sts = boto3.client("sts")
    creds = sts.assume_role(
        RoleArn=TOOL_ROLE_ARN,
        RoleSessionName=f"agent-{tenant_id[:8]}",
        Tags=[{"Key": "tenant_id", "Value": tenant_id}],
        DurationSeconds=3600,
    )["Credentials"]
    return boto3.client(
        "s3",
        aws_access_key_id=creds["AccessKeyId"],
        aws_secret_access_key=creds["SecretAccessKey"],
        aws_session_token=creds["SessionToken"],
    )
```

IAM policy:

```json
{
  "Effect": "Allow",
  "Action": ["s3:GetObject"],
  "Resource": "arn:aws:s3:::agent-kb/*",
  "Condition": {
    "StringLike": {
      "s3:prefix": ["${aws:PrincipalTag/tenant_id}/*"]
    }
  }
}
```

Agent orchestrator passes `tenant_id` — LLM never selects IAM scope.

## GCP Workload Identity Federation

External K8s → GCP without service account keys:

```yaml
# K8s SA annotated to GCP SA
annotations:
  iam.gke.io/gcp-service-account: agent-tools@project.iam.gserviceaccount.com
```

Or non-GKE OIDC:

```python
from google.auth import identity_pool

credentials = identity_pool.Credentials.from_info({
    "type": "external_account",
    "audience": "//iam.googleapis.com/projects/123/locations/global/workloadIdentityPools/pool/providers/k8s",
    "subject_token_type": "urn:ietf:params:oauth:token-type:jwt",
    "token_url": "https://sts.googleapis.com/v1/token",
    "service_account_impersonation_url": "...",
})
```

## Agent tool gateway pattern

Tools don't call AWS directly from LLM sandbox — orchestrator broker:

```python
@tool("read_knowledge_document")
def read_kb(doc_id: str, ctx: ToolContext) -> str:
    s3 = s3_client_for_tenant(ctx.tenant_id)
    key = f"{ctx.tenant_id}/docs/{doc_id}"
    obj = s3.get_object(Bucket=KB_BUCKET, Key=key)
    return obj["Body"].read().decode()
```

Sandbox has no cloud creds; only orchestrator process holds federated identity.

## Credential lifetime and refresh

| Cloud | Default TTL | Agent implication |
|-------|-------------|-------------------|
| AWS STS | 15 min–12 hr | Refresh before long tool batch |
| GCP SA | 1 hr | SDK auto-refresh |
| Azure | 1–24 hr | Managed identity refresh |

Long-running agent runs (>1hr) must refresh or subprocess per activity with fresh creds.

## Audit and least privilege

CloudTrail / GCP Audit Logs record `roleSessionName` and session tags — correlate to `run_id` by naming convention `agent-run_9f3`.

Role permissions: start with read-only; add write per tool after review. Deny `iam:*`, `s3:ListAllMyBuckets`, metadata SSRF paths.

## Anti-patterns

- Mounting node IAM role on agent pods — blast radius entire cluster.
- Same S3 bucket prefix for all tenants without ABAC.
- Passing cloud creds into code interpreter sandbox.
- Eternal `AWS_ACCESS_KEY_ID` in CI for agent deploy — use OIDC GitHub Actions to AWS.

## Resources

- [AWS — IAM Roles for Service Accounts (IRSA)](https://docs.aws.amazon.com/eks/latest/userguide/iam-roles-for-service-accounts.html)
- [GCP — Workload Identity Federation](https://cloud.google.com/iam/docs/workload-identity-federation)
- [Azure — Workload identity federation](https://learn.microsoft.com/en-us/entra/workload-id/workload-identity-federation)
- [Kubernetes — Service Accounts](https://kubernetes.io/docs/concepts/security/service-accounts/)
- [OWASP — Secrets Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)

## Operational checklist for production rollouts

Before widening traffic, confirm dashboards exist for the leading indicators discussed above — not only lagging incident counts. Run a game day that exercises rollback: feature flag off, alias revert, or kill switch without a new deploy. Document who owns each control in the service catalog so on-call is not guessing during a Sev2.

Slice metrics by tenant tier during canary. Global averages hide bad enterprise cohorts. Pair technical metrics with a sample of user-visible outcomes weekly — support ticket themes often lead dashboards by 48 hours.

When third-party providers change defaults (models, TLS roots, streaming semantics), error-class metrics should catch drift within hours even if no deploy shipped on your side. Keep a changelog subscription for every dependency on the critical path.

## Field notes from incident reviews

Repeat incidents without automation tickets are a planning failure, not an engineering surprise. Capture toil hours in retro; fund paydown in the next sprint. Prefer idempotent handlers and explicit state machines over ad-hoc scripts that only the author understands.

Audit trails matter for billing, auth, and safety paths. Log structured enums — not prose — so aggregation survives high volume. Redact secrets and tokens at the logging boundary; debugging can use correlation ids instead.

## Operational checklist for production rollouts

Before widening traffic, confirm dashboards exist for the leading indicators discussed above — not only lagging incident counts. Run a game day that exercises rollback: feature flag off, alias revert, or kill switch without a new deploy. Document who owns each control in the service catalog so on-call is not guessing during a Sev2.

Slice metrics by tenant tier during canary. Global averages hide bad enterprise cohorts. Pair technical metrics with a sample of user-visible outcomes weekly — support ticket themes often lead dashboards by 48 hours.

When third-party providers change defaults (models, TLS roots, streaming semantics), error-class metrics should catch drift within hours even if no deploy shipped on your side. Keep a changelog subscription for every dependency on the critical path.

## Field notes from incident reviews

Repeat incidents without automation tickets are a planning failure, not an engineering surprise. Capture toil hours in retro; fund paydown in the next sprint. Prefer idempotent handlers and explicit state machines over ad-hoc scripts that only the author understands.

Audit trails matter for billing, auth, and safety paths. Log structured enums — not prose — so aggregation survives high volume. Redact secrets and tokens at the logging boundary; debugging can use correlation ids instead.

## Operational checklist for production rollouts

Before widening traffic, confirm dashboards exist for the leading indicators discussed above — not only lagging incident counts. Run a game day that exercises rollback: feature flag off, alias revert, or kill switch without a new deploy. Document who owns each control in the service catalog so on-call is not guessing during a Sev2.

Slice metrics by tenant tier during canary. Global averages hide bad enterprise cohorts. Pair technical metrics with a sample of user-visible outcomes weekly — support ticket themes often lead dashboards by 48 hours.

When third-party providers change defaults (models, TLS roots, streaming semantics), error-class metrics should catch drift within hours even if no deploy shipped on your side. Keep a changelog subscription for every dependency on the critical path.

## Field notes from incident reviews

Repeat incidents without automation tickets are a planning failure, not an engineering surprise. Capture toil hours in retro; fund paydown in the next sprint. Prefer idempotent handlers and explicit state machines over ad-hoc scripts that only the author understands.

Audit trails matter for billing, auth, and safety paths. Log structured enums — not prose — so aggregation survives high volume. Redact secrets and tokens at the logging boundary; debugging can use correlation ids instead.

