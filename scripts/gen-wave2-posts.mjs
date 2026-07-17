#!/usr/bin/env node
/**
 * Generate wave-2 blog posts (≥900 words) from scripts/wave2-topics.json
 * Usage: node scripts/gen-wave2-posts.mjs [--batch N] [--start N] [--limit N] [--dry-run]
 */
import { readFile, writeFile, mkdir, access } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { SPECIFIC, VARIANTS, TERM_GLOSSARY, pick, hash } from "./wave2-content-bank.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const BLOG = path.join(ROOT, "content/blog");
const TOPICS_FILE = path.join(ROOT, "scripts/wave2-topics.json");

const args = process.argv.slice(2);
const force = args.includes("--force");
const dryRun = args.includes("--dry-run");
const batchIdx = args.includes("--batch") ? Number(args[args.indexOf("--batch") + 1]) : null;
const start = args.includes("--start") ? Number(args[args.indexOf("--start") + 1]) : 0;
const limit = args.includes("--limit") ? Number(args[args.indexOf("--limit") + 1]) : Infinity;

const MAX_DATE = new Date("2026-07-17T23:59:59Z");
const START_DATE = new Date("2024-07-01T00:00:00Z");

const RESOURCES = {
  AI: [
    "https://platform.openai.com/docs/",
    "https://python.langchain.com/docs/",
    "https://www.anthropic.com/research",
    "https://huggingface.co/docs",
    "https://arxiv.org/list/cs.AI/recent",
  ],
  Kotlin: [
    "https://kotlinlang.org/docs/home.html",
    "https://developer.android.com/kotlin",
    "https://kotlinlang.org/docs/multiplatform.html",
    "https://github.com/JetBrains/compose-multiplatform",
  ],
  Compose: [
    "https://developer.android.com/jetpack/compose",
    "https://m3.material.io/",
    "https://developer.android.com/develop/ui/compose/performance",
  ],
  Android: [
    "https://developer.android.com/",
    "https://developer.android.com/about/versions",
    "https://source.android.com/docs",
  ],
  Flutter: [
    "https://docs.flutter.dev/",
    "https://api.flutter.dev/",
    "https://dart.dev/guides",
  ],
  Backend: [
    "https://12factor.net/",
    "https://microservices.io/patterns/",
    "https://grpc.io/docs/",
  ],
  Security: [
    "https://owasp.org/www-project-top-ten/",
    "https://cheatsheetseries.owasp.org/",
    "https://cwe.mitre.org/",
  ],
  Web: [
    "https://developer.mozilla.org/",
    "https://web.dev/",
    "https://www.w3.org/WAI/WCAG21/Understanding/",
  ],
  Data: [
    "https://www.postgresql.org/docs/",
    "https://kafka.apache.org/documentation/",
    "https://docs.getdbt.com/",
  ],
  Platform: [
    "https://kubernetes.io/docs/",
    "https://developer.hashicorp.com/terraform/docs",
    "https://opentelemetry.io/docs/",
  ],
  IoT: [
    "https://mqtt.org/",
    "https://www.openchargealliance.org/",
    "https://www.zigbee.org/",
  ],
  default: [
    "https://martinfowler.com/",
    "https://github.com/",
    "https://stackoverflow.com/",
  ],
};

const CATEGORY_CONTEXT = {
  Flutter: { noun: "feature", env: "Flutter/Dart codebase", signal: "frame time, jank, and crash-free sessions" },
  Android: { noun: "module", env: "Android app", signal: "ANRs, cold start, and Play Vitals" },
  Compose: { noun: "surface", env: "Compose UI", signal: "recomposition counts and jank stats" },
  Kotlin: { noun: "module", env: "Kotlin codebase", signal: "build time, test flakiness, and runtime crashes" },
  AI: { noun: "pipeline", env: "LLM/RAG stack", signal: "token cost, latency, and eval scores" },
  Backend: { noun: "service", env: "backend fleet", signal: "error rate, p95 latency, and saturation" },
  Security: { noun: "control", env: "security program", signal: "findings, MTTR, and audit gaps" },
  Web: { noun: "route", env: "web app", signal: "Core Web Vitals and conversion impact" },
  Data: { noun: "pipeline", env: "data platform", signal: "freshness SLAs and query cost" },
  Platform: { noun: "cluster", env: "platform", signal: "SLO burn and toil hours" },
  IoT: { noun: "device fleet", env: "IoT deployment", signal: "connectivity, firmware drift, and telemetry gaps" },
};
const ctxFor = (category) =>
  CATEGORY_CONTEXT[category] ?? { noun: "component", env: category.toLowerCase() + " stack", signal: "error rate and latency" };

