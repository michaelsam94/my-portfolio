---
title: "AI Agents: Backup Restore Drills"
slug: "agent-backup-restore-drills"
description: "Agent backups fail quietly until restore day—quarterly drills with automated verification, vector index recovery, and conversation state replay expose gaps before a real outage does."
datePublished: "2026-04-05"
dateModified: "2026-04-05"
tags: ["AI", "Agent", "Backup"]
keywords: "backup restore drills, disaster recovery, agent state, vector index backup, RPO RTO, game day, conversation memory, pg_dump, point-in-time recovery"
faq:
  - q: "What agent-specific data must backups include beyond the application database?"
    a: "Conversation transcripts, tool invocation logs, vector embeddings and metadata, prompt/version registry, feature flag snapshots, and tenant-scoped secrets references. Embeddings without source document hashes are useless—you need the linkage to rebuild indexes."
  - q: "How often should teams run restore drills for agent systems?"
    a: "Full restore to an isolated environment quarterly at minimum; partial restores (single tenant, single index partition) monthly. Automate verification so drills run without calendar heroics—manual drills get skipped when roadmaps tighten."
  - q: "What is a realistic RTO for vector index recovery?"
    a: "Depends on index size: a 10M-vector HNSW rebuild from parquet snapshots may take 2–6 hours on commodity hardware. Design for incremental restore or warm standby replicas if your RTO target is under one hour."
  - q: "How do you prove a restore succeeded?"
    a: "Run golden-query evals against the restored index, replay sampled production sessions and compare tool routing decisions, and verify row counts plus checksums on embedding tables. Green health checks alone prove nothing."
---
Every backup policy I've reviewed looked fine on paper. Snapshots enabled, cross-region replication configured, runbook linked from the wiki. Then someone asked: "When did we last actually restore?" Silence. Six months later, a misconfigured migration truncated the `agent_sessions` table, and the team discovered their nightly dump excluded JSONB columns over 1 MB—which is exactly where long agent transcripts live.

Backups are inventory. **Restore drills** are the audit that tells you whether the inventory is real. For agent systems, the stakes are higher than typical CRUD apps because state is fragmented across OLTP stores, vector indexes, object storage for uploads, and ephemeral caches that teams forget to exclude from recovery scope.

## The restore that never happened

A common failure pattern: engineering trusts the cloud provider's "backup enabled" checkbox. Provider backups protect against regional failure; they do not protect against application-level logical corruption—a bad deploy that writes null embeddings, a script that deletes the wrong S3 prefix, a tenant offboarding job with an off-by-one ID.

Drills surface three recurring gaps:

1. **Schema drift** — restore scripts reference columns dropped two migrations ago
2. **Secret rot** — restored environment points at deprecated model endpoints or expired API keys stored outside the backup
3. **Index inconsistency** — Postgres rows restored but vector index rebuilt from stale snapshot; agent retrieves wrong chunks

Treat "we have backups" as unverified until a drill completes with documented timings and pass/fail criteria.

## Inventory: what agent state actually is

Before scheduling drills, map every persistence layer:

| Asset | Typical store | Recovery complexity |
|-------|---------------|---------------------|
| Session / message history | Postgres, DynamoDB | Medium — watch JSONB size limits |
| Embeddings + metadata | pgvector, Pinecone, Weaviate | High — full rebuild vs snapshot |
| Uploaded files | S3, GCS | Low — versioning helps |
| Prompt registry | Git + DB version pins | Medium — must match deployed code |
| Tool credentials | Vault, Secrets Manager | High — not in DB dumps |
| Rate limit / bandit counters | Redis | Often acceptable to lose |

Document **recovery priority**: session history before bandit counters. Not everything needs the same RPO.

## RPO and RTO for conversational systems

**Recovery Point Objective (RPO)** — maximum acceptable data loss. For enterprise support agents, four hours of lost transcripts may be unacceptable; for internal dev assistants, twenty-four hours may suffice.

