---
title: "AI Agents: Changelog Compacted Topics"
slug: "agent-changelog-compacted-topics"
description: "Long changelogs blow agent context windows—compaction with topic clustering, recency weighting, and structured summaries keeps release history useful without drowning every turn in noise."
datePublished: "2025-01-29"
dateModified: "2025-01-29"
tags: ["AI", "Agent", "Changelog"]
keywords: "changelog compaction, topic clustering, agent memory, release notes, context window, semantic summarization, RAG changelog, incremental updates"
faq:
  - q: "What does 'compacted topics' mean for agent changelogs?"
    a: "Instead of injecting raw release notes into every agent turn, you cluster changelog entries by topic (auth, billing, API), summarize each cluster into a fixed token budget, and expose only the clusters relevant to the current user query or tool scope."
  - q: "When should compaction run—at ingest time or at query time?"
    a: "Run structural compaction at ingest (when a release ships) so summaries are stable and testable. Run relevance filtering at query time so the agent sees only topics tied to the active codebase, tenant feature flags, or the user's question."
  - q: "How do I prevent compaction from hiding breaking changes?"
    a: "Tag breaking changes with a dedicated severity lane that bypasses normal compression. Keep full text in durable storage; inject compact summaries plus explicit BREAKING blocks when the agent's scope touches affected modules."
  - q: "What metrics tell me compaction is working?"
    a: "Track tokens injected per session, answer accuracy on changelog-grounded evals, hallucination rate on version-specific questions, and user escalation rate when agents cite outdated behavior."
---
A support agent at a B2B SaaS company was asked why OAuth scopes changed in the March release. It confidently explained behavior from January—because the system prompt included twelve months of release notes verbatim, and the model attended to the first matching paragraph it found. The correct answer lived in line 847 of a JSON export nobody had trimmed since v2.4.

Changelog compaction is not summarization for its own sake. It is **context economics**: keeping release history available to agents without turning every turn into a document-retrieval problem. This post covers how to cluster, compress, and selectively inject changelog topics so agents stay accurate across long product lifetimes.

## Why raw changelogs fail agents

Release notes accumulate faster than context windows grow. A mature product might ship forty entries per quarter across API, mobile, billing, and infra. Pasting that into system context consumes tokens that should go to user intent, tool schemas, and retrieved code.

Three failure modes show up repeatedly:

| Failure mode | Symptom | Root cause |
|--------------|---------|------------|
| Stale dominance | Agent cites old behavior | Recency bias inverted—early entries repeat keywords |
| Topic collision | Wrong module blamed | "Settings" appears in five unrelated entries |
| Missing severity | Breaking change ignored | Compression averages away imperative language |

Agents do not "read" changelogs the way engineers scan GitHub releases. They pattern-match on surface text. Compaction must preserve **semantic anchors**—module names, API paths, flag keys, migration deadlines—not just shorter prose.

## Topic clustering at ingest

The first compaction stage groups entries before any LLM summarization. Deterministic clustering reduces cost and makes regressions testable.

A practical pipeline:

1. **Normalize** each entry: title, body, affected components, semver, date, severity tags.
2. **Embed** title + first paragraph; assign to nearest topic centroid or HDBSCAN cluster.
3. **Merge** clusters below a minimum entry count into an "misc" bucket with a higher summarization priority.
4. **Emit** a `TopicCluster` record per group with stable IDs tied to your taxonomy.

```typescript
// changelog/compactTopics.ts
import { embed, clusterByCentroid } from "./ml";
import { ChangelogEntry, TopicCluster } from "./types";

const TAXONOMY = ["auth", "billing", "api", "mobile", "infra", "security"] as const;

export async function compactRelease(
  releaseId: string,
  entries: ChangelogEntry[],
): Promise<TopicCluster[]> {
  const vectors = await embed(entries.map((e) => `${e.title}\n${e.summary}`));
  const labeled = clusterByCentroid(vectors, TAXONOMY);

  const byTopic = new Map<string, ChangelogEntry[]>();
  for (let i = 0; i < entries.length; i++) {
    const topic = labeled[i] ?? "misc";
    byTopic.set(topic, [...(byTopic.get(topic) ?? []), entries[i]!]);
  }

  return Promise.all(
    [...byTopic.entries()].map(async ([topic, group]) => ({
      releaseId,
      topic,
      entryIds: group.map((e) => e.id),
      compactText: await summarizeTopicGroup(topic, group),
      breaking: group.filter((e) => e.severity === "breaking"),
      tokenBudget: topic === "security" ? 512 : 256,
    })),
  );
}

async function summarizeTopicGroup(
  topic: string,
  entries: ChangelogEntry[],
): Promise<string> {
  // Prefer structured output: bullet facts, not narrative fluff
  return llmSummarize({
    system: "Extract user-visible behavior changes only. Preserve API paths and flag names.",
    entries,
    maxTokens: 200,
    topic,
  });
}
```

Keep **breaking entries out of the summary body**. Store them as structured fields the query layer can inject unconditionally when scope matches.

## Recency-weighted topic windows

