"""Complete unique bodies for slugs where git HEAD is template-polluted."""

FULL: dict[str, str] = {}

FULL["web-performance-404-page-product-sites"] = r"""Marketing shipped a gorgeous illustrated 404 that returned HTTP 200 — Search Console indexed twelve thousand error URLs and organic traffic dipped for six weeks. A product 404 is not a brand moment alone; it is recovery infrastructure. Return the correct status code, help the user find what they wanted, and measure whether they leave or re-engage.

## HTTP status and SEO fundamentals

Always respond with **404 Not Found** (or **410 Gone** when permanently removed). Soft 404s — pretty pages with 200 OK — poison crawl budget and pollute analytics. Configure your edge or framework explicitly:

```typescript
// Next.js App Router
export default function NotFound() {
  return <NotFoundPage />;
}
// not-found.tsx automatically sets 404 status
```

For static hosts, ensure missing paths hit a real 404 document, not SPA fallback to index.html with client-side routing unless you implement prerendered 404 HTML at the edge.

Log 404 paths server-side with referrer and user agent — aggregate weekly. Spikes from one partner domain mean broken inbound links worth fixing at source, not only on your page.

## Content that actually helps users

Effective product 404 pages include:

- **Site search** pre-focused in the header — user already typed a URL; give them search immediately
- **Top destinations** — docs getting started, pricing, support, status page (not random blog posts)
- **Report broken link** form capturing attempted URL and optional email for follow-up
- **Clear language** — "This page moved or never existed" beats cute copy without navigation

Avoid auto-redirecting to homepage — users lose context and bounce confused. Optional smart redirect only when you have high-confidence URL mapping from migrations (`/old-path` → `/new-path` with 301 at server, not JavaScript).

## Performance budget for error routes

404s should load **faster** than happy-path pages — users are already frustrated. Inline critical CSS for the error layout; skip heavy hero video and third-party widgets. Do not load chat widget on 404 unless support is the primary recovery path.

Target LCP under 1.5s on 404 template. Monitor separately in RUM:

```javascript
if (document.body.dataset.pageType === "404") {
  reportMetric("404_lcp", lcpValue, { path: location.pathname });
}
```

Track **404 recovery rate** — users who click search, popular link, or navigate to another page within 60 seconds versus immediate bounce.

## Accessibility on error pages

404 is still a full page — heading hierarchy starts with h1 ("Page not found"), skip link to main content, focus moves to h1 on render for screen reader users. Search input needs `<label>` or `aria-label`. Color contrast on muted illustration text must pass WCAG AA.

Do not rely on illustration alone — always include text explanation. `prefers-reduced-motion` disables animated "lost in space" loops.

## Internationalization and localization

404 copy must translate — `/de/docs/missing` shows German recovery options. hreflang pages that 404 need consistent language in error UI. RTL layouts mirror search and link order.

## Analytics without polluting funnels

Exclude 404 from conversion funnels in analytics config. Segment 404 views by:

- Referrer (external broken link vs internal typo)
- Attempted path patterns (deprecated API docs `/v1/` vs random scans)
- Device class

Alert when 404 rate spikes 3× week-over-week on `/docs/*` — often signals broken release or renamed routes without redirects.

## Migration and redirect discipline

When renaming routes, ship **301 redirects** for six months minimum alongside updated sitemap. Keep redirect map in git:

```yaml
# redirects.yml
- from: /blog/old-slug
  to: /blog/new-slug
  status: 301
```

404 page links to search cannot fix missing redirects — fix server redirects first, polish 404 second.

## Soft 404 detection in monitoring

Synthetic checks hit known-bad URLs expecting 404 status and key string "not found". CI fails if status becomes 200. Google Search Console "Soft 404" report warrants weekly review — often SPA routing misconfiguration.

## Edge and CDN configuration

Cloudflare, Fastly, and similar platforms need explicit 404 page rules — default error page may ignore your React bundle. Serve lightweight static 404 at edge when origin is down to avoid circular error pages.

Cache 404 responses carefully — short TTL (minutes) if some paths flip between valid and invalid during deploys; longer TTL for truly static missing assets.

## Security considerations

404 pages still execute CSP — do not weaken headers on error routes. Reflected path in error message ("You tried /{{path}}") needs HTML escaping to prevent XSS from maliciously crafted URLs logged into page content.

Rate-limit 404 report form — attackers probe paths via your site; do not amplify into email spam to support.

## When to use 410 Gone

Permanently removed content (discontinued product, deleted account portal) should return **410** — signals crawlers to drop faster than 404. Document 410 list in SEO runbook when deprecating major sections.

## Design system integration

404 should use same header, footer, and tokens as product chrome — user knows they are still on your site. Dark mode and theme tokens apply; do not ship unstyled default server page on production domain.

Storybook story for 404 with visual regression — teams forget error pages until rebrand breaks contrast.

A great 404 page combines correct HTTP semantics, fast load, accessible recovery paths, and instrumentation that turns dead ends into product feedback — broken link reports and search queries reveal where navigation and docs fail before support tickets do.

## Framework-specific 404 implementations

**Next.js:** `not-found.tsx` at segment level for localized 404 within docs section while app shell persists. **Remix:** throw `Response` with status 404 from loader. **Static site generators:** prebuild 404.html copied to output root on deploy.

Ensure client-side routers register server 404 fallback — direct URL hit must not return SPA shell with empty content and 200 status.

## A/B testing recovery paths

Test search-first versus popular-links-first layouts — recovery rate differs by audience (developers search docs; consumers click category links). Run experiment two weeks minimum; segment by referrer type.

## Broken link outreach workflow

Weekly export top 100 404 paths with external referrers — email partner webmasters with corrected URLs. Internal broken links become tickets assigned to team owning source page. Reduces repeat 404 without waiting for users to complain.

## Performance checklist summary

| Check | Target |
|-------|--------|
| HTTP status | 404 or 410, never 200 |
| LCP | < 1.5s mobile p75 |
| JS weight | Minimal — no chat widget unless required |
| Search | Labeled input, keyboard accessible |
| Analytics | Excluded from conversion funnels |

Product 404 pages earn their keep when metrics show users recovering instead of bouncing — treat them as product surface area, not design afterthought.
"""