const pickTags = (category, slug) => {
  const base = [category];
  const parts = slug.split("-").slice(0, 2);
  for (const p of parts) {
    const tag = p.charAt(0).toUpperCase() + p.slice(1);
    if (!base.includes(tag) && tag.length > 2) base.push(tag);
  }
  return base.slice(0, 5);
};

const staggerDate = (index, total) => {
  const t = index / Math.max(1, total - 1);
  const ms = START_DATE.getTime() + t * (MAX_DATE.getTime() - START_DATE.getTime());
  return new Date(ms).toISOString().slice(0, 10);
};

const faqFor = (title, slug, category) => {
  const subject = title.replace(/^(RAG:|AI Agents:|MCP:|API Design:|Security:|Authentication:|OAuth:|Zero Trust:|React:|Next\.js:|CSS:|TypeScript:|Data Engineering:|PostgreSQL:|Kafka:|Apache Spark:|dbt:|Kubernetes:|Terraform:|Docker:|Observability:|SRE:|IoT:|MQTT:|OCPP:|Edge Computing:|Go:|Rust:|Python:|FastAPI:|Testing:|Software Architecture:|System Design:|iOS:|Swift:|SwiftUI:)\s*/i, "");
  const ctx = ctxFor(category);
  return [
    {
      q: `What is ${subject}?`,
      a: `${subject} covers the engineering practices, APIs, and tradeoffs teams use when implementing this capability in a production ${ctx.env}. It is not a single library call — it is how the ${ctx.noun} behaves under real users, releases, and failure modes.`,
    },
    {
      q: `When should teams prioritize ${subject}?`,
      a: `Prioritize it when ${ctx.signal} show regression, when the feature is on your critical user journey, or when you are about to scale traffic/devices/tenants and the current approach will not survive the load. Defer only if metrics are flat and the code path is genuinely unused.`,
    },
    {
      q: `What are common mistakes with ${subject}?`,
      a: `Copying a tutorial without matching your constraints, skipping measurement until after launch, mixing UI and IO without test seams, and treating edge cases (offline, rotation, permissions) as follow-ups. Another pattern: shipping the demo path without rollback or feature flags.`,
    },
    {
      q: `How does ${subject} fit a modern ${category} stack?`,
      a: `Modern tooling (${ctx.env}) adds automation, but ownership stays human: you still need explicit contracts, tested migrations, and runbooks. ${subject} should be observable in production and safe to change in small diffs.`,
    },
  ];
};

const section = (heading, paragraphs) => `## ${heading}\n\n${paragraphs.join("\n\n")}\n`;

const codeBlock = (lang, code) => `\`\`\`${lang}\n${code}\n\`\`\`\n`;

const glossaryHits = (slug) =>
  Object.entries(TERM_GLOSSARY).filter(([k]) => slug.includes(k.replace(/-/g, "-")));

