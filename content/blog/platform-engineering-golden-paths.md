---
title: "Golden Paths in Platform Engineering"
slug: "platform-engineering-golden-paths"
description: "Design golden paths that teams actually adopt: paved-road templates, optional escape hatches, documentation co-located with code, and measuring path vs off-path usage."
datePublished: "2026-02-20"
dateModified: "2026-02-20"
tags: ["Platform Engineering", "DevOps", "Developer Experience", "Architecture"]
keywords: "golden path platform engineering, paved road developer experience, internal developer platform, platform templates, backstage scaffolder"
faq:
  - q: "What is a golden path in platform engineering?"
    a: "The officially supported, documented, easiest way to accomplish a common task — deploy a microservice, set up CI, provision a database. It encodes organizational best practices in templates and automation so teams don't reinvent wheels or bypass security defaults."
  - q: "How is a golden path different from mandatory standards?"
    a: "Golden paths are the default recommendation with friction removed — scaffolding, docs, support. Standards are rules you must comply with. Effective platforms combine both: the golden path is compliant by construction; off-path usage requires exception approval."
  - q: "How do you measure golden path adoption?"
    a: "Track percentage of new services created via scaffolder vs manual setup, CI template usage, deployment method (GitOps repo vs kubectl), and support ticket volume per onboarding path. Low adoption means the path isn't easier than the alternative."
---

Platform team shipped a "reference architecture" PDF. Six months later, eleven microservices existed and nine ignored the PDF. The two that followed it were the ones platform engineers built themselves. Golden paths aren't documentation — they're the path of least resistance: `create service` → working repo with CI, observability, and deploy pipeline in four minutes.

## Paved road vs golden path vs cage

| Approach | Developer experience | Risk control |
|----------|---------------------|--------------|
| Wild west | Maximum freedom | Inconsistent, security gaps |
| Golden path | Easy default, escape hatches | Most teams compliant by default |
| Cage | Only approved options | Low variance, high frustration |

Golden path philosophy: **make the right thing easy, not the wrong thing impossible.** Platform teams that block all off-path work become bottlenecks. Teams that document without automating become ignored.

## Anatomy of a golden path

Our `web-api` golden path includes:

```
backstage.io/create → select web-api template
    │
    ├── Git repo (TypeScript, Express, health checks)
    ├── Dockerfile + Helm chart
    ├── GitHub Actions (test, scan, deploy to staging)
    ├── Argo CD Application manifest
    ├── Datadog APM + standard dashboards
    ├── SOPS secrets placeholder
    └── README with runbook links
```

Four minutes to first deploy to staging. Deviating means copying none of this and owning the integration gap.

**Template source lives in Git.** Versioned, PR-reviewed, changelog when platform updates base image or CI action versions.

## Backstage Software Templates example

```yaml
# template.yaml
apiVersion: scaffolder.backstage.io/v1beta3
kind: Template
metadata:
  name: web-api
  title: Web API (Golden Path)
spec:
  steps:
    - id: fetch
      action: fetch:template
      input:
        url: ./skeleton
    - id: publish
      action: publish:github
      input:
        repoUrl: github.com?owner=acme&repo=${{ values.name }}
    - id: register
      action: catalog:register
```

Developers discover templates in the internal developer portal — not Confluence, not Slack pins.

## Escape hatches without anarchy

Off-path is allowed with visibility:

- **Exception registry:** Jira ticket + architect approval for non-standard runtime (Rust instead of Node)
- **Compliance checks still run:** VPC placement, tagging, vulnerability scan in CI — regardless of template
- **Sunset off-path services:** quarterly review of services not on golden path CI; migrate or justify

The goal isn't 100% template usage — it's 80% on-path with off-path being deliberate, not accidental.

## Keeping paths fresh

Stale templates are worse than no templates — they ship deprecated Node 16 while docs say 20.

- **Platform changelog** when template updates; notify service owners of opt-in upgrades
- **Dependabot on template repos** — template maintainers eat their own cooking first
- **Quarterly developer survey:** "What blocked you from using the golden path?"

We run `template-test` CI that scaffolds a dummy service and deploys to ephemeral namespace on every template PR.

## Anti-patterns we've seen

**PDF architecture.** Nobody reads it during sprint pressure.

**Platform built for platform team.** Templates work for Go microservices because platform uses Go; Python teams suffer.

**Mandatory portal with 47 form fields.** Scaffolder asks three questions; sensible defaults handle the rest.

**No migration path.** Existing services can't adopt golden path CI without rewrite. Offer incremental adoption — drop in standard Dockerfile, keep app code.

## Measuring success

| Metric | Healthy signal |
|--------|----------------|
| Time to first prod deploy (new service) | Decreasing quarter over quarter |
| Scaffolder-created repos / total new repos | > 70% |
| Platform support tickets | Flat or down as org grows |
| Security scan pass rate on first CI run | > 90% |

Golden paths succeed when developers choose them because Thursday afternoon beats Friday firefighting.

## Template versioning and upgrades

Semantic version your template repo. Services record `templateVersion` in catalog metadata. Platform announces breaking template changes with migration PRs — automated codemods when possible for CI workflow renames.

Deprecate old templates with sunset date; Backstage template page shows "deprecated — migrate to web-api-v2" banner.

## Operational notes

Measure time-from-template-to-first-successful-deploy as north star metric. If median exceeds one hour, interview last five teams that abandoned the scaffolder — their blockers become next quarter platform roadmap, not anecdote.

Track template adoption weekly in your service catalog — a golden path nobody uses is just another repo to maintain, not platform leverage.

## Internal developer portal integration

Golden paths live in Backstage, Port, or Cortex — not a wiki page:

```yaml
# backstage-template.yaml
apiVersion: scaffolder.backstage.io/v1beta3
kind: Template
metadata:
  name: web-api-golden
  title: Web API (Golden Path)
spec:
  steps:
    - id: fetch
      action: fetch:template
      input:
        url: ./template
    - id: publish
      action: publish:github
    - id: register
      action: catalog:register
```

Template output registers in service catalog automatically — ownership, links to runbooks, and CI status visible on day one.

## Self-service vs guardrails

Balance developer speed with organizational requirements:

| Autonomous | Requires approval |
|------------|-------------------|
| Dev/staging deploy | Production deploy |
| Add dependency | New external integration |
| Scale replicas | Cross-VPC network access |
| Feature flag toggle | PII data store creation |

Embed guardrails in templates — Terraform modules with policy-as-code (OPA, Sentinel) reject non-compliant infrastructure at scaffold time, not at 2 AM deploy.

Pair with [platform engineering internal developer platform](https://blog.michaelsam94.com/platform-engineering-internal-developer-platform/) for broader IDP architecture decisions.

## Common production mistakes

Teams get golden paths wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of golden paths fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Resources

- [Backstage Software Templates](https://backstage.io/docs/features/software-templates/)
- [Team Topologies — platform teams](https://teamtopologies.com/)
- [Puppet State of DevOps — platform engineering](https://www.puppet.com/resources/report)
- [CNCF Platforms whitepaper](https://tag-app-delivery.cncf.io/whitepapers/platforms/)
- [Spotify Engineering — golden paths talk](https://engineering.atspotify.com/)