FULL["software-architecture-decision-records"] = r"""Three engineers re-debated Kafka versus RabbitMQ because the original choice lived in a departed architect's slide deck. Architecture Decision Records (ADRs) capture context, decision, and consequences in a few hundred words — optimized for the reader six months later asking "why on earth did we do this?" Michael Nygard's format spread because it fits pull requests, not because enterprises love paperwork.

## Minimal template that gets used

```markdown
# ADR-0007: Use PostgreSQL as system of record

## Status
Accepted

## Context
We need ACID transactions for billing and reporting joins.
Team knows Postgres; managed RDS available.

## Decision
PostgreSQL 16 on RDS as primary datastore.
Read replicas for analytics after Q3.

## Consequences
+ Strong consistency, mature tooling
- Horizontal write scaling limited; revisit sharding if >10k TPS
```

Number sequentially (`0001`, `0002`). Title is searchable. Keep the whole ADR under one printed page — if it grows longer, split into decision plus linked spike document.

## What deserves an ADR

Write ADRs for decisions that are **hard to reverse**, **cross-team**, or **debate-prone**: database choice, messaging bus, auth model, monolith versus services split, public API versioning strategy, multi-region active-active. Skip ADRs for routine library bumps, formatter choices, or sprint-level implementation details — over-documenting dilutes attention from decisions that constrain the system for years.

## When to write in the workflow

Open ADR pull request **before** or **alongside** implementation PR for significant forks. Reviewers comment on decision merit separately from code style. Retroactive ADRs help onboarding when documenting existing system — label `Accepted (documenting existing)` so readers know timing.

Disagreements in PR comments become Context paragraph edits — not Slack loss when the thread archives.

## MADR and considered options

Markdown Any Decision Records add optional sections: decision drivers, considered options, pros/cons tables. Useful for contentious picks:

| Option | Pros | Cons |
|--------|------|------|
| Kafka | Throughput, log retention | Ops complexity, team skill gap |
| RabbitMQ | Team familiarity, routing | Lower throughput ceiling |

Skip MADR ceremony for obvious choices — "use HTTPS" does not need a workshop.

## Linking code and ADRs

Reference ADR in commit message: `Implement read replica routing (ADR-0007)`. Code search finds rationale. ADR links to spike branch or proof-of-concept PR. When implementation diverges from ADR consequences, supersede the ADR — do not let docs lie.

## Superseding without deleting

Mark status **Superseded by [ADR-0012](adr/0012-eventbridge.md)** — never delete old ADRs. History explains why you left Postgres-only for read replicas and prevents new hires from relitigating settled tradeoffs without context. Status values: Proposed, Accepted, Deprecated, Superseded.

## Avoiding the ADR graveyard

- Name real alternatives you rejected — "we considered Mongo" without why it lost is useless
- Record **measurable** consequences ("expect 20ms added latency on read path")
- Review ADRs in quarterly architecture sync — supersede when reality diverged
- Assign owner in ADR header — orphaned Proposed ADRs older than 30 days get accepted or rejected in sync

## Tools: adr-tools, Log4brains, or plain markdown

`adr new "Use Redis for session store"` scaffolds files in `doc/adr/`. Log4brains builds static site from ADR folder for internal publishing. Plain markdown in `docs/adr/` works — tooling is optional; git history is mandatory.

## Team topology and ADRs

When Team Topologies stream-aligned teams own services, ADRs at service repo level beat central architecture committee queue. Platform team publishes ADRs for paved road choices; product teams ADR local deviations with platform review.

## Relationship to RFCs and design docs

RFCs explore problem space before decision; ADR records outcome. Spike code belongs linked from ADR, not pasted inline. Design docs for one feature are not ADRs — ADRs capture durable constraints affecting multiple features.

## Anti-patterns

- ADRs written only for audit checkbox after implementation shipped
- Generic consequences ("better scalability") without numbers or tradeoff honesty
- Storing ADRs only in Confluence — drifts from code, dies on tool migration
- Endless Proposed status — ambiguous decisions hurt more than wrong accepted ones

## Example consequence honesty

Bad: "Improves performance." Good: "Cuts p95 read latency from 80ms to 35ms in load test; adds 15ms write latency due to synchronous replication; ops must monitor replication lag alert."

ADRs are organizational memory with git blame — cheap to write, expensive to omit when the architect leaves and the bus factor hits one.

## ADR review in architecture sync

Monthly or quarterly sync agenda item: list Proposed ADRs older than 30 days — accept, reject, or request revision. Rejected ADRs get status Rejected with reason — prevents zombie proposals.

## Integrating with RFC process

Large initiatives: RFC explores options (2 pages), ADR records decision (1 page), implementation follows. RFC comments inform ADR Context section — link RFC PR in ADR header.

## Measuring ADR effectiveness

Qualitative signal: new hires stop asking "why Kafka" in Slack — they read ADR-0004. Quantitative: count repeated architecture debates in meeting notes — should decrease for documented decisions.

## Security-sensitive decisions

Auth model, encryption, and data residency choices always get ADRs — audit trail for compliance questions. Link to threat model diagram when security ADR references trust boundaries.

## Platform team ADR catalog

Platform publishes ADRs for org-wide defaults (Kubernetes ingress, observability stack). Product teams reference platform ADRs in local ADRs: "Conforms to ADR-PLAT-003 logging standard."

## Localization for global teams

ADRs written in English with glossary for domain terms — translate summary bullets for regional engineering leads if language barrier blocks adoption. Full ADR translation rarely worth cost.

Architecture Decision Records work when they are short, honest, versioned beside code, and reviewed like production changes — shelfware ADRs in Confluence nobody reads are worse than no ADRs because they create false confidence.
"""