const bodyFor = (topic, index, total) => {
  const { slug, title, category } = topic;
  const subject = title.replace(/^(RAG:|AI Agents:|MCP:|API Design:|Security:|Authentication:|OAuth:|Zero Trust:|React:|Next\.js:|CSS:|TypeScript:|Data Engineering:|PostgreSQL:|Kafka:|Apache Spark:|dbt:|Kubernetes:|Terraform:|Docker:|Observability:|SRE:|IoT:|MQTT:|OCPP:|Edge Computing:|Go:|Rust:|Python:|FastAPI:|Testing:|Software Architecture:|System Design:|iOS:|Swift:|SwiftUI:)\s*/i, "");
  const kw = slug.replace(/-/g, " ");
  const related = slug.split("-").slice(0, 2).join("-");
  const specific = SPECIFIC[slug];

  const intro = specific?.intro ?? pick(VARIANTS.intro, slug)(subject, category);

  const specificSections = (specific?.sections ?? []).map(({ h, p }) => section(h, p)).join("\n");

  const ctx = ctxFor(category);

  const s1 = section("Problem framing", [
    `When ${subject.toLowerCase()} is underspecified, every ${ctx.noun} team invents a partial fix — inconsistent UX, duplicated platform code, or "works on my device" bugs that explode in production. The symptom on dashboards is usually ${ctx.signal}, but the root cause is missing shared patterns.`,
    `The cost is slower releases and fearful refactors. Engineers re-learn the same platform edges (permissions, lifecycle, threading) on every feature. Product loses predictability because nobody can say what will break when you touch related code.`,
    `Solid ${category} engineering turns ${subject.toLowerCase()} from a recurring argument into a documented pattern with tests and an owner.`,
  ]);

  const s2 = section("Design principles that survive production", [
    `**Explicit contracts.** Whether the boundary is HTTP, gRPC, SQL, or an internal module API, the contract should be machine-checkable and versioned. Ambiguity is where ${kw} bugs hide.`,
    `**Observability first.** Logs, metrics, and traces are not "phase two." If you cannot answer "what happened?" for ${subject.toLowerCase()}, you do not yet understand the behavior you shipped.`,
    `**Fail closed, degrade gracefully.** Authentication, authorization, validation, and quota checks should deny by default. Partial availability beats corrupt state — users forgive slowness more than wrong answers.`,
    `**Idempotency and replay safety.** Networks retry. Users double-click. Jobs re-run. Design ${kw} flows so duplicates are harmless or detectable.`,
  ]);

  const s3 = section("Implementation patterns", [
    `A practical baseline for ${subject.toLowerCase()} in ${category.toLowerCase()} stacks:`,
    `1. **Model the happy path minimally** — ship the smallest flow that satisfies the user story with correct semantics.\n2. **Add failure paths next** — timeouts, retries with jitter, circuit breaking, and compensating actions.\n3. **Instrument before optimizing** — measure p50/p95 latency, error budgets, and saturation; tune from evidence.\n4. **Document operational playbooks** — what to check, what to rollback, who owns downstream dependencies.`,
    `For code structure, keep side effects at the edges and core logic pure where possible. Pure functions are trivial to test; IO at the boundary is trivial to mock. That split makes ${kw} changes safer because business rules stay isolated from transport details.`,
    codeBlock(
      category === "Kotlin" || category === "Android" || category === "Compose" ? "kotlin" : category === "Python" ? "python" : category === "Go" ? "go" : category === "Rust" ? "rust" : "typescript",
      category === "Kotlin" || category === "Android" || category === "Compose"
        ? `// Isolate ${kw} logic for testability\ninterface ${subject.replace(/[^A-Za-z0-9]/g, "")}Gateway {\n  suspend fun execute(input: Request): Result<Response>\n}\n\nclass Default${subject.replace(/[^A-Za-z0-9]/g, "")}Gateway(\n  private val client: HttpClient,\n  private val metrics: Metrics,\n) : ${subject.replace(/[^A-Za-z0-9]/g, "")}Gateway {\n  override suspend fun execute(input: Request): Result<Response> = runCatching {\n    metrics.count(" ${slug}.attempt")\n    client.post("/v1/${slug.split("-").slice(-2).join("-")}") {\n      setBody(input)\n      timeout { request = 2_000 }\n    }.body()\n  }.onFailure { metrics.count("${slug}.error") }\n}`
        : category === "Python"
          ? `# ${subject} — keep domain logic separate from IO\nfrom dataclasses import dataclass\n\n@dataclass(frozen=True)\nclass ${subject.replace(/[^A-Za-z0-9]/g, "")}Request:\n    tenant_id: str\n    payload: dict\n\nclass ${subject.replace(/[^A-Za-z0-9]/g, "")}Service:\n    def __init__(self, repo, clock):\n        self._repo = repo\n        self._clock = clock\n\n    def handle(self, req: ${subject.replace(/[^A-Za-z0-9]/g, "")}Request) -> None:\n        # idempotent write pattern\n        if self._repo.seen(req.tenant_id, req.payload["id"]):\n            return\n        self._repo.save(req)\n`
          : category === "Go"
            ? `// ${subject} with explicit timeouts\ntype ${subject.replace(/[^A-Za-z0-9]/g, "")}Service struct {\n  repo Repository\n  metrics *Metrics\n}\n\nfunc (s *${subject.replace(/[^A-Za-z0-9]/g, "")}Service) Handle(ctx context.Context, req Request) error {\n  ctx, cancel := context.WithTimeout(ctx, 2*time.Second)\n  defer cancel()\n  if err := req.Validate(); err != nil {\n    return fmt.Errorf("${slug}: %w", err)\n  }\n  return s.repo.Save(ctx, req)\n}\n`
            : `// ${subject}: typed boundary + structured errors\nexport async function handle${subject.replace(/[^A-Za-z0-9]/g, "")}(input: Input): Promise<Result> {\n  const parsed = schema.safeParse(input);\n  if (!parsed.success) throw new ValidationError(parsed.error);\n  const span = tracer.startSpan("${slug}");\n  try {\n    return await repo.execute(parsed.data);\n  } finally {\n    span.end();\n  }\n}\n`
    ),
  ]);

  const glossarySection =
    glossaryHits(slug).length > 0
      ? section(
          "Key terms",
          glossaryHits(slug).map(([k, v]) => `**${k.replace(/-/g, " ")}** — ${v}`),
        )
      : "";

  const s4 = section("Operational concerns", [
    pick(VARIANTS.ops, slug + "1")(subject),
    `Production ${kw} work is mostly operability: dashboards, alerts, runbooks, and ownership. Define SLOs that reflect user experience — availability, latency, correctness — not vanity metrics. Alerts should page on symptoms (SLO burn) and ticket on causes (error logs), avoiding noise that trains teams to ignore pages.`,
    `Rollouts for ${subject.toLowerCase()} benefit from progressive delivery: canary by percentage or by tenant cohort, with automatic rollback when error rate or latency regresses beyond thresholds. Pair deploys with feature flags so you can disable logic paths without redeploying.`,
    `Capacity planning ties directly to cost and reliability. Measure peak QPS, payload sizes, fan-out factor, and dependency limits. Load test with production-shaped traffic; synthetic "hello world" tests miss queue backlogs and downstream contention.`,
  ]);

  const s5 = section("Security and compliance angles", [
    `Even when ${subject.toLowerCase()} is not "security software," it participates in your trust boundary. Apply least privilege to service accounts, rotate credentials, and validate all inputs at the trust perimeter. For regulated workloads, maintain an audit trail that answers who changed what, when, and from where.`,
    `Secrets belong in managed stores — not environment variables checked into templates. For PII-adjacent flows, minimize retention and prefer tokenization over copying raw fields. Document data flows for ${kw} so security reviews do not rely on tribal knowledge.`,
  ]);

  const s6 = section("Testing strategy", [
    `Unit tests cover pure logic: validation, mapping, state transitions, and edge cases. Contract tests protect API boundaries that ${subject.toLowerCase()} depends on. Integration tests with real containers — databases, brokers, sandboxes — catch configuration mistakes mocks hide.`,
    `For critical ${category.toLowerCase()} paths, add property-based or fuzz testing where generative input explores weird combinations. Replay production traffic (sanitized) into staging before large refactors. Chaos experiments — dependency latency, partial outages — validate that retries and fallbacks actually work.`,
  ]);

  const s7 = section("Migration and evolution", [
    `Legacy systems rarely block greenfield designs; they constrain sequencing. Strangle ${kw} functionality behind a stable interface, migrate callers incrementally, and delete old paths once traffic drops to zero. Maintain a migration tracker with explicit decommission dates so "temporary" bridges do not ossify.`,
    `Versioning policy should be boring: additive changes only in minor versions, breaking changes only with deprecation windows and communication. Where ${subject.toLowerCase()} spans mobile, web, and backend, coordinate release trains so clients never lead servers into incompatible states.`,
  ]);

  const s8 = section("Related concepts", [
    `${subject} intersects with broader ${category.toLowerCase()} topics — see companion notes on [${related} patterns](https://blog.michaelsam94.com/${related}/) and [production observability](https://blog.michaelsam94.com/designing-for-observability-slos/) when wiring metrics and alerts. Treat those links as adjacent reading, not prerequisites: the goal here is a self-contained operational understanding you can apply without chasing every rabbit hole.`,
  ]);

  const takeaway = section("The takeaway", [
    `${subject} rewards disciplined boring engineering: clear contracts, measurable SLOs, secure defaults, and rollout paths that fail safely. The teams that struggle usually lack visibility or ownership, not intelligence. Start with the user-visible outcome, instrument it, iterate with small diffs, and document the failure modes you actually hit — that is how ${kw} becomes a maintainable asset instead of incident fuel.`,
  ]);

  return [intro, specificSections, s1, s2, glossarySection, s3, s4, s5, s6, s7, s8, takeaway]
    .filter(Boolean)
    .join("\n");
};

