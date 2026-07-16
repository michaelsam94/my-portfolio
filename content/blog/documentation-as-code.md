---
title: "Documentation as Code"
slug: "documentation-as-code"
description: "Treat docs like software: version in Git, review in PRs, test snippets, generate from OpenAPI, and keep runbooks next to the code they describe."
datePublished: "2025-11-10"
dateModified: "2025-11-10"
tags: ["Career", "Engineering", "Documentation", "DevOps"]
keywords: "documentation as code, docs in Git, Markdown documentation, OpenAPI generated docs, ADR architecture decision records, docs CI review, runbooks version control"
faq:
  - q: "What belongs in the repo versus a wiki?"
    a: "Anything that must stay in sync with code belongs in the repo: API docs generated from schemas, README setup steps, ADRs, runbooks for services you deploy from that repo, and CONTRIBUTING guides. Wikis fit org-wide policies and onboarding overviews that change independently of a single service's release cycle."
  - q: "How do I prevent docs from rotting?"
    a: "Review docs in the same PR as code changes when behavior changes. Add CI checks: link checking, OpenAPI drift detection, and optional snippet execution tests. Assign doc updates in the PR template checklist. Rot happens when docs are nobody's job — make them part of definition of done."
  - q: "Should I use a docs site generator or plain Markdown?"
    a: "Start with Markdown in the repo. Add MkDocs, Docusaurus, or VitePress when navigation, search, and multi-package docs justify the tooling. Generated sites still source from Git; the generator is a build step, not a separate authoring silo."
---

The onboarding doc said to run `make dev` and open localhost:3000. The Makefile was renamed six months ago; the port moved to 8080 in a config refactor nobody told docs about. New hires lost half a day. That failure is not "people don't read docs" — it is docs living outside the change stream. Documentation as code means writing, reviewing, versioning, and testing documentation the same way you treat application code: in Git, in pull requests, with CI that catches drift before it ships.

## What "as code" actually means

Four practices define the approach:

1. **Version control** — Markdown, OpenAPI specs, and diagrams live beside the services they describe.
2. **Review in PRs** — a behavior change without a doc update fails the same bar as a change without tests.
3. **Automated validation** — link checkers, schema diff, spell check, and snippet tests in CI.
4. **Generated where possible** — API reference from OpenAPI/Protobuf; CLI help from `--help` output embedded in docs.

The goal is a single source of truth that moves with the codebase, not a Confluence page bookmarked in 2019.

## Structure that scales

A layout I have seen work across monorepos and small services:

```
docs/
  adr/           # architecture decision records
  runbooks/      # incident and ops procedures
  api/           # OpenAPI specs (or link to packages)
README.md        # quickstart — must work on day one
CONTRIBUTING.md  # PR process, local setup
```

Each service directory can carry a focused `README.md` for ownership and deployment specifics. ADRs capture *why* decisions were made — invaluable when the original author has moved on:

```markdown
# ADR 0042: Use event sourcing for billing

## Status
Accepted (2025-09-12)

## Context
Billing disputes require reconstructing state at arbitrary past dates...

## Decision
Store billing events in PostgreSQL; project invoices asynchronously.
```

ADRs are immutable once accepted; supersede with a new ADR rather than editing history.

## OpenAPI and generated reference

Hand-written API docs lie. Generate from the spec:

```yaml
# docs/api/openapi.yaml
openapi: 3.1.0
info:
  title: Orders API
  version: 2.1.0
paths:
  /v2/orders/{id}:
    get:
      operationId: getOrder
      ...
```

CI step:

```bash
npx @redocly/cli lint docs/api/openapi.yaml
npx @redocly/cli diff docs/api/openapi.yaml origin/main --fail-on-changed
```

If the spec changes without a version bump or changelog entry, the build fails. Redoc or Swagger UI publishes from the same file — no duplicate endpoint tables.

## Runbooks next to deployment config

Runbooks that live in a separate wiki always lag. Put them in `docs/runbooks/high-cpu.md` and link from alerts:

```markdown
## Symptom
P99 latency > 2s on orders-api for 5+ minutes.

## Investigation
1. Check Grafana dashboard: orders-api / golden signals
2. kubectl top pods -n production -l app=orders-api
3. Recent deploys: git log --oneline -5 on main

## Mitigation
Roll back: kubectl rollout undo deployment/orders-api -n production
```

When the deployment name or namespace changes, the same PR updates the runbook.

## CI checks worth adding

| Check | Tool | Catches |
|-------|------|---------|
| Broken links | lychee, markdown-link-check | Moved URLs, typos |
| OpenAPI drift | Redocly diff | Undocumented API changes |
| Spelling | cspell | Obvious errors in user-facing text |
| Code snippet syntax | mdbook test, custom extractors | Invalid examples |

Keep checks fast. A five-minute doc pipeline runs on every PR; a thirty-minute one gets skipped.

## Culture beats tooling

The best doc CI fails if teams treat doc updates as optional. PR templates help:

```markdown
## Checklist
- [ ] Tests added/updated
- [ ] User-facing behavior documented (README, OpenAPI, or CHANGELOG)
- [ ] Runbook updated if ops behavior changed
```

Tech leads model the behavior: comment on missing docs in code review the same way you comment on missing error handling.

## Versioning and deprecation

Docs in git need lifecycle management like code:

```markdown
> **Deprecated:** Use `/api/v2/orders` instead. Removal: 2026-09-01.
```

- **CHANGELOG.md** — user-visible behavior changes per release
- **MIGRATION.md** — step-by-step upgrade guides for breaking changes
- **Deprecation headers in API** — `Sunset`, `Deprecation` RFC 8594 alongside doc updates

Same PR that deprecates an endpoint updates OpenAPI, adds sunset header middleware, and updates the migration guide. Splitting across three PRs guarantees users miss the notice.

## Documentation site generation

Pick tooling that matches team workflow:

| Tool | Best for | Tradeoff |
|------|----------|----------|
| MkDocs + Material | Internal tech docs | Python ecosystem |
| Docusaurus | Product docs + blog | React overhead |
| mdBook | Rust-style books | Simple, less plugin ecosystem |
| Astro Starlight | Fast static sites | Newer, fewer enterprise examples |

Generate API reference from OpenAPI — never maintain endpoint tables by hand. Embed runnable examples where possible (curl, SDK snippets tested in CI).

## Ownership and stale doc detection

`CODEOWNERS` for `/docs/**` routes review requests to team experts. Add CI job:

```bash
# Fail if doc not updated in 180 days AND references deprecated API version
find docs -name '*.md' -mtime +180 -exec grep -l 'api/v1' {} \;
```

Quarterly doc gardening sprint: fix top 20 broken links from lychee report, archive pages with zero traffic in analytics.

Pair with [technical writing for engineers](https://blog.michaelsam94.com/technical-writing-for-engineers/) for voice and structure standards.

## Production checklist

- [ ] Broken link checker (lychee) in CI on every PR
- [ ] OpenAPI spec is source of truth, not generated annotations
- [ ] CODEOWNERS on `/docs/**` directories
- [ ] Deprecation notices with sunset dates in docs and API headers
- [ ] Doc updates required in same PR as behavior changes

## Common production mistakes

Teams get documentation as code wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of documentation as code fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Resources

- [Architecture Decision Records (ADR) overview](https://adr.github.io/)
- [OpenAPI Specification](https://spec.openapis.org/oas/latest.html)
- [Redocly CLI — lint and diff OpenAPI](https://redocly.com/docs/cli/)
- [Google developer documentation style guide](https://developers.google.com/style)
- [Diátaxis documentation framework](https://diataxis.fr/)