FULL["software-cqrs-event-sourcing-tradeoffs"] = r"""The conference talk showed event sourcing like default architecture — every button click an immutable fact, read models materializing like magic. Six months later the team debugged why inventory projection lagged checkout by four minutes during peak. CQRS (Command Query Responsibility Segregation) and event sourcing solve specific pains: asymmetric read/write load, audit trails, and temporal reconstruction. They also introduce dual models, eventual consistency, and replay machinery. Use them when the business value exceeds the tax — not because DDD blogs said so.

## CQRS without event sourcing

```
Command → Write model (normalized DB)
              ↓ publish domain event
         Read model (denormalized Elasticsearch)
Query ← Read model only
```

Writes optimize for invariants; reads optimize for UI screens. Accept eventual consistency between models — display "processing" states honestly. You do **not** need an event store to separate read and write schemas — many teams publish domain events from CRUD writes without storing events as source of truth.

## Event sourcing core loop

```python
def handle(cmd: PlaceOrder):
    order = Order.create(cmd)
    events = order.pull_uncommitted_events()
    event_store.append(stream_id=order.id, events=events)
    publish(events)
```

State equals fold(events). Snapshots optional for long streams — rebuild aggregate from snapshot plus events after snapshot version.

## When the tradeoff favors ES/CQRS

| Signal | Fit |
|--------|-----|
| Regulatory audit of every change | Strong |
| Multiple read views same writes | Strong |
| Complex domain with rich behavior | Moderate |
| Simple CRUD admin | Weak |
| Strong immediate read-your-writes everywhere | Weak |

## Projection rebuild operations

Bug in projector? Fix code, reset checkpoint, replay from offset — or rebuild read DB from scratch. Automate replay in staging on every release. Document RPO for projection lag; alert when lag exceeds business tolerance (inventory display stale while warehouse knows truth).

Full replay duration estimate belongs in runbook — "8 hours for 400M events" changes on-call response when projector corrupts.

## Command handling idempotency

Commands carry `command_id`; dedupe at aggregate level. Retries are normal with at-least-once messaging. Without idempotency, duplicate `PlaceOrder` commands double-charge or double-ship.

## Schema evolution and upcasting

Event schema version 3 must upcast versions 1 and 2 during replay. Store event type name and version in envelope; upcasters are code you maintain forever. Breaking changes without upcasters brick replay — treat event schemas like public API.

## When CQRS is overkill

CRUD with one read model and moderate traffic rarely needs event sourcing complexity. CQRS pays off when read and write shapes diverge sharply, audit history is mandatory, or temporal queries ("balance as of date") are core requirements.

## Avoid distributed monolith

CQRS across fourteen microservices without bounded context discipline creates chatty command buses. Start modular monolith with in-process handlers; extract when scaling proves need. Every network hop adds failure modes — do not pay the tax before load requires it.

## Hybrid path

Event source **Order** aggregate only; **Customer** stays CRUD. Not every table earns a stream. Choose per aggregate based on audit and projection needs, not globally.

## Read model eventual consistency UX

Users who submit form expect immediate feedback — write model confirms; read model may lag milliseconds to seconds. Show "confirmed" from write response; do not read-your-writes from Elasticsearch if lag exists unless synchronously updated cache layer handles it.

## Event store backup and replay testing

Event store is critical infrastructure — backup like primary database. Quarterly restore drill replays into empty projection environment and compares checksums to production read models.

## Operational metrics

Monitor: projection lag histogram, replay queue depth, command handler error rate, event store append latency. Page on lag SLO breach before users see stale dashboards.

CQRS and event sourcing are powerful where history, audit, and read/write asymmetry dominate — expensive everywhere else. Start with one aggregate, prove replay and projection ops, then expand.

## Saga versus event sourcing

Distributed sagas orchestrate commands across services with compensations — different from event sourcing within one aggregate. Teams confuse them — saga state machines can use event sourcing internally, but not every saga step needs global event store.

## Testing projections

Golden file tests: given event sequence fixture, assert read model output JSON. Run in CI on every projector change. Property-based tests generate random valid event sequences and assert invariants (balance never negative).

## Debugging production with event replay

Replay production events into staging projector sandbox to reproduce bug without touching production read DB. Mask PII in event export — GDPR limits full replay to sanitized subsets.

## Cost of event storage

Event store storage grows unbounded — snapshot aggregates and archive cold streams to object storage with retention policy. Billing team needs storage growth projection before signing multi-year event sourcing commitment.

## Team skill requirements

Event sourcing requires developers comfortable with async messaging, idempotency, and versioned schemas — plan training budget. CRUD teams forced into ES without coaching produce anemic events (`OrderUpdated` with full DTO dump).

## Comparison to change data capture

CDC from database binlog projects read models without event sourcing write path — valid CQRS shortcut when write model stays relational. Tradeoff: events reflect row changes, not domain intent — audit narrative weaker.

Choose CQRS and event sourcing when the business pays for auditability and projection flexibility — not because your conference badge says DDD.
"""

