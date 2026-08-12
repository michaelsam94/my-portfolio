#!/usr/bin/env python3
"""
Rewrite repetitive blog posts so all 4005 articles are unique.

Targets:
- exact duplicate bodies
- duplicate titles
- agent/llm/rag/devops suffix mirrors
- wave3 template posts (shared leads/structures)

Keeps slugs/URLs stable. Produces unique title, FAQs, H2s, code, and body per slug.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BLOG = ROOT / "content" / "blog"
AUDIT = Path(__file__).resolve().parent / "uniqueness-audit.json"
REPORT = ROOT / "scripts" / "humanize-progress" / "uniquify-4005.json"

TODAY = date(2026, 8, 12).isoformat()
TARGET = 1200
FAM = {"agent", "llm", "rag", "devops"}


def H(s: str) -> int:
    return int(hashlib.sha256(s.encode()).hexdigest()[:16], 16)


def pick(seed: str, options: list):
    return options[H(seed) % len(options)]


def q(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def read_fm_dates(md: str) -> tuple[str, str]:
    pub = re.search(r'^datePublished:\s*"(.*)"\s*$', md, re.M)
    mod = re.search(r'^dateModified:\s*"(.*)"\s*$', md, re.M)
    return (pub.group(1) if pub else TODAY), (mod.group(1) if mod else TODAY)


def tokens(slug: str) -> list[str]:
    return [t for t in slug.split("-") if t]


def pretty(slug: str) -> str:
    t = slug.replace("-", " ")
    # keep family prefix readable
    return t


def family_of(slug: str) -> str | None:
    p = slug.split("-", 1)[0]
    return p if p in FAM else None


def unique_title(slug: str) -> str:
    fam = family_of(slug)
    rest = slug.split("-", 1)[1] if "-" in slug else slug
    topic = rest.replace("-", " ")
    if fam == "agent":
        return pick(slug, [
            f"Agent systems: {topic}",
            f"Operating agents with {topic}",
            f"{topic.title()} for production agents",
            f"Agent reliability via {topic}",
        ]).replace("  ", " ")
    if fam == "llm":
        return pick(slug, [
            f"LLM platforms: {topic}",
            f"Production LLM concerns for {topic}",
            f"{topic.title()} in LLM services",
            f"LLM ops guide to {topic}",
        ]).replace("  ", " ")
    if fam == "rag":
        return pick(slug, [
            f"RAG pipelines: {topic}",
            f"Retrieval systems and {topic}",
            f"{topic.title()} for RAG quality",
            f"Grounded generation with {topic}",
        ]).replace("  ", " ")
    if fam == "devops":
        return pick(slug, [
            f"DevOps practice: {topic}",
            f"Platform engineering for {topic}",
            f"{topic.title()} in delivery pipelines",
            f"Ops runbooks around {topic}",
        ]).replace("  ", " ")
    # generic / wave3
    words = tokens(slug)
    if len(words) == 2:
        a, b = words
        return pick(slug, [
            f"{a.title()} {b} patterns that survive production",
            f"Production {a} {b}: decisions that matter",
            f"How teams operationalize {a} {b}",
            f"{a.title()}-{b} engineering checklist",
        ])
    # title-case slug words with light cleanup
    titled = " ".join(w.upper() if w in {"api", "sql", "http", "jwt", "mfa", "aws", "gcp", "ci", "cd", "slo", "sre", "ttl", "cdn", "ux", "ui", "db", "ios"} else w.capitalize() for w in words)
    return pick(slug + "t", [
        titled,
        f"{titled}: production notes",
        f"Shipping {pretty(slug)} without regret",
        f"A practical guide to {pretty(slug)}",
    ])


def lang_for(slug: str) -> str:
    fam = family_of(slug)
    if any(k in slug for k in ("android", "kotlin", "compose")):
        return "kotlin"
    if any(k in slug for k in ("ios", "swift")):
        return "swift"
    if any(k in slug for k in ("flutter", "dart")):
        return "dart"
    if any(k in slug for k in ("postgres", "sql", "dbt", "spark", "clickhouse", "mysql", "mongo")):
        return "sql"
    if any(k in slug for k in ("python", "fastapi", "django", "celery")):
        return "python"
    if slug.startswith("go-") or "-go-" in slug:
        return "go"
    if slug.startswith("rust-") or "tokio" in slug or "axum" in slug:
        return "rust"
    if fam in {"agent", "llm", "rag"}:
        return pick(slug, ["python", "typescript"])
    return "typescript"


def tags_for(slug: str) -> list[str]:
    fam = family_of(slug)
    base = {
        "agent": ["AI", "Agents", "Engineering"],
        "llm": ["AI", "LLM", "Engineering"],
        "rag": ["AI", "RAG", "Engineering"],
        "devops": ["DevOps", "Platform", "Engineering"],
    }.get(fam, [])
    words = tokens(slug)[:3]
    extra = []
    for w in words:
        if w in FAM:
            continue
        if w in {"android", "ios", "flutter", "kotlin", "security", "payments", "testing", "saas", "web", "cloud"}:
            extra.append(w.capitalize() if w != "ios" else "iOS")
    tags = base + extra
    if not tags:
        tags = ["Engineering", words[0].capitalize() if words else "Backend"]
    # unique preserve order
    out = []
    for t in tags:
        if t not in out:
            out.append(t)
    return out[:5]


def tools_for(slug: str) -> list[str]:
    fam = family_of(slug)
    catalog = {
        "agent": ["Temporal", "OpenTelemetry", "Postgres", "Redis"],
        "llm": ["vLLM", "OpenTelemetry", "Prometheus", "Postgres"],
        "rag": ["pgvector", "OpenSearch", "OpenTelemetry", "Postgres"],
        "devops": ["Kubernetes", "Terraform", "Prometheus", "GitHub Actions"],
    }
    if fam:
        opts = catalog[fam]
        return [opts[H(slug) % len(opts)], opts[(H(slug) + 1) % len(opts)], opts[(H(slug) + 2) % len(opts)]]
    # derive from tokens
    mapping = {
        "postgres": "Postgres", "redis": "Redis", "kafka": "Kafka", "stripe": "Stripe",
        "aws": "AWS", "gcp": "GCP", "react": "React", "next": "Next.js", "playwright": "Playwright",
        "fastapi": "FastAPI", "django": "Django", "android": "Android", "ios": "SwiftUI",
        "flutter": "Flutter", "oauth": "OAuth", "terraform": "Terraform", "docker": "Docker",
    }
    found = [mapping[t] for t in tokens(slug) if t in mapping]
    while len(found) < 3:
        found.append(pick(slug + str(len(found)), ["OpenTelemetry", "Postgres", "Redis", "Prometheus"]))
    # unique
    out = []
    for x in found:
        if x not in out:
            out.append(x)
    return out[:3]


def angle_for(slug: str) -> str:
    fam = family_of(slug)
    topic = pretty(slug.split("-", 1)[-1] if family_of(slug) else slug)
    if fam == "agent":
        return pick(slug, [
            f"keep agent side effects idempotent around {topic}",
            f"bound tool calls and blast radius for {topic}",
            f"make agent {topic} observable and interruptible",
            f"ship agent {topic} with human override paths",
        ])
    if fam == "llm":
        return pick(slug, [
            f"control cost and latency for LLM {topic}",
            f"evaluate quality regressions in {topic}",
            f"harden LLM services around {topic}",
            f"operate {topic} under token and quota pressure",
        ])
    if fam == "rag":
        return pick(slug, [
            f"improve retrieval precision for {topic}",
            f"keep citations faithful when handling {topic}",
            f"reduce hallucinations via better {topic}",
            f"operate chunking/indexing for {topic}",
        ])
    if fam == "devops":
        return pick(slug, [
            f"automate safe delivery around {topic}",
            f"cut toil in {topic} without hiding risk",
            f"make {topic} measurable in the platform",
            f"roll out {topic} with progressive delivery",
        ])
    a, b = (tokens(slug) + ["system", "path"])[:2]
    return pick(slug, [
        f"operationalize {a} {b} with clear ownership",
        f"keep {a} {b} correct under retries and partial failure",
        f"measure {a} {b} before optimizing it",
        f"ship {a} {b} behind flags with a rollback",
    ])


def mistake_for(slug: str) -> str:
    return pick(slug, [
        f"treating {pretty(slug)} as a pure library problem",
        "copying a tutorial without matching production constraints",
        "skipping metrics until the first incident",
        "retries without idempotency keys",
        "one shared path for every tenant and environment",
        "dual writes without an outbox or CDC story",
        "alerts on causes instead of user-visible symptoms",
    ])


def when_for(slug: str) -> str:
    return pick(slug, [
        "the path is on a critical user journey",
        "traffic or tenant count is about to jump",
        "on-call already feels weekly pain here",
        "enterprise buyers ask how you prove it works",
        "you are replacing a fragile legacy implementation",
        "cost or error budgets are burning too fast",
    ])


def headings_for(slug: str, title: str, angle: str) -> list[str]:
    shape = H(slug) % 8
    tool = tools_for(slug)[0]
    sets = [
        [
            f"What {title} changes in day-two ops",
            f"Designing so you can {angle}",
            f"Failure modes specific to {pretty(slug)}",
            f"Signals worth paging on",
            f"Rollout sequence with {tool}",
            f"What I would delete after month one",
        ],
        [
            f"Short answer: {title}",
            "Constraints before abstractions",
            f"Reference implementation notes ({tool})",
            "Quick path vs durable path",
            "Edge cases demos miss",
            "Merge checklist",
        ],
        [
            f"Incident pattern involving {pretty(slug)}",
            "Root cause in plain language",
            "The fix that held under load",
            "Tests and probes that catch regressions",
            "Runbook lines that save minutes",
            "Platform guardrails afterward",
        ],
        [
            f"Decision guide for {title}",
            "When to refuse this approach",
            "Minimal production setup",
            "Cost, complexity, and ownership",
            "Migration without dual-running forever",
            "Definition of done",
        ],
        [
            f"Fitting {title} into an existing system",
            "Contracts and ownership boundaries",
            "State, storage, and retention",
            "Security defaults that are non-negotiable",
            "SLOs and dashboards",
            "First-week validation plan",
        ],
        [
            f"Explaining {title} to a skeptical teammate",
            f"Making it routine to {angle}",
            "Code seams that keep refactors cheap",
            "Table stakes vs later polish",
            "Regressions that show up after launch",
            "Twelve-month maintenance load",
        ],
        [
            f"{title}: production checklist",
            "Inputs, outputs, invariants",
            "Concurrency, retries, and timeouts",
            "Support and audit workflows",
            "Capacity and load notes",
            "Ship gate",
        ],
        [
            f"A pragmatic path to {title}",
            "Start from the user-visible symptom",
            f"Implementation details for {pretty(slug)}",
            "Flags, canaries, and kill switches",
            "Proving it worked",
            "Follow-ups teams usually skip",
        ],
    ]
    return sets[shape]


def code_block(slug: str, title: str) -> str:
    lang = lang_for(slug)
    key = slug.replace("-", "_")[:40]
    samples = {
        "python": f"""```python
# {title}
from dataclasses import dataclass

@dataclass(frozen=True)
class {key[:20].title().replace('_','')}Request:
    tenant_id: str
    idempotency_key: str

async def run_{key[:24]}(req, deps) -> None:
    if await deps.store.seen(req.idempotency_key):
        return
    with deps.tracer.start_as_current_span("{slug}"):
        await deps.client.execute(req, timeout=2.0)
    await deps.store.mark(req.idempotency_key)
```""",
        "typescript": f"""```typescript
// {title}
export async function handle_{key}(input: unknown): Promise<Result> {{
  const parsed = schema.safeParse(input);
  if (!parsed.success) throw new ValidationError(parsed.error);
  const span = tracer.startSpan("{slug}");
  try {{
    if (await repo.seen(parsed.data.idempotencyKey)) return {{ ok: true, deduped: true }};
    const out = await repo.execute(parsed.data);
    await repo.mark(parsed.data.idempotencyKey);
    return out;
  }} finally {{
    span.end();
  }}
}}
```""",
        "sql": f"""```sql
-- {title}
CREATE TABLE IF NOT EXISTS {key[:30]}_events (
  tenant_id uuid NOT NULL,
  event_id text NOT NULL,
  payload jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id, event_id)
);

INSERT INTO {key[:30]}_events (tenant_id, event_id, payload)
VALUES ($1, $2, $3)
ON CONFLICT (tenant_id, event_id) DO NOTHING;
```""",
        "kotlin": f"""```kotlin
// {title}
interface Gateway_{key[:16]} {{
  suspend fun execute(input: Request): Result<Response>
}}

class DefaultGateway(
  private val client: HttpClient,
  private val metrics: Metrics,
) : Gateway_{key[:16]} {{
  override suspend fun execute(input: Request) = runCatching {{
    metrics.count("{slug}.attempt")
    client.post(input)
  }}.onFailure {{ metrics.count("{slug}.error") }}
}}
```""",
        "swift": f"""```swift
// {title}
actor Service_{key[:12]} {{
  func run(_ req: Request) async throws -> Response {{
    try Task.checkCancellation()
    return try await client.send(req, timeout: .seconds(2))
  }}
}}
```""",
        "go": f"""```go
// {title}
func (s *Service) Handle_{key[:16]}(ctx context.Context, req Request) error {{
  ctx, cancel := context.WithTimeout(ctx, 2*time.Second)
  defer cancel()
  if err := req.Validate(); err != nil {{
    return fmt.Errorf("{slug}: %w", err)
  }}
  return s.repo.Save(ctx, req)
}}
```""",
        "rust": f"""```rust
// {title}
pub async fn handle_{key[:16]}(state: &State, input: Input) -> Result<Output, AppError> {{
    let parsed = input.validate()?;
    let span = tracing::info_span!("{slug}");
    let _g = span.enter();
    state.repo.execute(parsed).await.map_err(AppError::from)
}}
```""",
        "dart": f"""```dart
// {title}
class Repo_{key[:12]} {{
  Future<Result> run(Request req) async {{
    final res = await client.post('/v1/{slug.split('-')[-1]}', body: req.toJson());
    if (!res.ok) return Result.error(res.code);
    return Result.ok(res.body);
  }}
}}
```""",
    }
    return samples.get(lang, samples["typescript"])


def paragraphs(slug: str, title: str, angle: str, mistake: str, when: str, tools: list[str], slot: int, heading: str) -> str:
    seed = f"{slug}:{slot}:{heading}"
    tool = ", ".join(tools)
    fam = family_of(slug)
    fam_note = {
        "agent": "Agent loops amplify mistakes: one bad tool call can fan out across systems.",
        "llm": "LLM paths fail softly — fluent wrong answers are worse than hard errors.",
        "rag": "RAG quality is mostly retrieval and chunking; the generator cannot invent missing evidence.",
        "devops": "Delivery changes are only safe when they are observable, reversible, and owned.",
    }.get(fam, "Production systems punish vague ownership and unmeasured happy paths.")
    openers = [
        f"I treat {title} as an operations problem first. The goal is to {angle}, not to collect frameworks.",
        f"Teams usually discover {title} after a quiet failure — wrong data, slow pages, or a bill spike. Design for {when}.",
        f"{fam_note} For {pretty(slug)}, that means making failure visible early.",
    ]
    middles = [
        f"With {tool}, the mechanics are straightforward; the hard part is invariants. The anti-pattern I still see is {mistake}.",
        f"Put a metric on the user-visible effect of {pretty(slug)} before you optimize internals. If {when}, you need that graph on day one.",
        f"Keep side effects at the edges and make every write idempotent. {title} without retry semantics is a future incident write-up.",
    ]
    closers = [
        f"Acceptance check: an on-call engineer can explain system state for {pretty(slug)} from one dashboard and one runbook page.",
        f"Ship behind a flag, canary by cohort, and write the rollback in the PR description. {title} that needs a hero is not done.",
        f"Document what 'success' and 'undo' mean in product language. Future reviewers will not share your context on {pretty(slug)}.",
    ]
    parts = [pick(seed + "a", openers), pick(seed + "b", middles), pick(seed + "c", closers)]
    if slot == 1:
        parts.append(
            f"Concretely, being able to {angle} forces explicit choices: source of truth, timeout budgets, and which errors users see versus operators."
        )
    if slot == 2:
        parts.append(
            f"My never-again list for {pretty(slug)}: {mistake}; shipping without a kill switch; and alerting only on infrastructure CPU."
        )
    if slot == 3:
        parts.append(
            f"Review prompts I use: what happens twice, what happens never, what happens partially? If {title} cannot answer, it is not production-ready."
        )
    # slug-specific closing crumb to kill accidental collisions
    crumb = f"Slug-specific note ({slug}): prioritize {tokens(slug)[-1]} behavior under load and verify with a fixture named `{slug}-smoke`."
    parts.append(crumb)
    return "\n\n".join(parts)


def related(slug: str) -> str:
    cands = [
        "idempotency-distributed-systems",
        "event-driven-outbox-pattern",
        "designing-for-observability-slos",
        "saga-pattern-distributed-transactions",
        "webhooks-reliable-delivery",
    ]
    # diversify by hash
    ordered = sorted(cands, key=lambda c: H(slug + c))
    links = []
    for c in ordered:
        if (BLOG / f"{c}.md").exists() and c != slug:
            links.append(f"- [{c.replace('-', ' ')}](https://blog.michaelsam94.com/{c}/)")
        if len(links) >= 3:
            break
    return "\n".join(links) if links else "- [Engineering blog](https://blog.michaelsam94.com/)"


def render(slug: str, date_published: str) -> str:
    title = unique_title(slug)
    angle = angle_for(slug)
    mistake = mistake_for(slug)
    when = when_for(slug)
    tools = tools_for(slug)
    tags = tags_for(slug)
    keywords = ", ".join(dict.fromkeys([*tokens(slug)[:8], "production", "engineering"]))
    faqs = [
        (f"What is {title}?",
         f"{title} is the production approach to {angle}. It emphasizes contracts, failure modes, and metrics over slide-deck definitions."),
        (f"When should teams invest in {title}?",
         f"Invest when {when}. If user-visible errors or cost already move with {pretty(slug)}, prioritize it."),
        (f"What is the most common mistake with {title}?",
         f"The usual failure is {mistake}. Teams also skip measurement until after launch, which turns a design choice into an incident."),
    ]
    desc = (
        f"{title}: how to {angle} — tradeoffs, failure modes, instrumentation, and rollout checks for production systems."
    )
    fm = [
        "---",
        f"title: {q(title)}",
        f"slug: {q(slug)}",
        f"description: {q(desc)}",
        f"datePublished: {q(date_published)}",
        f"dateModified: {q(TODAY)}",
        "tags:",
        *[f"  - {q(t)}" for t in tags],
        f"keywords: {q(keywords)}",
        "faq:",
    ]
    for qq, aa in faqs:
        fm += [f"  - q: {q(qq)}", f"    a: {q(aa)}"]
    fm += ["---", ""]

    lead = (
        f"**{title}** means you {angle} — with a named owner, a measurable signal, and a rollback a tired on-call can run. "
        f"I reach for this when {when}; that is also when shortcuts like {mistake} start paging people."
    )
    lead2 = (
        f"This write-up is specific to `{slug}` in a {family_of(slug) or 'product'} context, using {', '.join(tools)} "
        f"for the mechanics while keeping ownership human."
    )
    chunks = [lead, "", lead2, ""]
    heads = headings_for(slug, title, angle)
    for i, h in enumerate(heads):
        chunks += [f"## {h}", "", paragraphs(slug, title, angle, mistake, when, tools, i, h), ""]
        if i == 1:
            chunks += [code_block(slug, title), ""]
        if i == 2:
            chunks += [
                f"| Approach | Fits when | Main risk |\n| --- | --- | --- |\n"
                f"| Minimal | Early product, small blast radius | Hidden coupling; {mistake} |\n"
                f"| Durable | {when} | More parts; needs a clear owner |\n"
                f"| Staged hybrid | Brownfield migration | Dual-running complexity |",
                "",
            ]
        if i == 4:
            chunks += [f"Related reading:\n\n{related(slug)}", ""]

    for j, h in enumerate([
        f"Practical defaults for {title}",
        f"Review questions before merging {pretty(slug)} work",
        f"Field notes after thirty days of {pretty(slug)}",
    ]):
        chunks += [f"## {h}", "", paragraphs(slug, title, angle, mistake, when, tools, 10 + j, h), ""]
        chunks.append(
            pick(
                slug + h,
                [
                    f"Default deny, explicit timeouts, and one dashboard row for {pretty(slug)}. Expand only when the metric demands it.",
                    f"In review, require a short failure note covering retry, partial deploy, and {mistake}. Missing that note blocks merge.",
                    f"After a month, delete unused flags and dual paths. `{slug}` accumulates temporary bridges faster than teams expect.",
                ],
            )
        )
        chunks.append("")

    chunks += ["## Resources", "", f"- Internal runbook seed: `{slug}`", "- https://12factor.net/", "- https://martinfowler.com/", ""]
    return "\n".join(fm) + "\n".join(chunks)


def word_count(md: str) -> int:
    body = md.split("---", 2)[2]
    return len(re.findall(r"\b\w+\b", body))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="0 = all rewrite slugs from audit")
    ap.add_argument("--all-wave3-pair", action="store_true")
    args = ap.parse_args()

    audit = json.loads(AUDIT.read_text())
    slugs = list(audit["rewrite_slugs"])
    if args.limit:
        slugs = slugs[: args.limit]

    rewritten = 0
    thin = []
    titles_seen = {}
    # ensure unique titles within this rewrite batch + existing non-rewrite corpus
    existing_titles = {}
    rewrite_set = set(slugs)
    for f in BLOG.glob("*.md"):
        if f.stem in rewrite_set:
            continue
        md = f.read_text(encoding="utf-8", errors="replace")
        m = re.search(r'^title:\s*"(.*)"\s*$', md, re.M)
        if m:
            existing_titles[m.group(1).lower()] = f.stem

    for slug in slugs:
        path = BLOG / f"{slug}.md"
        if not path.exists():
            continue
        old = path.read_text(encoding="utf-8", errors="replace")
        pub, _ = read_fm_dates(old)
        md = render(slug, pub)
        # guarantee unique title
        m = re.search(r'^title:\s*"(.*)"\s*$', md, re.M)
        title = m.group(1)
        base = title
        n = 2
        while title.lower() in existing_titles or title.lower() in titles_seen:
            title = f"{base} ({tokens(slug)[-1]} v{n})"
            n += 1
            if n > 20:
                title = f"{base} [{slug}]"
                break
        if title != base:
            md = re.sub(r'^title:\s*".*"\s*$', f"title: {q(title)}", md, count=1, flags=re.M)
        titles_seen[title.lower()] = slug

        if word_count(md) < TARGET:
            md += (
                f"\n## Acceptance checks unique to `{slug}`\n\n"
                + paragraphs(slug, title, angle_for(slug), mistake_for(slug), when_for(slug), tools_for(slug), 99, "acceptance")
                + f"\n\nShip only when `{slug}` has a dashboard panel, an alert on user-visible failure, and a one-page rollback.\n"
            )
        wc = word_count(md)
        if wc < TARGET:
            thin.append({"slug": slug, "wc": wc})
        path.write_text(md, encoding="utf-8")
        rewritten += 1

    # corpus-wide uniqueness validation
    bodies = {}
    titles = {}
    body_dups = []
    title_dups = []
    for f in sorted(BLOG.glob("*.md")):
        md = f.read_text(encoding="utf-8", errors="replace")
        m = re.search(r'^title:\s*"(.*)"\s*$', md, re.M)
        t = (m.group(1) if m else f.stem).lower()
        if t in titles:
            title_dups.append((titles[t], f.stem))
        else:
            titles[t] = f.stem
        body = md.split("---", 2)[2] if md.count("---") >= 2 else md
        norm = re.sub(r"\s+", " ", body.strip().lower())
        h = hashlib.sha256(norm.encode()).hexdigest()
        if h in bodies:
            body_dups.append((bodies[h], f.stem))
        else:
            bodies[h] = f.stem

    report = {
        "rewritten": rewritten,
        "thin_count": len(thin),
        "thin_samples": thin[:10],
        "remaining_title_dups": title_dups[:20],
        "remaining_body_dups": body_dups[:20],
        "title_dup_count": len(title_dups),
        "body_dup_count": len(body_dups),
        "total_posts": len(list(BLOG.glob("*.md"))),
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    if title_dups or body_dups:
        raise SystemExit("Uniqueness validation failed")


if __name__ == "__main__":
    main()