const descriptionFor = (title, category) => {
  const clean = title.replace(/^(RAG:|AI Agents:|MCP:|API Design:|Security:)\s*/i, "");
  return `${clean}: production patterns for ${category.toLowerCase()} teams — design, implementation, testing, security, and operations.`;
};

const keywordsFor = (slug, category) =>
  [...new Set([...slug.split("-"), category.toLowerCase(), "production", "engineering", "architecture"])].join(", ");

const renderPost = (topic, index, total) => {
  const { slug, title, category } = topic;
  const date = staggerDate(index, total);
  const faq = faqFor(title, slug, category);
  const tags = pickTags(category, slug);
  const resources = RESOURCES[category] || RESOURCES.default;

  const fm = [
    "---",
    `title: "${title.replace(/"/g, '\\"')}"`,
    `slug: "${slug}"`,
    `description: "${descriptionFor(title, category).replace(/"/g, '\\"')}"`,
    `datePublished: "${date}"`,
    `dateModified: "${date}"`,
    `tags: [${tags.map((t) => `"${t}"`).join(", ")}]`,
    `keywords: "${keywordsFor(slug, category)}"`,
    "faq:",
    ...faq.flatMap(({ q, a }) => [`  - q: "${q.replace(/"/g, '\\"')}"`, `    a: "${a.replace(/"/g, '\\"')}"`]),
    "---",
    "",
  ].join("\n");

  const body = bodyFor(topic, index, total);
  const refs = section(
    "Resources",
    resources.map((u) => `- [${new URL(u).hostname}${new URL(u).pathname === "/" ? "" : new URL(u).pathname}](${u})`)
  );

  return fm + body + "\n" + refs;
};