FULL["software-domain-driven-design-strategic"] = r"""Every team called it "the account" but Billing meant ledger identity, CRM meant sales prospect, and Auth meant login credential — one database table, three incompatible mental models. Strategic Domain-Driven Design does not start with entities and repositories; it starts with linguistics and boundaries. Bounded contexts delimit where terms mean one thing; context maps show how contexts relate without pretending one unified enterprise model exists.

## Ubiquitous language

Product, engineering, and domain experts share vocabulary in workshops:

- **Policy** (Insurance): contract terms, not IAM policy
- **Quote** (Sales): priced offer, not string literal

Code names match speech: `IssuePolicyCommand`, not `ProcessDataRequest`. Glossary wiki maintained by product — engineers propose PRs when terms shift.

## Subdomain classification

```
Core:        underwriting rules engine
Supporting:  agent commission calculation
Generic:     payment capture (Stripe)
```

Invest modeling depth proportional to classification. Do not build custom payment kernel when Stripe is generic subdomain — your competitive advantage lives in underwriting, not PCI scope.

## Drawing bounded contexts

Start messy on whiteboard — refine to modules:

```
[Quoting] --ACL--> [Legacy Rating Engine]
[Policy Admin] --events--> [Billing]
[Claims] customer-supplier [Policy Admin]
```

Relationships dictate integration style: Anti-Corruption Layer for legacy, published language for stable APIs, conformist when upstream owns the model and you adapt.

## Context map workshops

Run event storming quarterly with product and engineering. Orange stickies (domain events), blue (commands), yellow (aggregates). Pink stickies (conflicts) often mark context boundaries. Update context map when org restructures — stale maps mislead new architects more than no map.

## Team alignment and Conway's law

One team per context where possible. Two teams one context breeds model schism — merge conflicts in ubiquitous language, incompatible shortcuts. Temporary shared ownership needs explicit governance and merge cadence for glossary.

## Evolution from monolith

Modular monolith enforces package-private boundaries between contexts before network boundaries. ArchUnit or custom lint: `@Deprecated crossContext` for illegal imports from quoting into billing internals. Extract microservice when scaling or team boundary proves need — not as day-one default.

## Anti-pattern: unified canonical model

Enterprise data model committees shipping XSD for all divisions move pain to integration without solving semantic mismatch. Prefer explicit translation at edges via ACL over one true `Customer` table with forty nullable columns.

## Core vs supporting investment

Core subdomain gets best engineers and rich models; supporting gets adequate quality; generic gets buy or thin adapter. Roadmap arguments reference subdomain map — "that feature is generic email, use SendGrid" ends debate.

## When to skip heavy DDD

Small product with one clear domain — over-partitioning contexts adds meetings without reducing bugs. Revisit when onboarding confusion or cross-team integration defects spike.

## Context map in repo

Store `docs/context-map.md` or PNG from workshop with date and attendees. Link from README. New service proposals reference which contexts they touch — architecture review starts from map, not blank whiteboard.

Strategic DDD aligns language, boundaries, and teams before tactical patterns — entities and repositories mean little if "customer" still means three different things in one standup.

## Partnership patterns on context maps

**Customer-supplier:** downstream context depends on upstream roadmap — negotiate SLAs for API changes. **Conformist:** downstream accepts upstream model wholesale — use when upstream is external vendor. **Open host service:** publish language with documentation — internal platform pattern.

## Physical versus logical boundaries

Bounded contexts start logical — separate packages in monolith. Physical separation (services) comes later when scaling or team boundaries require independent deploy. Premature service extraction without context clarity multiplies translation bugs.

## Event storming facilitation tips

Timebox 90 minutes; invite product owner and senior engineer minimum. Start with domain event stickies left-to-right timeline. Identify aggregates where commands attach. End with candidate context boundaries — do not force final map in one session.

## Legacy system ACL placement

Every legacy integration gets Anti-Corruption Layer at boundary — never leak legacy field names (`CUST_NBR`) into core domain. ACL team owns translation tests when legacy releases change.

## Measuring DDD adoption success

Fewer cross-team bugs on integration contracts. Faster onboarding when glossary answers "what is a policy." Reduced nullable-column tables — bounded contexts split schemas. Qualitative survey after six months.

## Relationship to microservices

Microservice per bounded context is idealized — practical systems share databases during migration. Context map still valuable when services share Postgres schema with schema-per-context naming discipline.

Strategic DDD is a communication and alignment tool first — code structure follows once language and boundaries stabilize across product and engineering.
"""
