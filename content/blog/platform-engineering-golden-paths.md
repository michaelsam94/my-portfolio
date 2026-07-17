---
title: "Golden Paths in Platform Engineering"
slug: "platform-engineering-golden-paths"
description: "Design golden paths that teams actually adopt: paved-road templates, optional escape hatches, documentation co-located with code, and measuring path vs off-path usage."
datePublished: "2026-02-20"
dateModified: "2026-07-17"
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


## Federated template ownership

Platform maintains base template; product verticals own template-overlays for domain-specific defaults. Federation prevents one template ignoring 40% of teams while keeping security baseline centralized.

## Path discovery in IDE

Ship platform create CLI mirroring scaffolder templates with same skeleton Git URLs. CLI and portal share template version pin.

## Cost of off-path services

Track AWS spend tagged golden-path:false quarterly. Off-path services averaging 3x cost per request become migration candidates with finance backing.

## Onboarding time SLA

Measure hours from platform new service to first successful staging deploy with CI green. Target under 4 hours median. Interview outliers over 24 hours.

## Template testing pyramid

Unit test template rendering (cookiecutter/yeoman output contains required files). Integration test scaffolds to ephemeral namespace with CI green. E2E test sample service deploys and passes smoke HTTP check. Template PR failing integration test blocks merge — prevents shipping broken Dockerfile base image pin.

## Documentation co-located with template

README in template repo, not wiki — versioned alongside skeleton. `docs/runbook.md` link pre-wired in catalog metadata. Stale wiki link was #1 complaint in our developer survey; co-location cut onboarding questions 35%.

## Naming and discoverability

Golden path names should match how developers ask questions: "web-api" not "standard-microservice-template-v2." Search in portal indexes title, description, and tags — template metadata `spec.parameters` includes `tier` and `language` filters. Obscure names hide paths; adoption stays low despite good scaffolding.

## Deprecation communications

When web-api-v1 template sunsets, Backstage shows banner on create page and emails owners of services on v1 catalog metadata. Automated PR bumps `templateVersion` in platform.yaml when diff is mechanical — human review only for breaking Helm chart changes.

## Cross-functional review of templates

Security reviews Dockerfile USER directive and read-only root. SRE reviews resource requests and probes. FinOps reviews default instance sizes. Template PR requires sign-off from each function — catches golden path shipping db.r6g.4xlarge default because platform engineer tested on beefy laptop.

## Hackathon and golden path adoption

Run internal hackathon requiring scaffolder use — friction discovered in 24 hours beats quarterly survey. Winning projects on golden path become reference implementations cited in template README; organic advocacy beats mandate memo from VP Engineering.

## Closing notes

Quarterly template refresh PRs bump base image CVE patches automatically; services opt-in via catalog metadata bump field without forced migration — balance security defaults with team autonomy.

## Additional guidance

Golden paths succeed when time-to-first-deploy drops quarter over quarter and scaffolder usage exceeds seventy percent of new repositories without mandate. Interview teams that chose off-path quarterly — their blockers become template fixes, not optional backlog items platform engineers defer indefinitely.

## Resources

- [Backstage Software Templates](https://backstage.io/docs/features/software-templates/)
- [Team Topologies — platform teams](https://teamtopologies.com/)
- [Puppet State of DevOps — platform engineering](https://www.puppet.com/resources/report)
- [CNCF Platforms whitepaper](https://tag-app-delivery.cncf.io/whitepapers/platforms/)
- [Spotify Engineering — golden paths talk](https://engineering.atspotify.com/)