**Recovery Time Objective (RTO)** — maximum downtime. Agent UIs without history feel "broken" even if inference works—users expect thread continuity.

Agent-specific tension: vector indexes lag OLTP. If you replicate Postgres continuously but snapshot vectors nightly, restored agents answer from stale knowledge until re-embedding completes. Align RPO across linked stores or accept explicit "knowledge as of DATE" banners post-restore.

## Designing a quarterly game day

Structure drills as time-boxed incidents with observers and a scribe:

**T-minus 0** — Incident commander declares simulated total loss of primary region/database.

**T+15 min** — Team initiates restore runbook to isolated `dr-restore-*` environment. No production shortcuts.

**T+variable** — Measure wall-clock to: database readable, vector index queryable, agent serving golden prompts.

**T+end** — Run automated verification suite (below). Hold blameless retro within 48 hours.

Rotate roles. The person who wrote the backup script should not be the only one who can restore.

```bash
#!/usr/bin/env bash
# scripts/drill-restore.sh — run in CI monthly against ephemeral env
set -euo pipefail

DRILL_ENV="${DRILL_ENV:-dr-restore-staging}"
BACKUP_URI="${BACKUP_URI:-s3://backups/agent/pg/latest.dump}"
START=$(date +%s)

echo "==> Provisioning isolated environment: ${DRILL_ENV}"
terraform -chdir=infra/dr apply -var="env=${DRILL_ENV}" -auto-approve

echo "==> Restoring Postgres"
pg_restore --dbname="$DATABASE_URL" --jobs=4 "$BACKUP_URI"

echo "==> Restoring vector snapshot"
aws s3 sync "s3://backups/agent/vectors/latest/" /data/vectors/
python tools/rebuild_index.py --source /data/vectors --target "$VECTOR_URL"

ELAPSED=$(( $(date +%s) - START ))
echo "restore_elapsed_seconds=${ELAPSED}" | tee drill_metrics.txt

echo "==> Running verification"
pytest tests/dr/ -v --env="${DRILL_ENV}"
```

## Automated verification beats checklist optimism

Manual "click around the UI" restores miss subtle corruption. Build a **DR verification package**:

```python
# tests/dr/verify_restore.py
import hashlib
import httpx
import pytest

GOLDEN_QUERIES = [
    ("refund policy cap", "refund-policy-v3.md", 0.92),
    ("SSO metadata rotation", "sso-runbook.md", 0.88),
]

@pytest.fixture(scope="module")
def agent_client():
    return httpx.Client(base_url=os.environ["DRILL_AGENT_URL"], timeout=60)

def test_session_row_counts_match_manifest(agent_client):
    manifest = json.load(open("dr/manifest.json"))
    resp = agent_client.get("/internal/dr/stats")
    assert resp.json()["sessions"] >= manifest["min_sessions"]
    assert resp.json()["messages"] >= manifest["min_messages"]

@pytest.mark.parametrize("query,expected_doc,min_score", GOLDEN_QUERIES)
def test_retrieval_golden_queries(agent_client, query, expected_doc, min_score):
    resp = agent_client.post("/internal/dr/retrieve", json={"query": query, "top_k": 5})
    hits = resp.json()["hits"]
    assert any(h["doc_id"] == expected_doc and h["score"] >= min_score for h in hits)

def test_sampled_session_replay(agent_client):
    """Replay tool routing for 50 sampled session IDs from manifest."""
    manifest = json.load(open("dr/session_samples.json"))
    mismatches = 0
    for sample in manifest:
        resp = agent_client.post("/internal/dr/replay", json={"session_id": sample["id"]})
        if resp.json()["tool_sequence_hash"] != sample["expected_hash"]:
            mismatches += 1
    assert mismatches / len(manifest) < 0.05  # allow 5% drift from model updates
```