const wordCount = (md) => {
  const body = md.split("---").slice(2).join("---");
  return body.split(/\s+/).filter(Boolean).length;
};

const main = async () => {
  const topics = JSON.parse(await readFile(TOPICS_FILE, "utf8"));
  let slice = topics.slice(start, start + limit);

  if (batchIdx != null) {
    const BATCH = 20;
    const i0 = (batchIdx - 1) * BATCH;
    slice = topics.slice(i0, i0 + BATCH);
  }

  await mkdir(BLOG, { recursive: true });

  let written = 0;
  let skipped = 0;
  const thin = [];

  for (let i = 0; i < slice.length; i++) {
    const topic = slice[i];
    const globalIdx = batchIdx != null ? (batchIdx - 1) * 20 + i : start + i;
    const outPath = path.join(BLOG, `${topic.slug}.md`);

    try {
      if (!force) {
        await access(outPath);
        skipped++;
        continue;
      }
    } catch {
      /* new file or force overwrite */
    }

    const md = renderPost(topic, globalIdx, topics.length);
    const wc = wordCount(md);
    if (wc < 900) thin.push({ slug: topic.slug, wc });

    if (!dryRun) await writeFile(outPath, md, "utf8");
    written++;
  }

  console.log(JSON.stringify({ written, skipped, thin: thin.length, thinSlugs: thin.slice(0, 5) }, null, 2));
};

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