Not all topics deserve equal history depth. API surface changes need six months; infra migrations might need only the latest cluster. Define per-topic **lookback windows** in releases, not calendar time, so compaction stays stable during quiet periods.

```typescript
const LOOKBACK: Record<string, number> = {
  api: 8,
  auth: 6,
  billing: 4,
  mobile: 3,
  infra: 2,
};

export function selectTopicHistory(
  clusters: TopicCluster[],
  activeTopics: string[],
): TopicCluster[] {
  return activeTopics.flatMap((topic) => {
    const window = LOOKBACK[topic] ?? 3;
    return clusters
      .filter((c) => c.topic === topic)
      .sort((a, b) => b.releaseId.localeCompare(a.releaseId))
      .slice(0, window);
  });
}
```

At query time, infer `activeTopics` from the user's repo path, open files, feature flags, or explicit `@changelog/auth` mentions. Default to a conservative subset—API + security—rather than injecting everything.

## Query-time injection contract

Treat compacted topics as a **typed context block**, not freeform prose. Agents and eval harnesses parse it reliably.

```markdown
<!-- injected by changelog service -->
<changelog_context scope="api,auth" as_of="2025-01-29">
## api (releases v3.2–v3.8)
- POST /v2/tokens accepts `scope` array; legacy `permissions` deprecated v3.6
- Rate limit headers renamed: X-RateLimit-Remaining

## auth (releases v3.5–v3.8)
- BREAKING: SAML metadata refresh required by 2025-02-15
- Session TTL default 24h → 8h for new tenants only
</changelog_context>
```

Rules that survive production:

- **Cap total tokens** for the block; drop oldest clusters within a topic before dropping entire topics.
- **Never compact away dates and version numbers**—agents need them for "since when" questions.
- **Log injection sets** per session for debugging wrong-answer reports.

## Evaluating compaction quality

Generic summarization metrics (ROUGE, BERTScore) correlate poorly with agent usefulness. Build a **changelog QA eval set**:

- Questions keyed to specific releases ("When did we deprecate X?")
- Cross-topic disambiguation ("Did billing or API change retry behavior?")
- Breaking-change detection under partial context

Run evals whenever your summarization prompt or clustering taxonomy changes. Track regression per topic cluster, not just aggregate accuracy.

Pair offline evals with production signals: when users correct the agent or open docs linked from a "wrong version" banner, tag the session with the injected cluster IDs and feed failures back into prompt tuning.

## Operational concerns

Compaction jobs should be **idempotent per release**. Re-running ingest for v3.7 must overwrite cluster v3.7 records without duplicating summaries in the vector store.

Store three tiers:

1. **Raw entries** — immutable audit trail
2. **Topic clusters** — compact summaries, versioned by summarizer model + prompt hash
3. **Injection logs** — what each session actually saw

Alert when summarization latency blocks release publish, when cluster count drifts unexpectedly (taxonomy drift), or when breaking-change count in raw entries ≠ structured breaking array count (parser bug).

Roll out summarizer prompt changes with shadow mode: generate new compact text, diff against production in eval, flip traffic only after passing gates.

## Security and compliance

Changelogs sometimes mention CVE fixes, customer-specific migrations, or embargoed features. Tag entries with visibility classes (`public`, `internal`, `customer-specific`) before compaction. Customer-specific clusters must never enter multi-tenant agent context without tenant ID filtering.

Summarization calls send entry text to an LLM—treat that as a data-processing boundary. Redact account IDs and ticket numbers at normalize time; use on-prem or zero-retention inference for regulated tenants.

## Monorepo and multi-product variants

Teams shipping multiple surfaces from one repo need **product dimension** on clusters, not just topic. A mobile-only change should not inflate API context for backend-only agent sessions. Tag entries with `product: [web, ios, api]` at normalize time; filter injection sets by the caller's product scope.

For monorepos, map file paths to products automatically via CODEOWNERS or package boundaries. When a user asks about `@packages/billing-sdk`, inject billing + api clusters for that package's lookback window—skip mobile entirely. Cross-product breaking changes (shared auth library) propagate via explicit `affects: all` tags that bypass product filters but still respect topic caps.

Version skew between client and server is another compaction edge case. Store minimum compatible versions in cluster metadata so agents can answer "you need app v4.2+" without re-reading six months of mobile notes.

## Closing

Compacted changelog topics turn release history from a context-window tax into a scoped, testable knowledge layer. Cluster at ingest, weight recency by topic, inject through a strict contract, and eval on version-specific questions—not on how pretty the summaries read. Agents that cite the right release save support hours; agents that cite January in March erode trust faster than no changelog at all.

## Resources

- [Keep a Changelog](https://keepachangelog.com/) — structured release format that compacts cleanly into topic clusters
- [Semantic versioning spec](https://semver.org/) — severity and breaking-change tagging for bypass lanes
- [OpenAI token counting guide](https://platform.openai.com/tokenizer) — budget compaction blocks against real model limits
- [HDBSCAN clustering](https://hdbscan.readthedocs.io/) — density-based topic grouping when taxonomy labels are incomplete
- [RAG evaluation patterns (LangChain)](https://python.langchain.com/docs/guides/evaluation/) — grounding evals for changelog QA sets