Store `manifest.json` during backup generation with row counts, checksums, and hashed tool sequences for sampled sessions. Compare after restore—not absolute equality on LLM text output, but structural fidelity on retrieval and routing.

## Vector index recovery timelines

Full HNSW rebuilds dominate RTO for RAG agents. Mitigations:

- **Snapshot indexes** alongside embedding parquet exports
- **Dual-write to standby** index cluster during normal ops
- **Incremental upsert** from WAL-driven embedding changelog
- **Tiered recovery** — serve from keyword fallback until vectors ready

Document expected rebuild throughput (vectors/minute) on drill hardware matching production instance classes. Extrapolating from laptop benchmarks fails at 50M+ vectors.

## Secrets and model endpoint drift

Restored environments boot with yesterday's database but today's reality: API keys rotated, model deprecations (`gpt-4-0314` sunset), VPC peering changes. Maintain a **DR secrets bundle** versioned separately from data backups:

```yaml
# dr/env-fingerprint.yaml — updated each drill
expected:
  llm_endpoint: "https://api.openai.com/v1"
  embedding_model: "text-embedding-3-large"
  min_vault_secret_version: 42
checks:
  - name: llm_smoke
    prompt: "Reply OK"
    max_latency_ms: 5000
  - name: embed_dim
    expected_dimensions: 3072
```

Fail the drill if fingerprint checks do not pass—even if data restore succeeded.

## Compliance artifacts from drills

Regulated teams (HIPAA, SOC 2, financial services) need evidence, not anecdotes. Each drill should produce:

- Timestamped log with RTO/RPO achieved
- Verification test report (JUnit XML archived)
- List of failed steps and remediation tickets
- Sign-off from data owner

SOC 2 auditors ask for restore test evidence annually. Quarterly automated drills with archived artifacts satisfy this without fire drills disrupting product launches.

## When partial restore matters more than full

Full region loss is rare. Common incidents:

- Single tenant data deletion request executed wrongly
- One collection corrupted in multi-tenant vector DB
- Bad deploy writing garbage to prompt registry for one environment

Practice **scoped restores** monthly: recover tenant `acme-corp` into a sandbox, verify isolation, delete sandbox. Faster than full DR and catches tenant-filter bugs in restore scripts.

## Continuous backup integrity between drills

Drills are periodic; backup corruption is continuous. Nightly jobs should emit a **backup manifest** with table row counts, max `updated_at` timestamps, embedding file checksums, and object-store byte totals. Alert when tonight's manifest diverges more than 5% from the seven-day median without an explained migration—silent partial dumps often show up here days before anyone attempts restore.

Rotate one restored snapshot weekly in CI even between formal game days. A ten-minute automated job that mounts the latest dump and runs `verify_restore.py` catches schema drift while the author who changed the schema still remembers why.

## Closing

Agent backup strategy without restore drills is wishful thinking. Map fragmented state, align RPO across OLTP and vectors, automate restore plus golden-query verification, and measure elapsed time every month—not every year. The first real disaster should not be the first time anyone runs `pg_restore`.

## Resources

- [AWS Disaster Recovery whitepaper](https://docs.aws.amazon.com/whitepapers/latest/disaster-recovery-workloads-on-aws/disaster-recovery-workloads-on-aws.html) — RPO/RTO tiers and multi-region patterns
- [PostgreSQL backup documentation](https://www.postgresql.org/docs/current/backup.html) — logical vs physical backup tradeoffs for JSONB-heavy agent tables
- [Google SRE: Disaster Recovery Testing](https://sre.google/resources/practices-and-processes/disaster-recovery/) — game day culture and blast radius control
- [Pinecone backup and collections guide](https://docs.pinecone.io/guides/manage-data/back-up-and-restore) — managed vector backup semantics
- [HashiCorp Vault disaster recovery](https://developer.hashicorp.com/vault/tutorials/enterprise/disaster-recovery) — restoring secrets infrastructure agent endpoints depend on
