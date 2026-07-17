---
title: "Technical Writing for Engineers"
slug: "technical-writing-for-engineers"
description: "How engineers write documentation that gets read: audience-first structure, runnable examples, diagrams, review workflows, and maintaining docs as code."
datePublished: "2025-12-02"
dateModified: "2026-07-17"
tags:
  - "Career"
  - "Documentation"
  - "Communication"
  - "Engineering"
keywords: "technical writing engineers, documentation best practices, README structure, docs as code, engineering communication, runbook writing"
faq:
  - q: "q"
    a: "a"
  - q: "q"
    a: "a"
  - q: "q"
    a: "a"
---

The best incident response of my career started with a runbook that had one accurate command and the name of the on-call who last verified it. The worst started with a Confluence page titled "Platform Overview" that was forty screens long and mentioned a service decommissioned eighteen months earlier. Engineers write constantly — PR descriptions, design docs, postmortems, Slack threads — but "technical writing" as a skill rarely gets deliberate practice.

Good technical writing is not literary style. It is information architecture: the right facts, in the right order, for a reader who is tired and under deadline.

## Know the reader and the job-to-be-done

Before typing, answer:

- **Who** — new hire, on-call engineer, PM, external API consumer?
- **When** — onboarding, debugging 3 AM, evaluating build vs buy?
- **Success** — what can they do after reading?

A design doc for staff engineers includes trade-off tables and rejected alternatives. A runbook for on-call includes symptoms, verification commands, and rollback — not history of why the service exists.

## Structure that respects attention

**Inverted pyramid.** Conclusion and action first; context after.

```markdown
## Symptom
Payments failing with `timeout contacting ledger`

## Fix (most cases)
1. Check ledger health: `kubectl get pods -n payments -l app=ledger`
2. If CrashLoopBackOff → scale to zero and restore from snapshot per runbook-ledger-restore.md

## Details
The ledger pod mounts...
```

**Headings as search targets.** "How to rotate API keys" beats "Security."

**One page, one job.** Split "Development setup" from "Production deployment." Long scrolls hide the answer.

## Runnable examples or it did not happen

Every code block should be copy-pasteable with stated prerequisites:

```bash
# Requires: aws cli v2, profile "staging"
aws ecs update-service --cluster api-staging --service web --force-new-deployment
```

Include expected output when non-obvious:

```
{
  "service": {
    "desiredCount": 3,
    "runningCount": 3
  }
}
```

Stale commands erode trust faster than missing docs. CI step: extract and dry-run examples where feasible.

## Diagrams for flows, tables for options

Use diagrams when sequence matters — request path, failure cascade, state machine. Use tables when comparing options:

| Approach | Latency | Ops burden |
| --- | --- | --- |
| Sync webhook | Low | Retry logic required |
| Outbox + queue | Higher | Durable, observable |

ASCII and Mermaid in git beat orphaned Lucidchart links.

## Design docs that survive review

Template that works:

1. **Problem** — one paragraph
2. **Goals / non-goals**
3. **Proposal** — diagram + component responsibilities
4. **Alternatives considered** — at least two, with rejection reasons
5. **Rollout and rollback**
6. **Open questions**

Non-goals prevent scope creep in comments. Alternatives prove you thought beyond the first idea.

## Postmortems without blame, with leverage

Blameless does not mean detail-free. Include timeline (UTC), contributing factors, what detected it, what fixed it, action items with owners. Future on-call reads the timeline, not the feelings.

## Docs as code workflow

- Markdown in repo under `docs/`
- PR review for doc changes alongside code
- Link checker in CI (lychee, markdown-link-check)
- ADRs for decisions (`docs/adr/0007-use-redis-for-sessions.md`)
- Generated API docs from OpenAPI where possible — single source of truth

When behavior changes, the PR that changes code updates the doc. Same PR, same reviewer.

## Editing checklist

- [ ] First paragraph answers "what is this?"
- [ ] Commands tested this week
- [ ] Jargon defined or linked on first use
- [ ] No passive voice hiding ownership ("mistakes were made" → "the deploy script skipped migration X")
- [ ] Under 800 words unless reference material

## Docs for on-call and incidents

Runbooks belong beside code: symptom, verification command, fix, rollback. Link from alert runbook URL in PagerDuty to the exact Markdown file in git. During incidents, the doc you update after resolution is as important as the postmortem — capture the command that actually worked, not the theoretical one.

## Writing for different audiences

Same system, three documents — not one doc with something for everyone:

| Audience | Doc type | Focus | Length |
|----------|----------|-------|--------|
| New hire | Tutorial | Happy path, local setup | 15 min read |
| Feature owner | How-to | One task end-to-end | 5 min |
| On-call | Reference | Flags, endpoints, failure modes | Lookup only |

Diátaxis works because mixing tutorial tone into reference material frustrates both readers. Link between types: tutorial ends with "see Runbook X for production deploy."

## API and code documentation

Generated OpenAPI from annotations drifts when annotations lie. Better pattern:

1. Hand-write `openapi.yaml` or proto as source of truth
2. Generate server stubs or client SDKs from spec
3. CI fails if implementation routes differ from spec (contract tests)

For internal libraries, document **invariants** not just signatures:

```kotlin
/**
 * Returns cached user or fetches from API.
 * @throws UserNotFound if ID invalid after refresh
 * INVARIANT: never returns stale data older than [maxAge]
 */
suspend fun getUser(id: UserId): User
```

The invariant line prevents misuse that Javadoc alone won't catch.

## Measuring documentation quality

Vanity metrics (page views) mislead. Track:

- **Time-to-first-success** — how long until a new engineer completes setup
- **Support ticket tags** — "docs unclear" count per area
- **Search failures** — internal doc search with zero results (add pages for those queries)
- **Doc PR age** — docs updated within 48h of related code merge

Quarterly, run a "doc drill": engineer unfamiliar with the service follows only the runbook to execute a failover. Gaps they hit become high-priority fixes.

## Common failure modes

- **Orphan docs** — Confluence page linked from nowhere, contradicts git
- **Screenshot rot** — UI changed, images didn't
- **Copy-paste commands** — missing env vars, wrong region
- **Missing prerequisites** — assumes VPN access not mentioned until step 7
- **No ownership** — `@team-platform` on every page means no one maintains any page

Assign a named owner per doc directory in `CODEOWNERS`. Stale docs older than six months without updates should trigger review tickets automatically.

## Production checklist

- [ ] Runbooks linked from PagerDuty alert URLs
- [ ] First paragraph answers "what is this?" in every doc
- [ ] Commands in docs tested within the last release cycle
- [ ] Diátaxis types separated (tutorial vs reference vs how-to)
- [ ] Quarterly doc drill with engineer unfamiliar with service

## Review workflow that keeps docs honest

Treat doc changes like code: PR review, CI link checking, ownership in CODEOWNERS. Require doc updates in the same PR as breaking API changes — block merge if `CHANGELOG` or API reference is stale. Schedule quarterly "doc debt" sprints to fix top ten support-ticket topics that lack runbooks. Measure doc success by time-to-resolution in support tickets referencing doc links, not by page view count alone.

## Resources

- [Google developer documentation style guide](https://developers.google.com/style)
- [Diátaxis documentation framework](https://diataxis.fr/)
- [Write the Docs](https://www.writethedocs.org/)
- [Architecture Decision Records (GitHub)](https://adr.github.io/)
- [Technical Writing Courses (Google)](https://developers.google.com/tech-writing)

## technical writing for engineers rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## technical writing for engineers rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## technical writing for engineers rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## technical writing for engineers rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## technical writing for engineers rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## technical writing for engineers rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## technical writing for engineers rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## technical writing for engineers rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## technical writing for engineers rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## technical writing for engineers rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## technical writing for engineers rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## API reference layers

OpenAPI spec generated from code stays accurate; narrative docs explain auth flows, pagination, idempotency, and error retry policy OpenAPI cannot express.

```yaml
# openapi excerpt — pair with prose on rate limits
paths:
  /charges:
    post:
      summary: Create charge (idempotent via Idempotency-Key header)
```

Link from each operation to guide section with curl example.

## On-call documentation hierarchy

1. Runbook (symptom → fix)
2. Architecture diagram (context)
3. ADR (why built this way)
4. Postmortem index (historical failures)

On-call starts at layer 1 — never layer 3 at 3 AM.

## Writing for international teams

Simple sentences, avoid idioms, define acronyms, UTC timestamps always, explicit locale assumptions in date formatting docs.

## Docs search

If using MkDocs/Docusaurus, configure local search or Algolia — unsearchable docs become Slack questions.

## Measuring doc success

- Time-to-first-success for onboarding survey
- Support ticket tags "docs unclear"
- Search zero-result queries

Quarterly review top zero-result queries → new pages.

## Changelog discipline

User-facing docs need changelog entry per release — link migration guides for breaking API changes.

## Pair writing

Engineer drafts accuracy; tech writer edits clarity — 30-minute pairing beats async comment wars.

Technical writing compounds — every hour invested in quickstart saves ten hours of interrupts over the doc lifetime.
