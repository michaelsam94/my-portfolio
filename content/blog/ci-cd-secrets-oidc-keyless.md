---
title: "Keyless CI Auth with OIDC"
slug: "ci-cd-secrets-oidc-keyless"
description: "Replace long-lived cloud credentials in CI with OpenID Connect tokens so pipelines authenticate to AWS, GCP, and Azure without stored secrets."
datePublished: "2025-03-07"
dateModified: "2025-03-07"
tags: ["DevOps", "CI/CD"]
keywords: "OIDC CI, keyless authentication, GitHub Actions OIDC, AWS IAM role CI, workload identity federation"
faq:
  - q: "What is keyless CI authentication?"
    a: "Keyless CI auth uses short-lived OIDC tokens issued by your CI platform to prove a job's identity—repository, branch, environment—without storing cloud access keys in secrets. The cloud provider validates the token against a configured trust policy and returns temporary credentials scoped to that job. Tokens expire in minutes and cannot be reused from a fork or different repo."
  - q: "Why is OIDC better than access keys in GitHub Secrets?"
    a: "Long-lived access keys leak through logs, fork PRs, compromised runners, and ex-employees with secret visibility. OIDC tokens are minted per job, bound to specific claims like ref and environment, and never appear in your repository. Rotation becomes automatic—there is no key to rotate."
  - q: "Can fork PRs use OIDC to deploy?"
    a: "Only if you explicitly allow it, which you generally should not for production. Trust policies should require specific repositories and ref patterns—main branch and release tags only. GitHub's `pull_request_target` with OIDC to production is a common footgun; restrict deployment OIDC to protected branches and GitHub Environments with required reviewers."
---

Storing `AWS_ACCESS_KEY_ID` in GitHub Secrets works until it doesn't—a key in a log snippet, a fork PR that exfiltrates secrets, or a contractor who copied credentials before offboarding. OIDC-based keyless auth removes the secret entirely. The CI job presents a signed identity token; the cloud provider checks "this token came from repo X on branch Y" and hands back credentials that die when the job ends.

## How the trust chain works

1. CI platform (GitHub Actions, GitLab CI, CircleCI) runs a job and mints an OIDC JWT.
2. The JWT contains claims: issuer, audience, repository, ref, workflow name, environment.
3. Your job sends the JWT to the cloud provider's STS or identity endpoint.
4. The provider validates signature and claims against a trust policy you configured.
5. Short-lived credentials (15 min – 1 hr) are returned scoped to an IAM role or service account.

No static secret ever enters the repository. The trust policy is the security boundary.

## GitHub Actions to AWS

Enable OIDC in the workflow permissions block:

```yaml
permissions:
  id-token: write   # required to request OIDC token
  contents: read

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::123456789012:role/github-deploy
          aws-region: us-east-1

      - run: aws s3 sync ./dist s3://my-bucket/
```

On the AWS side, create an IAM OIDC identity provider for `token.actions.githubusercontent.com` and a role trust policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "Federated": "arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com"
    },
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringEquals": {
        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
      },
      "StringLike": {
        "token.actions.githubusercontent.com:sub": "repo:myorg/myapp:ref:refs/heads/main"
      }
    }
  }]
}
```

Tighten `sub` to specific environments with GitHub Environments:

```
repo:myorg/myapp:environment:production
```

## GCP Workload Identity Federation

GCP uses Workload Identity Pools to map external OIDC tokens to service accounts:

```yaml
- uses: google-github-actions/auth@v2
  with:
    workload_identity_provider: projects/123/locations/global/workloadIdentityPools/github/providers/github
    service_account: deploy@my-project.iam.gserviceaccount.com

- uses: google-github-actions/setup-gcloud@v2
```

The provider's attribute condition maps GitHub claims to IAM:

```
assertion.repository == 'myorg/myapp' &&
assertion.ref == 'refs/heads/main'
```

## Azure Federated Credentials

Azure AD app registrations accept federated credentials bound to GitHub subject claims:

```yaml
- uses: azure/login@v2
  with:
    client-id: ${{ vars.AZURE_CLIENT_ID }}
    tenant-id: ${{ vars.AZURE_TENANT_ID }}
    subscription-id: ${{ vars.AZURE_SUBSCRIPTION_ID }}
```

Configure the federated credential in Azure Portal or CLI with subject `repo:myorg/myapp:ref:refs/heads/main`.

## Hardening the trust policy

**Scope by ref.** Allow `main`, `release/*`, and nothing else for production roles. Feature branches get a separate role with read-only or staging access.

**Use GitHub Environments.** Environments add deployment protection rules and inject an `environment` claim into the OIDC token. Bind production roles to `environment:production` only.

**Deny fork PRs.** GitHub does not issue OIDC tokens to workflows triggered from fork PRs by default for the `pull_request` event when using environments—but verify your setup. Never use `pull_request_target` with OIDC deploy unless you understand the privilege escalation risk.

**Least privilege on the role.** The assumed role should grant exactly what deploy needs—S3 put on one bucket, not `s3:*`. Separate build roles (ECR push) from deploy roles (ECS update).

## Migrating from static keys

Run both paths in parallel during migration: OIDC for new workflows, existing keys with expiration dates for legacy jobs. Audit CloudTrail for `AssumeRoleWithWebIdentity` success before deleting keys. Alert on any `CreateAccessKey` API calls after cutover.

I typically delete the IAM user entirely rather than disabling keys—disabled keys still show up in audits and get re-enabled by someone "just testing."

## When OIDC is not enough

Third-party SaaS tools that only accept API keys (some registries, legacy deploy targets) still need secrets—store them in a vault with rotation, not in repo env files. Self-hosted runners need the same OIDC setup but you must trust the runner infrastructure; compromised self-hosted runners can request tokens for any job they execute.

## GitHub OIDC to AWS

```yaml
permissions:
  id-token: write
steps:
  - uses: aws-actions/configure-aws-credentials@v4
    with:
      role-to-assume: arn:aws:iam::123456789:role/GitHubDeploy
      aws-region: us-east-1
```

No long-lived AWS keys in GitHub secrets — federation via OIDC with trust policy scoped to repo + branch.

## Common production mistakes

Teams get secrets oidc keyless wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

CI/CD for secrets oidc keyless breaks merges when pipeline secrets rotate without updating OIDC trust, cache keys ignore lockfile changes, and deployment gates check build success but not smoke tests.

## Debugging and triage workflow

When secrets oidc keyless misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [GitHub Actions OIDC documentation](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/about-security-hardening-with-openid-connect)
- [AWS IAM OIDC identity providers](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_create_oidc.html)
- [GCP Workload Identity Federation](https://cloud.google.com/iam/docs/workload-identity-federation)
- [Azure federated identity credentials](https://learn.microsoft.com/en-us/azure/developer/github/connect-from-azure-openid-connect)
