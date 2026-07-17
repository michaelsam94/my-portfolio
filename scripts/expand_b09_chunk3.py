#!/usr/bin/env python3
"""Expand b09_chunk_3 rag posts to >=1200 body words with unique topic content."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content" / "blog"
WORD_PAT = re.compile(r"\b[\w'-]+\b")
TARGET = 1200

FAQS = {
    "rag-bias-detection-evaluation": [
        ('What metrics should RAG teams track for retrieval bias?', 'Track recall@k and nDCG sliced by document source, language, publication date, and author demographics where metadata exists. Pair with counterfactual queries that swap demographic markers in otherwise identical questions. A flat aggregate MRR can hide a 30-point gap on non-English corpora.'),
        ('How do you evaluate bias when RAG uses hybrid retrieval?', 'Measure BM25 and vector rank separately per slice — lexical search amplifies majority-language terms while dense retrieval may over-weight dominant embedding clusters. Log which retriever surfaced each chunk and whether rerankers reorder minority sources out of top-k.'),
        ('When should bias evaluation block a RAG index publish?', 'Block when any pre-registered slice falls below fairness thresholds on primary retrieval metrics, when counterfactual tests show systematic source preference flip, or when eval results are not reproducible across two independent runs.'),
        ('What is the difference between bias detection and corpus debiasing?', 'Detection measures disparate retrieval or generation impact across groups; debiasing adjusts corpus composition, boosts, or filters. Detection must run continuously because corpora, embeddings, and query populations drift. Debiasing without measurement is guesswork.'),
    ],
    "rag-blue-green-database-migration": [
        ('Why use blue-green for RAG vector databases?', 'Blue-green lets you rebuild embeddings and HNSW indexes on the green cluster while blue serves live traffic. Cutover is a connection-string or alias flip — not an in-place reindex that degrades query latency for hours.'),
        ('How do you keep Postgres metadata in sync during blue-green?', 'Replicate document metadata and chunk manifests via logical replication or CDC into green. Validate row counts and checksums before cutover. Vector payloads may live in a separate store — treat both as one migration unit.'),
        ('What rollback looks like for a failed RAG DB cutover?', 'Keep blue warm for at least 24 hours. Rollback means repointing the retrieval service alias, not restoring from backup mid-traffic. Feature flags on corpus version prevent green from serving stale chunks after rollback.'),
        ('How long should dual-write last?', 'Dual-write until green read traffic matches blue within 0.1% on sample queries and no replication lag alarms fire for 72 hours. Shorter windows risk split-brain chunk IDs that break citation links.'),
    ],
    "rag-bm25-elasticsearch-tuning": [
        ('What BM25 k1 and b values work best for RAG knowledge bases?', 'Start with Elasticsearch defaults (k1=1.2, b=0.75) for mixed-length docs. Raise k1 toward 1.6–2.0 when keyword overlap matters (API identifiers, error codes). Lower b toward 0.3–0.5 when short titles and long bodies should contribute more equally.'),
        ('Should RAG use BM25 alone or hybrid with vector search?', 'Hybrid almost always wins: BM25 nails exact tokens; vectors handle paraphrase. Reciprocal rank fusion or weighted score combination is the production default for enterprise knowledge bases.'),
        ('How do you measure if BM25 tuning improved RAG answers?', 'Track nDCG@k on a golden query set, then measure downstream answer faithfulness when chunks feed an LLM. Retrieval metrics alone lie — wrong policy chunks ranked higher cause more harm than a flat score.'),
        ('What analyzer mistakes break BM25 for technical docs?', 'Over-stemming, splitting dotted identifiers (api.v2.auth), and lowercase folding on case-sensitive codes. Use keyword subfields for IDs and a standard analyzer for prose.'),
    ],
    "rag-breach-notification-playbook": [
        ('What triggers breach notification for a RAG system?', 'Unauthorized access to embedding stores containing PII snippets, prompt logs with regulated data exfiltrated, or retrieval indexes built from documents beyond authorized scope. Treat vector DB snapshots like database backups for classification.'),
        ('How fast must RAG teams notify after discovering a breach?', 'GDPR requires 72 hours to supervisory authority; many US state laws vary. Your playbook should start the clock at confirmed unauthorized access, not at root-cause completion. Legal owns external comms; engineering owns evidence preservation.'),
        ('What evidence should RAG incident response preserve?', 'Query logs with tenant IDs, retrieval chunk IDs accessed, model completion logs, API keys rotated, and index snapshot timestamps. Immutable audit trail before reindex or log rotation runs.'),
        ('Should you take RAG offline during breach investigation?', 'Read-only mode preserves evidence while stopping further exposure. Disable ingestion and purge endpoints first; keep retrieval up only if legal confirms no ongoing exfiltration vector through the same path.'),
    ],
    "rag-cache-aside-vs-read-through": [
        ('When should RAG pipelines use cache-aside instead of read-through?', 'Cache-aside when application code orchestrates retrieval, reranking, and generation and you need explicit cache keys with corpus version. Read-through fits session metadata and tenant config blobs accessed through a shared cache library.'),
        ('What RAG data is safe to cache?', 'Embedding vectors for immutable chunks, idempotent retrieval bundles keyed by corpus version, compiled prompt templates. Short-TTL or never: personalized filters, authorization decisions, anything whose staleness causes wrong answers or cross-tenant leakage.'),
        ('How do you prevent cache stampedes on hot RAG queries?', 'Per-key locks (Redis SETNX), request coalescing, jittered TTLs, stale-while-revalidate for embedding lookups. Never let concurrent workers miss the same key and hammer your vector DB simultaneously.'),
        ('Does caching RAG completions violate retention policies?', 'It can. Cache keys derived from user PII and storing completions beyond approved retention triggers GDPR issues. Hash keys, encrypt at rest, set TTL aligned with data classification.'),
    ],
    "rag-cache-stampede-prevention": [
        ('What causes cache stampedes in RAG pipelines?', 'Popular document updates expiring many chunk cache keys at once, viral queries missing embedding cache simultaneously, or corpus republication invalidating broad key prefixes without gradual TTL jitter.'),
        ('What is single-flight and when should RAG use it?', 'Single-flight ensures one origin fetch per cache key while others wait or serve stale. Use on embedding computation and full retrieval bundles — the most expensive miss paths.'),
        ('How does stale-while-revalidate help RAG latency?', 'Serve slightly stale retrieval results while one worker refreshes in background. Acceptable for public docs with version metadata; unacceptable for real-time policy without version checks.'),
        ('What metrics indicate an impending stampede?', 'Sudden spike in embedding API QPS while cache hit rate drops, vector DB connection pool saturation, p95 retrieval latency cliff. Alert on miss-rate derivative, not just absolute latency.'),
    ],
}

# Additional FAQs for remaining slugs - compact but topic-specific
MORE_FAQS = {
    "rag-canary-analysis-flagger": [
        ('What should Flagger canaries measure for RAG deploys?', 'Retrieval recall@5 on shadow queries, p95 embed latency, faithfulness score on golden set, and empty-result rate — not just HTTP 200 from the API gateway.'),
        ('How long should a RAG canary run?', 'At least one full business cycle or 30 minutes minimum with statistically meaningful query volume. Low-traffic tenants need synthetic canary query injection.'),
        ('Can Flagger rollback a bad embedding model deploy?', 'Yes if metrics come from Prometheus recording rules on eval sidecar. Wire corpus version into canary labels so rollback does not affect unrelated indexes.'),
        ('What fails a RAG canary besides error rate?', "Regression in nDCG@10, spike in citation precision failures, or increase in \"I don't know\" rate when ground truth expects an answer."),
    ],
    "rag-canary-token-alerts": [
        ('What are canary tokens in a RAG context?', 'Honeytoken documents or fake credentials planted in the corpus. Any retrieval or generation referencing them indicates unauthorized index access or over-broad search.'),
        ('Where should canary tokens live?', 'In isolated corpus partitions with unique strings never appearing in legitimate docs. Alert on any query log or completion containing the token substring.'),
        ('How is this different from traditional honeypots?', 'Canary tokens are content-based tripwires inside the knowledge base, not network honeypots. They catch insider misuse and broken access filters on retrieval.'),
        ('How often rotate canary token values?', 'Quarterly or after any suspected index leak. Rotation requires re-indexing only the canary partition — keep automation for that path tested.'),
    ],
    "rag-capacity-forecasting-models": [
        ('What drives RAG capacity growth?', 'Corpus size (embedding storage), query QPS (GPU/CPU for embed and rerank), index rebuild frequency, and token generation volume downstream. Each scales differently.'),
        ('How forecast embedding storage?', 'Linear in chunk count × dimension × 4 bytes for float32, plus HNSW graph overhead (~1.5–2× raw vectors). Model monthly ingest rate from document pipeline metrics.'),
        ('Should you forecast LLM tokens separately from retrieval?', 'Yes. Retrieval capacity is sub-second CPU/GPU; generation is token-billed and bursty. Peak Monday-morning patterns differ between embed API and chat completions.'),
        ('What leading indicators precede RAG capacity incidents?', 'Growing p95 embed queue depth, index build duration trending up, disk usage on vector nodes crossing 70%, connection pool wait time on metadata DB.'),
    ],
    "rag-catalog-datahub-amundsen": [
        ('Why catalog RAG corpora in DataHub or Amundsen?', 'Teams lose track of which documents feed which indexes, who owns refresh SLAs, and what PII classifications apply. Catalog links corpus → index → downstream RAG app with lineage.'),
        ('What metadata fields matter for RAG datasets?', 'Corpus version, chunking strategy, embedding model, refresh cadence, PII classification, owner team, and eval recall@5 from last publish.'),
        ('How integrate catalog with index publish pipeline?', 'CI job writes dataset properties on successful index build. Failed eval blocks catalog "production" tag — prevents consumers binding to bad indexes.'),
        ('Can catalog help debug wrong RAG answers?', 'Yes — trace answer citation chunk ID back to catalog document version and ingestion job. Shows whether user got stale or wrong-source content.'),
    ],
    "rag-cdc-debezium-postgres": [
        ('Why CDC for RAG metadata stores?', 'Document title, ACL, and soft-delete flags live in Postgres. CDC propagates changes to search indexes without full reindex — critical for permission-aware retrieval.'),
        ('How handle deletes in vector indexes via CDC?', 'Tombstone events remove chunk IDs from the index. Hard deletes in Postgres must map to explicit delete API on vector store — eventual consistency window should be documented.'),
        ('What Debezium config matters for RAG?', 'Include only tables that affect retrieval filters. Large blob columns should not replicate — store blob refs and fetch from object storage on ingest.'),
        ('How avoid CDC lag causing stale RAG permissions?', 'Monitor replication lag SLA; fail closed on retrieval if lag exceeds threshold — better empty results than leaking revoked documents.'),
    ],
    "rag-cdn-cache-purge-strategies": [
        ('What RAG assets belong on a CDN?', 'Static chat widget bundles, public help-center HTML rendered from RAG, cached API responses for anonymous FAQ endpoints — not personalized retrieval results with tenant data.'),
        ('When purge vs short TTL for RAG content?', 'Purge immediately on security-sensitive doc retraction. Use short TTL (60–300s) for frequently updated public docs; event-driven purge on publish webhooks for everything else.'),
        ('How purge without stampeding origin?', 'Soft purge (mark stale, revalidate in background) via CDN API. Surge protect origin with stale-while-error during mass purge after corpus republication.'),
        ('Tag-based purge for multi-tenant RAG?', 'Tag CDN objects by corpus_id and tenant tier. Purge tag on tenant offboarding without touching shared static assets.'),
    ],
    "rag-cdn-stale-while-revalidate": [
        ('How SWR helps RAG-facing static content?', 'Users get instant cached help pages while CDN fetches fresh render in background. Reduces TTFB for documentation portals backed by RAG search widgets.'),
        ('What Cache-Control header for RAG FAQ pages?', 'public, max-age=60, stale-while-revalidate=3600, stale-if-error=86400 — tune max-age to publish frequency. Never SWR on authenticated API responses.'),
        ('Does SWR apply to embedding API responses?', 'Generally no — embeddings are dynamic and tenant-specific. SWR fits edge-cached rendered HTML and public JSON schema docs, not vector search results.'),
        ('How monitor SWR effectiveness?', 'CDN age header distribution, origin hit ratio, revalidation QPS. Spike in revalidation without traffic growth may indicate too-short max-age.'),
    ],
    "rag-cert-manager-dns01": [
        ('Why DNS-01 for RAG platform TLS?', 'Wildcard certs for *.rag-api.example.com and gRPC embed services without HTTP-01 per-host challenges. Required when ingress is internal or split across clusters.'),
        ('How cert-manager interacts with RAG multi-cluster?', 'One DNS-01 solver with Route53/Cloudflare API; Certificate resource per cluster referencing same DNS name with distinct secret namespaces.'),
        ('What happens when cert renewal fails mid-traffic?', 'Monitor cert-manager Certificate Ready=False. Alert 14 days before expiry — RAG clients with pinned intermediates fail hard on expiry, not gracefully.'),
        ('Should embed gRPC use same cert as HTTPS API?', 'Separate certs if different trust domains or mTLS requirements. Document SAN list includes internal service mesh names agents use for retrieval.'),
    ],
    "rag-certificate-transparency-monitoring": [
        ('Why monitor CT logs for RAG domains?', 'Detect misissued certs for your RAG API domain before attackers use them for MITM or phishing clones of your chat interface.'),
        ('What CT alerts matter for internal RAG services?', 'Unexpected certs for api.rag.internal or embed.gw.company.com — often first sign of misconfigured cert-manager or compromised DNS.'),
        ('How integrate CT monitoring with cert-manager?', 'Compare CT log entries against expected cert-manager ACME issuer fingerprints. Alert on certs from unknown CAs.'),
        ('Does CT monitoring replace cert pinning?', 'No — complementary. CT catches issuance; pinning protects clients that already trust a compromised CA.'),
    ],
    "rag-changelog-compacted-topics": [
        ('Why compacted topics for RAG event streams?', 'Document publish events replay from compacted Kafka topic keyed by document_id — consumers rebuild partial index state without reading full history.'),
        ('What keys use log compaction in RAG pipelines?', 'document_id → latest version metadata, corpus_id → current publish config, tenant_id → ACL snapshot hash.'),
        ('How avoid unbounded compaction lag?', 'Right-size segment bytes, monitor kafka.log.cleaner.* metrics. Large PDF ingest bursts create compaction debt that delays ACL updates reaching indexes.'),
        ('Compacted topic vs CDC for RAG?', 'CDC captures row-level DB truth; compacted topics capture publish-intent events. Many systems use both — CDC for permissions, compacted topic for ingest orchestration.'),
    ],
    "rag-chaos-monkey-game-days": [
        ('What RAG dependencies inject failure on first?', 'Vector DB latency, embedding API 503, reranker timeout, metadata Postgres read replica lag — in that order of user impact frequency.'),
        ('What does a successful RAG game day prove?', 'Retrieval degrades to cached or BM25-only fallback, generation returns graceful "search unavailable" not hallucinated answers, no unbounded retry spend.'),
        ('How measure RAG resilience quantitatively?', 'Error budget burn during injection, max token spend per degraded query, time to detect via SLO alert. Pre-register pass/fail thresholds.'),
        ('Should game days include corpus corruption scenarios?', 'Yes — simulate bad embed deploy with canary metrics. Practice rollback to previous corpus_version alias without full reindex.'),
    ],
    "rag-chargeback-dispute-automation": [
        ('How RAG supports chargeback dispute automation?', 'Retrieve transaction records, merchant policy clauses, and prior dispute outcomes to draft evidence packets. Citations must map to authoritative policy chunks.'),
        ('What guardrails prevent wrong dispute evidence?', 'Faithfulness checks on each cited claim, jurisdiction metadata filters at retrieval, human review queue for amounts above threshold.'),
        ('Which corpora feed chargeback RAG?', 'Card network rules PDFs, internal merchant agreement DB, historical won/lost case summaries with outcome labels.'),
        ('How audit automated dispute drafts?', 'Log retrieval chunk IDs, model version, and human edits to final submission. Regulators ask for traceability, not just LLM fluency.'),
    ],
    "rag-chatops-incident-bots": [
        ('What RAG incidents should chatops bots handle first?', 'Lookup runbooks by error signature, summarize recent deploys affecting retrieval, pull grafana dashboard links for embed latency SLO.'),
        ('How avoid chatops bot hallucinating runbook steps?', 'Retrieve runbook chunks with citation-only mode; bot paraphrases retrieved steps, never invents. Fail if no runbook chunk above threshold.'),
        ('Slack vs PagerDuty integration for RAG on-call?', 'PagerDuty for SLO burn; Slack bot for context gathering and `/rag-status corpus_version` queries during triage.'),
        ('How keep bot commands from leaking cross-tenant data?', 'Bind Slack user to on-call roster; retrieval filters enforce tenant scope on every incident query.'),
    ],
    "rag-chunk-overlap-tuning": [
        ('What overlap percentage works for procedural docs?', '15–20% of chunk size when steps span boundaries. Runbooks with numbered steps often need 80–128 token overlap on 512-token chunks.'),
        ('When does overlap hurt more than help?', 'When top-k returns three near-duplicate chunks differing only by overlap region — reduces diversity and wastes context window.'),
        ('How overlap interacts with hybrid search?', 'Duplicate chunks inflate BM25 IDF oddly and create redundant vector neighbors. Deduplicate by parent section ID at query time if overlap exceeds 25%.'),
        ('Should overlap differ by embedding model?', 'Re-evaluate when switching models — smaller effective context models may need more overlap to preserve boundary context in each chunk embedding.'),
    ],
    "rag-chunking-strategies-compared": [
        ('Can you mix chunking strategies in one RAG index?', 'Yes — route by doc_type metadata: markdown uses header split, PDFs use semantic, tickets use fixed 384. Single index with strategy tag in metadata.'),
        ('Which strategy fails most on PDF exports?', 'Fixed-size without layout-aware extraction — tables become garbage chunks. Preprocess with Unstructured or Docling before strategy selection.'),
        ('How often re-evaluate chunking strategy?', 'On corpus format migration, embedding model change, or recall@5 drop exceeding 5 points on weekly eval.'),
        ('Agentic chunking — when is cost justified?', 'When rule-based strategies fail eval on high-value legal or medical sets and manual chunking cost exceeds LLM boundary detection at index time.'),
    ],
    "rag-circuit-breaker-bulkhead-patterns": [
        ('Where put circuit breakers in RAG pipelines?', 'Embedding API, vector DB, reranker, and LLM gateway — each independent breaker. Opening embed breaker should not open generation breaker.'),
        ('What bulkhead pools for RAG?', 'Separate thread pools for ingest embed workers vs interactive query embed. Prevents batch reindex from starving live user retrieval.'),
        ('Half-open state testing for RAG breakers?', 'Send synthetic canary query on half-open — measure success rate before full close. Use cheap BM25-only path as half-open probe.'),
        ('How breakers interact with cache fallback?', 'On breaker open, serve stale cache if corpus_version matches; if no cache, return explicit degraded response — never silent empty context to LLM.'),
    ],
    "rag-citation-attribution-grounding": [
        ('Do citations prevent RAG hallucinations?', 'They reduce unsupported claims but models still misquote or cite wrong chunks. Combine citation formatting with NLI faithfulness checks before display.'),
        ('Inline vs footnote citations for RAG UI?', 'Inline for compliance Q&A where users verify per claim. Footnotes acceptable for short summaries; long answers need per-sentence references.'),
        ('What metadata must citations include?', 'Document title, URL or internal ID, section, version, effective date — enough for auditor to find exact passage in 30 seconds.'),
        ('How handle conflicting cited sources?', 'Prompt model to present both positions with citations. Prefer retrieval-time filters on status:current to reduce conflicts before generation.'),
    ],
    "rag-cloud-trail-anomaly-alerts": [
        ('Which CloudTrail events matter for RAG on AWS?', 's3:PutObject to corpus buckets, sagemaker:InvokeEndpoint on embed models, secretsmanager:GetSecretValue for API keys, unauthorized iam:PassRole to embed jobs.'),
        ('How detect exfiltration via RAG S3 corpus?', 'Alert on GetObject volume anomaly from unfamiliar principals or cross-account roles. Baseline per IAM role by hour-of-day.'),
        ('Integrate CloudTrail with vector DB access logs?', 'Correlate AWS principal with application tenant_id in retrieval audit log — CloudTrail alone misses in-app authorization bugs.'),
        ('What ML for CloudTrail anomaly detection?', 'GuardDuty plus custom metric filters on PutObject rate to embed-adjacent buckets. Tune false positive rate before paging on-call.'),
    ],
    "rag-cluster-autoscaler-node-pools": [
        ('Separate node pools for RAG ingest vs query?', 'Yes — ingest is batch CPU/GPU heavy with spot tolerance; query needs stable on-demand nodes with low latency. Autoscaler policies differ.'),
        ('What triggers scale-up for embed GPU pools?', 'Pending pod count on embed deployment, queue depth metric from ingest job, GPU utilization sustained above 80% for 5 minutes.'),
        ('How avoid autoscaler thrashing during reindex?', 'Set scale-down delay to 15+ minutes on ingest pool; use Jobs with backoffLimit instead of bare Deployments for batch embed.'),
        ('Cluster autoscaler vs HPA for RAG API?', 'HPA on retrieval deployment by CPU and custom embed latency metric; cluster autoscaler adds nodes when HPA cannot schedule. Wire both — HPA alone starves on node cap.'),
    ],
    "rag-colbert-late-interaction": [
        ('When choose ColBERT over bi-encoder for RAG?', 'When recall@k with bi-encoder plateaus and you can afford 2–5× retrieval latency for high-stakes queries — legal, medical, tier-1 support.'),
        ('How ColBERT indexes differ from single-vector?', 'Store token-level embeddings per chunk — larger index footprint. Plan storage 10–50× bi-encoder depending on max doc length token cap.'),
        ('Late interaction at rerank vs first-stage?', 'Often first-stage ColBERT retrieve top-100, then cross-encoder rerank top-20 — balances latency and quality. Full ColBERT on million-chunk index needs pruning.'),
        ('How evaluate ColBERT ROI for RAG?', 'Measure nDCG lift and downstream faithfulness on golden set vs added p95 latency and storage cost. ROI negative if bi-encoder + rerank already within SLO.'),
    ],
    "rag-cold-start-recommendations": [
        ('Cold start in RAG vs recommender systems?', 'RAG cold start is empty retrieval for new documents or new tenants without indexed corpus — not user-item collaborative filtering, though hybrid systems combine both.'),
        ('How bootstrap retrieval for new tenant?', 'Seed with platform-wide template docs, transfer learning from similar tenant corpus metadata, or BM25 on title-only until embed index completes.'),
        ('What UX during RAG cold start?', 'Transparent "knowledge base indexing" state, fallback to general model with no-RAG mode clearly labeled, avoid confident answers without retrieved context.'),
        ('Measure cold start duration how?', 'Time from first document ingest to recall@5 > threshold on tenant-specific eval questions. SLA this for enterprise onboarding.'),
    ],
    "rag-cold-storage-tiering": [
        ('What RAG data belongs in cold storage?', 'Superseded corpus versions, raw PDF archives after chunking, eval query logs older than retention policy — not active vector indexes.'),
        ('Tiering embeddings vs source documents?', 'Keep hot tier for current corpus vectors on NVMe; Glacier for source PDFs and expired index snapshots. Rehydrate before rebuild jobs.'),
        ('Cost model for RAG storage tiers?', 'Vector hot storage dominates at scale — cold tier saves on raw ingest archives and compliance retention, not on live HNSW.'),
        ('Lifecycle policy on S3 for RAG corpora?', 'Transition to IA after 30 days post-supersede, Glacier after 90, expire after legal hold release. Tag objects with corpus_version for automated lifecycle.'),
    ],
    "rag-collaborative-filtering-embeddings": [
        ('How CF embeddings complement RAG?', 'CF captures "users who read X also needed Y" — inject as retrieval boost or sidebar suggestions alongside semantic search on documentation.'),
        ('Cold start with CF in RAG portals?', 'Fall back to popularity-weighted doc views until interaction matrix has minimum density per tenant.'),
        ('Privacy concerns with CF on enterprise RAG?', 'Aggregate click logs at team level, not individual, for B2B. Exclude confidential doc IDs from CF training entirely.'),
        ('Evaluate CF + RAG hybrid how?', 'A/B test click-through on suggested docs vs pure semantic retrieval baseline. CF wins on navigational intent, semantic wins on novel questions.'),
    ],
    "rag-color-contrast-apca": [
        ('Why APCA for RAG chat UI?', 'Citation links and confidence badges must meet contrast on dark-mode chat surfaces — WCAG 2.x ratios fail on thin text APCA catches.'),
        ('Which RAG UI elements need contrast audit?', 'Source snippet cards, inline citation brackets, warning badges on unverified claims, streaming text on gradient backgrounds.'),
        ('APCA vs WCAG 2.1 for compliance?', 'Some jurisdictions still reference WCAG 2.x — test both during RAG widget design. APCA better predicts readability for 14px citation text.'),
        ('Automate contrast checks in RAG frontend CI?', 'Playwright + axe or custom APCA calc on Storybook stories for chat message variants including cited and error states.'),
    ],
    "rag-column-encryption-pgcrypto": [
        ('What RAG metadata encrypt with pgcrypto?', 'Document source URLs with tokens, API keys in connector config, user-upload attribution fields — not chunk text already in vector DB unless compliance requires.'),
        ('Performance impact on RAG ACL queries?', 'Encrypt only sensitive columns; keep tenant_id and document_id plaintext for index joins. Decrypt after row fetch, not in WHERE clause.'),
        ('Key rotation with pgcrypto column encryption?', 'Use envelope encryption — data key per row wrapped by KMS master. Rotation re-wraps keys without re-encrypting entire corpus metadata table.'),
        ('pgcrypto vs application-layer encryption for RAG?', 'App-layer when multiple services need same ciphertext; pgcrypto when only Postgres-backed admin API reads sensitive connector credentials.'),
    ],
    "rag-compaction-schedule-tuning": [
        ('Compaction schedule for RAG vector stores?', 'LSM-based vector DBs need periodic compaction after bulk ingest — schedule off-peak, monitor write amplification during reindex week.'),
        ('Kafka compaction vs vector compaction?', 'Do not conflate — Kafka log compaction for publish events; vector store compaction merges segments after delete tombstones from CDC stream.'),
        ('Tune compaction too aggressive symptoms?', 'Ingest latency spikes, IO saturation on vector nodes, failed embed jobs timing out during compaction window.'),
        ('Automate compaction after corpus delete?', 'Tenant offboarding triggers delete API then scheduled compaction job — verify disk reclaimed within 24h SLA.'),
    ],
    "rag-component-library-documentation": [
        ('Document RAG UI components how?', 'Storybook stories for citation variants, loading states, empty retrieval, faithfulness warning badges — with copy-paste props for embed widget integrators.'),
        ('What props document for RAG chat bubble?', 'citations array schema, onCitationClick handler, faithfulnessStatus enum, streaming vs complete render modes.'),
        ('Keep design system in sync with RAG API changes?', 'Version widget SDK alongside corpus API — breaking citation schema change triggers major semver on component library.'),
        ('Accessibility docs for RAG components?', 'Keyboard nav to expand citations, screen reader labels for source cards, focus trap in citation modal — document in each component MDX page.'),
    ],
    "rag-compression-lz4-zstd": [
        ('Compress what in RAG pipelines?', 'Chunk text at rest in object storage, gRPC embed payloads, Kafka document events — not already-quantized vectors unless using PQ with separate concern.'),
        ('LZ4 vs zstd for RAG ingest?', 'LZ4 for low-latency inline compress on API ingest; zstd level 3–5 for cold archive of raw PDFs where ratio matters more than CPU.'),
        ('Decompression latency impact on retrieval?', 'Negligible for chunk text <8KB. Profile if storing megabyte JSON metadata blobs — split metadata instead of extreme compression.'),
        ('Compress embeddings on disk?', 'Some vector DBs use internal compression; raw float32 dumps use zstd for snapshot transfer between blue-green clusters.'),
    ],
    "rag-conftest-manifest-validation": [
        ('What RAG manifests validate with Conftest?', 'Kubernetes deploys for embed workers, corpus ACL Rego policies, ingress TLS requirements, resource limits on GPU jobs.'),
        ('OPA policies for RAG tenant isolation?', 'Rego deny Deployments missing tenant network policy label, deny public Ingress on internal-only embed service.'),
        ('CI gate before RAG index publish?', 'Conftest on Helm values — require corpus_version label, deny latest tag on embed image, require PodSecurity restricted.'),
        ('Conftest vs admission controller?', 'Conftest in CI catches bad configs pre-merge; admission controller catches bypass. Use both for defense in depth on RAG platform.'),
    ],
    "rag-connection-pooling-tuning": [
        ('Pool sizing for RAG metadata Postgres?', 'Interactive retrieval: pool size ≈ expected concurrent requests per pod, not total cluster QPS. Ingest workers need separate larger pool or direct connection.'),
        ('PgBouncer transaction vs session mode for RAG?', 'Transaction mode for stateless retrieval API; session mode if using prepared statements or LISTEN for CDC notify — many ORMs need session mode.'),
        ('Pool exhaustion symptoms in RAG?', 'Retrieval timeout while Postgres CPU idle — classic pool wait. Alert on pool waiting count, not just query duration.'),
        ('Separate pools for read vs write?', 'Yes — read replica pool for retrieval ACL checks; primary pool for ingest metadata writes. Prevents batch ingest starving interactive reads.'),
    ],
    "rag-connection-proxy-pgbouncer": [
        ('Why PgBouncer in front of RAG Postgres?', 'Thousands of short metadata lookups per retrieval request from horizontally scaled pods — PgBouncer multiplexes to avoid Postgres connection limit exhaustion.'),
        ('Max client connections formula?', 'RAG API pods × pool per pod + ingest workers + admin overhead. Set max_client_conn accordingly; default_pool_size to Postgres max_connections / num_pools.'),
        ('Pgbouncer with vector-adjacent pgvector?', 'If metadata and vectors share Postgres with pgvector, isolate pools — heavy ANALYZE on vector table should not block ACL lookup pool.'),
        ('Failover behavior through PgBouncer?', 'On primary failover, PgBouncer resumes to new primary if DNS updated — RAG apps need retry with backoff on connection reset during failover window.'),
    ],
    "rag-consent-management-records": [
        ('Consent records for RAG over user uploads?', 'Store consent scope — which upload batches may be embedded, shared across tenants or not, retention end date. Block ingest job without valid consent record ID.'),
        ('GDPR erasure and RAG indexes?', 'Erasure request triggers delete by user_id across Postgres metadata, vector chunk delete API, and completion log purge — consent record marks legal basis withdrawn.'),
        ('Audit consent for RAG training use?', 'Distinguish retrieval-only consent vs fine-tuning consent in record type. Mixing them creates regulatory exposure on enterprise deals.'),
        ('Consent version migration?', 'When policy updates, re-consent workflow before indexing new user content — corpus_version bump excludes pre-consent chunks via metadata filter.'),
    ],
    "rag-consent-screen-ux-patterns": [
        ('UX patterns for RAG data collection consent?', 'Plain language: what documents are indexed, who can query them, retention period. Separate toggles for upload-to-RAG vs chat logging.'),
        ('Pre-checked boxes for RAG consent?', 'Avoid — GDPR and CPRA discourage pre-checked broad consent. Default off for optional corpus contribution.'),
        ('Show consent impact in RAG settings?', 'Live preview: "3 documents shared with team search" with revoke per document. Reduces surprise when colleagues find uploaded content.'),
        ('Mobile consent for RAG upload?', 'Bottom sheet with scroll-to-enable accept, link to full policy, easy revoke in settings — same patterns as photo upload consent.'),
    ],
    "rag-consumer-group-rebalance": [
        ('Rebalance impact on RAG ingest consumers?', 'During Kafka rebalance, document publish lag spikes — retrieval serves stale corpus. Monitor consumer lag alert during deploys scaling ingest workers.'),
        ('Static membership for RAG ingest?', 'Use cooperative-sticky assignor; increase session timeout cautiously. Frequent pod restarts during K8s rollouts trigger rebalance storms without static membership.'),
        ('Pause consumption during rebalance?', 'Some clients expose rebalance listener — flush in-flight embed batches before partition revoke to avoid duplicate chunk IDs.'),
        ('Separate consumer groups per tenant tier?', 'Enterprise tenants on dedicated group isolate rebalance blast radius from shared free-tier ingest consumers.'),
    ],
    "rag-container-image-scanning-gate": [
        ('Scan what images in RAG platform?', 'Embed worker GPU images, retrieval API, ingest sidecars, chatops bot — any image with network access to corpus data.'),
        ('Block deploy on CRITICAL CVE?', 'Yes for CVSS ≥9 with known exploit in embed API image. Waivers require security ticket with expiry before merge to prod cluster.'),
        ('Base image update cadence for RAG?', 'Weekly rebuild on patched Python/CUDA base even without app changes — ML images accumulate CVEs faster than slim API images.'),
        ('Scan vs runtime Falco for RAG?', 'Scan at CI gate; Falco detects anomalous syscalls at runtime — shell spawn in embed container should never happen.'),
    ],
    "rag-container-queries-responsive": [
        ('Container queries for RAG embed widget?', 'Size citation panel and input bar by widget container width, not viewport — embeds in sidebar vs full page need different breakpoints.'),
        ('@container vs media query for RAG UI?', 'Container queries when widget lives in customer portal iframe; media queries only for first-party full-page chat.'),
        ('Minimum container width for RAG chat?', 'Below 320px container, collapse citation sidebar to accordion — test in Storybook with container query units cqw.'),
        ('Fallback browsers without container queries?', 'Feature query @supports (container-type: inline-size) with viewport fallback layout — document degradation in embed integration guide.'),
    ],
}

FAQS.update(MORE_FAQS)

EXPANSIONS = {
    "rag-bias-detection-evaluation": """
## Slice-based retrieval eval for RAG

A compliance chatbot retrieved EU GDPR articles for English queries but consistently surfaced US-state privacy blog posts for Spanish queries — not because the model was biased, but because the Spanish corpus was 90% US marketing translations. Slice evals on `language` and `jurisdiction` metadata caught it; aggregate nDCG looked fine.

Build a slice matrix for RAG: rows are cohorts (language, region, doc age, source tier), columns are retrieval metrics (recall@5, MRR, nDCG@10) and downstream faithfulness. Pre-register blocking slices before index publish.

## Counterfactual query pairs

Swap protected or proxy markers in identical questions:

- "What is maternity leave policy for employees in Berlin?"
- "What is maternity leave policy for employees in Munich?"

Same intent, different geography — large divergence in retrieved doc IDs warrants corpus or boost investigation. For RAG, also counterfactualize **metadata filters** left off: same query with and without `region:EU` filter should not flip answer authority if product policy says EU-only.

```python
def retrieval_disparity(pairs: list[tuple[list[str], list[str]]]) -> float:
    # Fraction of pairs where top-1 chunk IDs differ
    diffs = sum(1 for a, b in pairs if (a[:1] != b[:1]))
    return diffs / max(len(pairs), 1)
```

Run counterfactual suites in CI on every corpus version bump — bias regressions often enter through new document batches, not model changes.
""",
    "rag-blue-green-database-migration": """
## Dual-cluster cutover for vector indexes

Blue cluster serves `corpus_v42`; green builds `corpus_v43` from scratch — new chunk boundaries, new embedding model, new HNSW graph. Never mutate blue in place during model upgrades; query latency during HNSW rebuild is unpredictable.

Cutover sequence:

1. Finish green index build and run eval gate (recall@5, faithfulness).
2. Enable shadow traffic — green answers logged but not shown.
3. Flip `ACTIVE_CORPUS` alias in config service.
4. Keep blue read-only 72h for rollback.

```yaml
# retrieval-config ConfigMap
active_corpus: v43
rollback_corpus: v42
shadow_percent: 0  # was 10 during validation
```

## Postgres metadata synchronization

Document ACLs and chunk manifests live in Postgres; vectors live in Pinecone/Weaviate/pgvector. Blue-green must migrate both:

- Logical replication for `documents`, `chunks`, `tenant_acl` tables.
- Vector store uses separate index alias — `index-v43-green` promoted after row-count parity check.

Validate with checksum query: `SELECT corpus_version, COUNT(*), SUM(hashtext(chunk_id)) FROM chunks GROUP BY 1` on blue vs green.

## Rollback without citation breakage

Chunk IDs must be stable across versions or citations in user history break. Version chunk IDs as `{doc_id}:v{corpus_version}:{seq}` during migration window, maintain redirect map from old IDs for 30 days post-cutover.
""",
    "rag-bm25-elasticsearch-tuning": """
## k1 and b on mixed-length RAG corpora

Enterprise knowledge bases mix 50-token error code entries with 3,000-token runbooks. Default `b=0.75` penalizes runbooks heavily — a runbook mentioning "timeout" twenty times beats a precise error code doc mentioning "ERR_CONNECTION_TIMEOUT" once.

Start tuning with a labeled set of 200 real user queries from search logs:

| Parameter | Symptom if wrong | Direction to adjust |
|-----------|------------------|---------------------|
| k1 too low | Repeated keywords in long docs don't rank | Increase toward 1.6 |
| b too high | Short authoritative titles lose to long FAQs | Decrease toward 0.4 |
| Both default | Exact SKU queries miss | Add keyword subfield, filter first |

## Hybrid RRF with BM25

Pure vector RAG misses rare strings; pure BM25 misses paraphrase. Production default:

```json
POST /_search
{
  "query": {
    "hybrid": {
      "queries": [
        { "match": { "content": { "query": "reset SSO password" } } },
        { "knn": { "field": "embedding", "query_vector": [...], "k": 50 } }
      ]
    }
  },
  "rank": { "rrf": { "rank_constant": 60 } }
}
```

Tune BM25 boosts on `title^3`, `error_code` keyword field, and `jurisdiction` filter before touching vector weight — lexical precision fixes are cheaper than re-embedding.

## Eval loop tying BM25 to answer quality

Weekly job: for each golden query, log BM25 rank vs vector rank of the chunk that supported the correct answer. If correct chunk is BM25 rank 15 but vector rank 2, your boosts are wrong for that query class. Slice by `doc_type` to find systematic misses.
""",
    "rag-breach-notification-playbook": """
## RAG-specific breach scenarios

Standard breach playbooks miss vector-store paths:

- **Over-broad retrieval filter bug** exposes Tenant A docs to Tenant B queries — log evidence shows cross-tenant chunk IDs in retrieval traces.
- **Snapshot leak** — S3 bucket with HNSW backup world-readable; embeddings reconstruct approximate source text.
- **Prompt log exfiltration** — completion logs contain retrieved PII snippets without redaction.

Each scenario has different notification triggers and evidence preservation steps.

## 72-hour timeline template

| Hour | Engineering | Legal/comms |
|------|-------------|-------------|
| 0–4 | Contain: disable ingest, read-only retrieval, preserve logs | Assess personal data scope |
| 4–24 | Forensics: query audit, chunk access list, IAM review | Draft regulator notification if required |
| 24–72 | Remediation plan, rotate keys, patch ACL | Customer notification if high risk |

Clock starts at **confirmed** unauthorized access, not at root-cause analysis completion.

## Evidence preservation for RAG

Before any reindex or log rotation:

```bash
# Immutable export — do not run on live writer without snapshot
aws s3 sync s3://rag-query-logs/ s3://legal-hold-breach-2026-07/ --storage-class GLACIER_IR
pg_dump --table=retrieval_audit --format=custom > audit_breach.dump
```

Include: `request_id`, `tenant_id`, `chunk_ids[]`, `corpus_version`, `principal`, timestamp. Legal needs to answer which documents were retrievable by whom during the exposure window.
""",
    "rag-cache-aside-vs-read-through": """
## Cache-aside for retrieval bundles

Application owns the orchestration — embed, search, rerank — so cache-aside gives explicit keys:

```typescript
function bundleKey(tenant: string, corpusVersion: string, query: string): string {
  const q = createHash("sha256").update(query.toLowerCase().trim()).digest("hex").slice(0, 16);
  return `rag:bundle:${tenant}:${corpusVersion}:${q}`;
}
```

**Always include `corpusVersion`.** Publishing HR policy v2 without bumping version serves v1 chunks from cache — compliance failure, not cache bug.

On miss: acquire Redis lock (`SET lock NX EX 10`), fetch origin, set with TTL 3600, release lock. Waiters retry cache read before hitting origin again.

## Read-through for tenant config

Tenant-specific retrieval config — reranker model, max chunks, ACL template — fits read-through behind a small cache service:

```python
class TenantConfigCache:
    def get(self, tenant_id: str) -> TenantConfig:
        cached = self.redis.get(f"tenant_cfg:{tenant_id}")
        if cached:
            return TenantConfig.parse_raw(cached)
        cfg = self.db.load_tenant_config(tenant_id)
        self.redis.setex(f"tenant_cfg:{tenant_id}", 300, cfg.json())
        return cfg
```

Callers use one API; cache population is transparent. Invalidate on admin config update via pub/sub channel.

## When not to cache

Never cache: authorization decisions, cross-tenant filtered results keyed without tenant, completions containing user PII. TTL alone does not fix wrong-tenant keys — schema review cache keys in PR checklist.
""",
    "rag-cache-stampede-prevention": """
## Thundering herd on corpus republication

Republication invalidates `rag:embed:*:v42:*` — ten thousand keys expire within the same second if TTL is uniform. Every concurrent user query misses and hits the embed API together.

**Fix: jitter TTL at write time**

```python
import random
base_ttl = 3600
ttl = base_ttl + random.randint(0, 600)  # spread expirations over 10 minutes
redis.setex(key, ttl, value)
```

**Fix: stale-while-revalidate header on retrieval HTTP layer**

Serve stale bundle with `X-Corpus-Version` header while background refresh runs. Client or gateway decides if stale version is acceptable.

## Single-flight implementation

Only one goroutine/thread per key fetches from origin:

```go
var group singleflight.Group

func GetBundle(ctx context.Context, key string) (Bundle, error) {
    v, err, _ := group.Do(key, func() (interface{}, error) {
        return fetchFromOrigin(ctx, key)
    })
    return v.(Bundle), err
}
```

`golang.org/x/sync/singleflight` collapses concurrent misses. Log `singleflight_shared` metric — high values mean stampede was prevented.

## Alerting before the cliff

Alert when:
- `embed_api_qps / embed_cache_hit_rate` derivative spikes
- Redis `connected_clients` flat but origin QPS 5× baseline
- p95 embed latency > 2× while CPU headroom exists (queueing, not compute)
""",
}

# Continue expansions for remaining slugs in part 2
EXPANSIONS_PART2 = {
    "rag-canary-analysis-flagger": """
## Flagger metrics for RAG deployments

HTTP 200 from `/health` is meaningless for RAG.canary needs custom Prometheus metrics:

```yaml
analysis:
  metrics:
  - name: rag-recall-at-5
    thresholdRange:
      min: 0.85
    interval: 1m
  - name: rag-faithfulness-score
    thresholdRange:
      min: 0.90
  - name: rag-empty-result-rate
    thresholdRange:
      max: 0.02
```

Record rules compute these from eval sidecar that runs golden queries every 30s against canary pods.

## Shadow corpus validation

Canary deployment at 10% traffic with **new** `corpus_version` label. Primary metric: `faithfulness_canary - faithfulness_primary < -0.05` triggers rollback — catches bad embed deploy before full cutover.

## Progressive traffic with Flagger

```
Canary → 10% (5 min) → 30% (10 min) → 100%
```

Each step requires metric pass. On failure, Flagger routes traffic back and optionally triggers `CorpusAliasRollback` webhook to repoint index alias.
""",
    "rag-canary-token-alerts": """
## Planting honeytoken documents

Create isolated corpus partition `canary/` with documents containing unique strings:

```
CANARY-RAG-7f3a9b2e-do-not-cite-internal-tripwire
```

Properties:
- Never appear in legitimate docs (grep CI check on main corpus).
- Indexed with same pipeline as production docs.
- ACL restricted — only security team principals should retrieve them.

## Alert pipeline

```sql
-- Stream processing on query logs
SELECT tenant_id, user_id, query_text
FROM retrieval_audit
WHERE query_text LIKE '%CANARY-RAG-7f3a9b2e%'
   OR EXISTS (SELECT 1 FROM unnest(retrieved_chunk_ids) c WHERE c LIKE 'canary:%')
```

Page immediately — indicates broken ACL filter, insider search, or prompt injection attempting exfiltration.

## Rotation without false positives

Quarterly rotation script:
1. Add new canary doc with new token.
2. Deploy index update for canary partition only.
3. Remove old canary doc after 24h dual-alert window.
4. Update alert regex.

Test rotation in staging — stale alert rules missing new token cause alert fatigue when old token appears in test data.
""",
    "rag-capacity-forecasting-models": """
## Embedding storage forecast

```
storage_bytes ≈ chunk_count × dimensions × 4 × (1 + hnsw_overhead)
hnsw_overhead ≈ 0.5 to 1.0 × raw vector bytes
```

Example: 10M chunks × 1536 dims × 4 bytes = 61 GB raw vectors → plan 120–180 GB with HNSW on NVMe.

Forecast monthly: `new_docs_per_month × avg_chunks_per_doc × bytes_per_vector`.

## Query-side GPU/CPU capacity

Embed QPS capacity ≈ `(gpu_count × batch_throughput) / avg_batch_latency`. Separate forecast for:

- **Interactive query embed** — p99 SLO driven, scale HPA on latency.
- **Batch reindex** — spot GPU pool, schedule off-peak, does not share interactive quota.

## Token generation forecast

Downstream LLM cost scales with `queries × avg_chunks × avg_chunk_tokens × generation_multiplier`. Monday 9am spike pattern differs from embed — use separate time-series model with day-of-week seasonality.

## Leading indicator dashboard

Track 30-day slope of: disk usage %, index build duration, embed queue depth p95, metadata DB connection wait. Alert when two or more trend positive simultaneously — capacity incident within 2 weeks.
""",
    "rag-catalog-datahub-amundsen": """
## Lineage: corpus → index → app

DataHub lineage graph:

```
S3 corpus bucket → Airflow ingest DAG → pgvector index → RAG API → Customer portal
```

Each edge carries `corpus_version`, `embedding_model`, `last_eval_recall_at_5`. When support asks "why wrong answer?", trace from citation chunk back through lineage to ingestion job and source PDF hash.

## Required dataset properties

| Property | Example | Why |
|----------|---------|-----|
| corpus_version | v2026.07.15 | Cache and alias binding |
| chunk_strategy | markdown_header | Debug recall regressions |
| pii_classification | confidential | Access review |
| owner | team-knowledge-platform | Escalation path |
| eval_recall_at_5 | 0.91 | Publish gate |

CI writes properties on successful index build; failed eval blocks `production` tag.

## Amundsen vs DataHub for RAG teams

Both work — choose based on existing enterprise data platform. Critical feature: API to query "which indexes include dataset X?" for GDPR erasure propagation.
""",
    "rag-cdc-debezium-postgres": """
## Row-level sync to retrieval ACL

Postgres `documents` table columns: `id`, `tenant_id`, `title`, `deleted_at`, `acl_group`. Debezium captures changes → Kafka → consumer updates retrieval filter cache and vector metadata.

**Delete path:** `deleted_at` set → consumer calls vector DB delete by `document_id`, removes from BM25 index. Lag window = CDC lag — document ACL says deleted but still retrievable.

## Fail-closed on excessive lag

```python
if cdc_lag_seconds > tenant.sla.max_cdc_lag:
    raise RetrievalUnavailable("Metadata sync delayed — try again")
```

Better empty results than serving revoked content. Monitor `debezium.metrics.MMilliSecondsSinceLastEvent`.

## Exclude blob columns

Debezium connector config:

```json
"column.exclude.list": "public.documents.raw_pdf,public.documents.full_text"
```

Replicate IDs and metadata only; embed pipeline reads blobs from S3 on explicit ingest event. Keeps Kafka messages small and avoids PII in topic by accident.
""",
    "rag-cdn-cache-purge-strategies": """
## Event-driven purge on document publish

Webhook from CMS on publish/unpublish:

```typescript
async function onDocumentPublish(doc: DocumentEvent) {
  await cdn.purgeTags([`corpus:${doc.corpusId}`, `doc:${doc.id}`]);
  await rag.invalidateRetrievalCache(doc.corpusId); // app-layer
}
```

CDN purge for static rendered pages; app-layer cache purge for API retrieval bundles. Both required — CDN-only leaves API stale.

## Soft purge vs hard purge

**Soft purge** (Cloudflare, Fastly): mark stale, serve stale while revalidating — avoids origin stampede.

**Hard purge**: immediate removal — use for security retraction (PII leak, legal hold violation).

## Surge protection during mass purge

After major corpus republication, origin may see 10× revalidation QPS. Enable `stale-if-error` and rate-limit revalidation at origin with CDN shield layer.
""",
    "rag-cdn-stale-while-revalidate": """
## Cache-Control for RAG documentation portal

Public help pages rendered from CMS, search widget calls API separately:

```
Cache-Control: public, max-age=120, stale-while-revalidate=3600, stale-if-error=86400
```

User sees cached page instantly; CDN fetches fresh HTML in background. **Widget API calls are not CDN cached** — only static shell.

## Separating cache tiers

| Asset | Strategy |
|-------|----------|
| HTML help pages | SWR as above |
| JS widget bundle | long max-age + hash filename |
| `/api/retrieve` | no-store, private |
| OpenAPI spec | max-age=3600, SWR=7200 |

## Measuring SWR hit ratio

CDN analytics: `AGE` header distribution. Healthy SWR shows large fraction of responses with `AGE > max-age` (served stale while revalidating). Zero stale serves means SWR not working or max-age too long.
""",
    "rag-cert-manager-dns01": """
## Wildcard cert for multi-tenant RAG API

```
*.rag-api.example.com
rag-api.example.com
```

DNS-01 via Route53 solver — required because embed gRPC service and regional API shards don't expose HTTP-01 challenge paths.

```yaml
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: rag-api-wildcard
spec:
  dnsNames:
  - "rag-api.example.com"
  - "*.rag-api.example.com"
  issuerRef:
    name: letsencrypt-prod-dns
  secretName: rag-api-tls
```

## Renewal alerting

Certificate `Ready=False` or `RenewalTime` within 14 days → page platform team. RAG SDK clients with certificate pinning fail hard on expiry — no graceful degradation.

## Multi-cluster cert distribution

ExternalSecrets or cert-manager `Certificate` per cluster referencing same DNS name. Avoid copying `tls.crt` manually — rotation drift between clusters causes mysterious regional outages.
""",
    "rag-certificate-transparency-monitoring": """
## CT log monitoring for RAG domains

Services like crt.sh, Facebook CT Monitor, or Certstream feed alert on:

```
*.rag.example.com
embed.internal.example.com
```

Unexpected cert from unknown CA or new subdomain may indicate:
- Misconfigured cert-manager in staging using prod DNS
- Compromised DNS allowing fraudulent ACME validation
- Phishing clone of RAG chat UI

## Expected issuer allowlist

```yaml
expected_issuers:
  - "Let's Encrypt R3"
  - "Amazon RSA 2048 M03"  # ACM if used at LB
alert_on_unknown_issuer: true
```

Compare CT entries weekly against cert-manager `Certificate` status resources.

## Does not replace mTLS or pinning

CT catches **issuance** anomalies. Client pinning catches MITM with legitimately issued rogue cert. Use both layers for customer-facing RAG SDK.
""",
    "rag-changelog-compacted-topics": """
## Compacted topic for document version state

Kafka topic `document-state` keyed by `document_id`, compacted:

```json
{"document_id": "doc-8842", "corpus_version": 43, "status": "indexed", "chunk_count": 12}
```

New consumers rebuild latest state per document without reading full history — fast RAG ingest worker recovery after crash.

## Tombstones for deletion

Publish record with `value: null` for key — compaction removes doc. Consumer must propagate delete to vector index. Missing tombstone handling leaves ghost chunks retrievable forever.

## Compaction lag monitoring

`kafka.log.cleaner.max.compaction.lag.ms` exceeded → ACL updates delayed reaching indexes. Alert alongside consumer lag — both must be green before declaring ingest healthy.
""",
    "rag-chaos-monkey-game-days": """
## RAG failure injection menu

Game day scenario progression:

1. **Embed API +500ms latency** — verify timeout, cache fallback, no unbounded retry spend.
2. **Vector DB 503** — verify BM25-only degraded mode or explicit "search unavailable" response.
3. **Reranker timeout** — verify passthrough of vector top-k without rerank, logged degradation flag.
4. **Metadata DB replica lag 60s** — verify fail-closed or stale-ACL detection.

Success criteria pre-registered: max `$0.05` token spend per degraded query, no hallucinated citations when retrieval empty.

## Measure resilience quantitatively

| Metric | Pass threshold |
|--------|----------------|
| Time to detect (SLO alert) | < 3 min |
| Error budget burn during 30 min injection | < 5% weekly budget |
| User-visible wrong answers | 0 on golden set |

Run quarterly; rotate scenarios. Document rollback practiced during corpus corruption simulation.
""",
    "rag-chargeback-dispute-automation": """
## Retrieval corpora for dispute evidence

RAG over:
- Card network chargeback rules (Visa/Mastercard PDFs chunked by rule section)
- Merchant agreement clauses with effective dates
- Historical dispute outcomes labeled won/lost with reason codes

Generation produces evidence packet draft with mandatory `[chunk_id]` citations per claim.

## Jurisdiction and amount guardrails

```python
def draft_dispute(transaction, amount_cents):
    chunks = retrieve(
        query=transaction.dispute_reason,
        filters={"jurisdiction": transaction.merchant_region, "status": "current"},
    )
    draft = generate(chunks, citation_required=True)
    if amount_cents > AUTO_SUBMIT_LIMIT:
        queue_human_review(draft)
    return draft
```

Faithfulness check each claim against cited chunk before queue or submit.

## Audit trail requirements

Log: `transaction_id`, `chunk_ids[]`, `model_version`, `human_edits_diff`, `submitted_at`. Payment networks audit evidence provenance, not LLM eloquence.
""",
    "rag-chatops-incident-bots": """
## Slack bot commands for RAG on-call

```
/rag-status corpus_version
/rag-compare v42 v43 recall
/rag-runbook embed-latency-slo-burn
```

Bot retrieves runbook chunks — never invents steps. Implementation:

```python
def handle_runbook_lookup(error_signature: str) -> str:
    chunks = retrieve(f"runbook {error_signature}", filters={"doc_type": "runbook"})
    if not chunks or chunks[0].score < 0.7:
        return "No runbook found — escalate to platform."
    return summarize_with_citations(chunks, allow_only_retrieved_text=True)
```

## PagerDuty enrichment

Webhook enriches incident with: active `corpus_version`, last deploy SHA of retrieval service, embed p95 from last hour, link to Grafana RAG dashboard. Reduces MTTR for "search seems broken" vague pages.

## Tenant isolation in incident queries

Map Slack user to on-call roster entry → allowed `tenant_ids`. Never run unconstrained retrieval in shared incident channel — cross-tenant leak via bot is embarrassing and reportable.
""",
    "rag-chunk-overlap-tuning": """
## Overlap vs parent-document retrieval

Overlap duplicates content in the index — 512-token chunks with 128-token overlap means ~25% storage overhead and near-duplicate top-k results.

Alternative: 128-token chunks for search, return parent 1024-token section to LLM. Eliminates duplicate embeddings while preserving boundary context for generation.

Choose overlap when:
- Pipeline is simple (no parent-child linking)
- Storage is cheap relative to engineering time

Choose parent-document when:
- Top-k shows >30% near-duplicate chunks
- Index size or query latency already at limits

## Measuring duplicate rate in top-k

```python
def duplicate_rate(chunks: list[str], threshold: float = 0.85) -> float:
    from difflib import SequenceMatcher
    pairs = 0
    dups = 0
    for i, a in enumerate(chunks):
        for b in chunks[i+1:]:
            pairs += 1
            if SequenceMatcher(None, a, b).ratio() > threshold:
                dups += 1
    return dups / max(pairs, 1)
```

Run on eval query sample weekly. duplicate_rate > 0.3 → reduce overlap or enable dedup at query time.
""",
    "rag-chunking-strategies-compared": """
## Pipeline chaining in production

Real systems rarely use one strategy:

```python
def chunk_document(doc: ParsedDoc) -> list[Chunk]:
    if doc.format == "markdown":
        sections = markdown_header_split(doc)
    elif doc.format == "pdf":
        sections = unstructured_extract_then_semantic_split(doc)
    else:
        sections = recursive_split(doc)
    return [c for s in sections for c in split_if_oversized(s, max_tokens=768)]
```

Tag each chunk with `chunk_strategy` in metadata — debug recall regressions by strategy slice in eval dashboard.

## Eval-driven strategy selection

Run identical 100-question eval across fixed, recursive, header, semantic on **your** corpus. The winner on recall@5 may lose on answer accuracy if chunks are too small for generation — measure both.

Document the decision in ADR: "We use header + recursive because semantic added 4× index cost for 2-point recall gain."
""",
    "rag-circuit-breaker-bulkhead-patterns": """
## Independent breakers per dependency

```python
embed_breaker = CircuitBreaker(fail_max=5, reset_timeout=30)
vector_breaker = CircuitBreaker(fail_max=3, reset_timeout=60)
llm_breaker = CircuitBreaker(fail_max=5, reset_timeout=45)

@embed_breaker
def embed_query(text): ...

def retrieve(query):
    if vector_breaker.current_state == "open":
        return cached_or_bm25_fallback(query)
    ...
```

Opening embed breaker must not open LLM breaker — otherwise healthy generation path dies when only embed fails.

## Bulkhead thread pools

| Pool | Purpose | Size |
|------|---------|------|
| interactive-embed | live queries | 32 threads |
| batch-ingest-embed | reindex jobs | 64 threads, lower priority |
| rerank | cross-encoder | 16 threads |

Kubernetes: separate Deployments with resource quotas so batch ingest cannot evict interactive pods.

## Half-open probing

On half-open, send synthetic cheap query (`healthcheck-probe`) before closing breaker. Require 3/3 success over 30s. Log `breaker_state_transition` for postmortems.
""",
    "rag-citation-attribution-grounding": """
## Structured claims for automated verification

Force JSON output for high-stakes RAG:

```json
{
  "claims": [
    {"text": "Logs retained 180 days", "source_chunk_ids": ["policy:v3:4.2:07"]}
  ]
}
```

Post-process: for each claim, run NLI entailment against chunk text. Drop or flag claims below threshold before UI render.

## Citation precision vs recall tradeoff

- **High citation recall, low precision**: model cites everything, many wrong — users lose trust.
- **High precision, low recall**: few citations, all correct — may omit support for true claims.

Target precision > 0.95 on eval even if recall is 0.80. A missing citation is better than a wrong one in compliance contexts.

## Version-aware citation display

Show `effective_date` and `version` in citation UI when metadata available — user sees "Policy v3.1 (effective 2024-06-01)" not just "Policy Handbook". Reduces confusion when multiple versions retrieved.
""",
    "rag-cloud-trail-anomaly-alerts": """
## High-signal CloudTrail events for RAG

| Event | Risk |
|-------|------|
| s3:GetObject on corpus bucket from new principal | Exfiltration |
| sagemaker:InvokeEndpoint spike on embed endpoint | Cost attack |
| iam:CreateAccessKey for rag-ingest role | Persistence |
| s3:PutBucketPolicy public read | Catastrophic exposure |

Metric filter → CloudWatch alarm → PagerDuty with runbook link.

## Baseline per principal

Use CloudTrail Insights or custom anomaly detection: alert when `GetObject` count for `rag-batch-worker` role exceeds 3× 7-day hourly average. Tune to avoid false positives during scheduled reindex.

## Correlate with application audit log

CloudTrail shows AWS principal; app log shows `tenant_id` and `chunk_ids`. Join on `request_id` propagated through ingest pipeline — CloudTrail alone misses in-app authorization bugs.
""",
    "rag-cluster-autoscaler-node-pools": """
## Separate pools for ingest and query

```yaml
# ingest pool — spot tolerant
nodeSelector:
  workload: rag-ingest
tolerations:
  - key: nvidia.com/gpu
    operator: Exists
# query pool — on-demand, low latency
nodeSelector:
  workload: rag-query
```

Cluster autoscaler max nodes differ: ingest pool scales 0–50 spot; query pool 3–20 on-demand minimum 3 for HA.

## HPA + cluster autoscaler wiring

HPA scales retrieval Deployment on custom metric `embed_queue_depth`. When pods pending `Insufficient gpu`, cluster autoscaler adds nodes. **Set cluster max high enough** — HPA hitting max replicas with pending pods means node cap, not app cap.

## Scale-down delay during reindex

Set `--scale-down-delay-after-add=15m` on ingest pool — prevents thrashing when batch job completes and nodes immediately terminate before next nightly reindex.
""",
    "rag-colbert-late-interaction": """
## When ColBERT earns its storage cost

Bi-encoder recall@50 plateaus at 0.78 on legal corpus; ColBERT hits 0.89 — justified for tier-1 legal RAG where miss cost is high. For internal IT FAQ, bi-encoder + rerank within SLO is sufficient.

Storage math: ColBERT stores token embeddings per chunk. 512-token cap × 128-dim × 4 bytes × 1M chunks ≈ 256 GB vs 6 GB bi-encoder — plan NVMe and segment pruning.

## Two-stage pipeline

```
ColBERT retrieve top-200 → cross-encoder rerank top-20 → LLM
```

Full ColBERT on 10M chunks at query time needs aggressive pruning (MaxSim with candidate prefilter from BM25).

## ROI evaluation template

| Metric | Bi-encoder + rerank | ColBERT |
|--------|---------------------|---------|
| nDCG@10 | baseline | +Δ |
| p95 retrieval ms | baseline | +Δ |
| Storage $/month | baseline | +Δ |

Ship ColBERT only if faithfulness gain on golden set exceeds product threshold and Δ latency fits SLO.
""",
    "rag-cold-start-recommendations": """
## New tenant empty index

Enterprise onboarding: tenant uploads zero documents. Retrieval returns nothing — model must not hallucinate confidently.

UX states:
- "Indexing your documents (0 of N complete)"
- Fallback: general LLM with banner "Answers not from your knowledge base"
- Suggested actions: upload docs, connect Confluence, use template starter pack

## Transfer from similar tenants

With consent, bootstrap retrieval boosts from anonymized aggregate click patterns of similar industry tenants — not raw document sharing. Cold start duration SLA: recall@5 > 0.7 within 24h of first doc ingest on 50-doc starter eval.

## Measuring cold start

Metric: `hours_from_first_ingest_to_recall_threshold`. Dashboard per tenant tier — enterprise CS sees blockers when SLA missed.
""",
    "rag-cold-storage-tiering": """
## Tiering strategy for RAG assets

| Tier | Content | Access pattern |
|------|---------|----------------|
| Hot NVMe | Active corpus vectors + HNSW | ms latency queries |
| Warm S3 Standard | Current raw PDFs | ingest reprocessing |
| Cold Glacier | Superseded corpus snapshots | compliance retention |
| Delete | Expired per legal hold release | — |

Vector indexes don't belong in Glacier — rebuild cost exceeds storage savings. Archive **source** PDFs and expired index **snapshots**, not live query index.

## Lifecycle automation

```json
{
  "Rules": [{
    "Filter": {"Tag": {"corpus_status": "superseded"}},
    "Transitions": [
      {"Days": 30, "StorageClass": "STANDARD_IA"},
      {"Days": 90, "StorageClass": "GLACIER"}
    ]
  }]
}
```

Rehydrate Glacier objects 12h before scheduled rebuild job — automate in workflow orchestrator.
""",
    "rag-collaborative-filtering-embeddings": """
## Hybrid RAG + CF ranking

Base retrieval: semantic top-50. Boost scores by CF embedding similarity between user's click history and document `doc_id` embeddings.

```python
final_score = 0.7 * semantic_score + 0.3 * cf_score
```

CF wins navigational queries ("that doc about SSO I saw last week"); semantic wins novel troubleshooting.

## Privacy-preserving CF for enterprise

Train CF on aggregated team-level clicks, exclude `classification:confidential` doc IDs from CF matrix entirely. B2B customers reject individual click tracking in RAG analytics.

## Cold start fallback

Until user has ≥5 clicks, CF score = 0; rely pure semantic. Show popularity-based "Trending in your org" sidebar from aggregate non-personalized counts.
""",
    "rag-color-contrast-apca": """
## APCA on RAG citation UI

Citation snippets often render at 13px on `#1a1a2e` dark background — passes WCAG 2.1 4.5:1 for bold but fails APCA for thin regular weight. Users miss unverified claim warnings.

Test combinations:
- Citation link text on card background
- `faithfulness:warning` amber badge on white and dark themes
- Streaming cursor and partial text on gradient header

Target APCA Lc ≥ 75 for body citation text, ≥ 90 for warning badges.

## CI integration

Storybook stories per message variant → Playwright screenshot → APCA calculator script in CI fails PR if regression. Pair with axe for focus order on citation expand button.
""",
    "rag-column-encryption-pgcrypto": """
## Selective column encryption

Encrypt connector credentials and OAuth refresh tokens in Postgres:

```sql
INSERT INTO rag_connectors (tenant_id, config_enc)
VALUES ($1, pgp_sym_encrypt($2::text, current_setting('app.enc_key')));
```

Keep `tenant_id`, `connector_type`, `status` plaintext for listing queries. Decrypt only in ingest worker after row fetch — never in WHERE clause (no index on ciphertext).

## Rotation with envelope keys

Wrap `app.enc_key` with KMS CMK; rotate CMK annually via `pgp_sym_decrypt` → reencrypt migration script during maintenance window. Document which columns encrypted in schema migration comments.
""",
    "rag-compaction-schedule-tuning": """
## Vector store compaction windows

After bulk delete (tenant offboarding), schedule compaction during off-peak:

```
Sunday 02:00 UTC — vector segment merge job
Monitor: disk_write_bytes, query_latency_p99 during window
```

Abort compaction if p99 query latency exceeds SLO — resume next window.

## Kafka vs vector compaction

Don't conflate: Kafka log compaction for `document-state` topic; vector DB segment merge for tombstone-heavy indexes. Both needed; separate runbooks and on-call dashboards.
""",
    "rag-component-library-documentation": """
## Storybook coverage for RAG widget states

Required stories:
- `ChatMessage/Cited` — inline [1] links
- `ChatMessage/UnverifiedClaim` — amber warning badge
- `ChatMessage/EmptyRetrieval` — honest "no docs found"
- `ChatMessage/Streaming` — partial text + loading citation slot

Each story documents props table: `citations: Citation[]`, `faithfulnessStatus`, `onCitationClick`.

## SDK semver coupling

Breaking change to citation JSON schema → major bump `@company/rag-widget`. Document migration guide in Storybook MDX and changelog — embed customers pin versions and miss silent breakage otherwise.
""",
    "rag-compression-lz4-zstd": """
## Compression choices by RAG stage

| Stage | Algorithm | Rationale |
|-------|-----------|-----------|
| Kafka doc events | lz4 | speed |
| S3 raw PDF archive | zstd-3 | ratio |
| gRPC embed batch | lz4 | low CPU on API |
| Index snapshot transfer | zstd-5 | bandwidth |

Don't compress float32 vectors in app code if vector DB handles internal quantization — double compression wastes CPU.

## Benchmark before enabling

On representative chunk JSON (avg 2KB): measure compress+decompress p99. If adds >1ms per chunk at retrieval, compress at rest only, not on wire for hot path.
""",
    "rag-conftest-manifest-validation": """
## Rego policies for RAG deployments

```rego
deny[msg] {
  input.kind == "Deployment"
  input.metadata.labels.app == "rag-embed"
  not input.spec.template.metadata.labels.corpus_version
  msg := "rag-embed Deployment missing corpus_version label"
}

deny[msg] {
  input.spec.template.spec.containers[_].image == "rag-api:latest"
  msg := "rag-api must not use latest tag"
}
```

Run `conftest test -p policy/ k8s/` in CI on every Helm render.

## Tenant isolation policy

Deny Ingress with `auth: none` on embed service. Require `NetworkPolicy` label for tenant-scoped namespaces. Conftest catches regressions before kubectl apply.
""",
    "rag-connection-pooling-tuning": """
## Pool sizing formula

```
pool_size_per_pod = (expected_concurrent_requests × avg_query_duration_ms) / 1000
total_connections = pool_size_per_pod × pod_count
```

Keep total < Postgres `max_connections` × 0.7. RAG retrieval does short ACL lookups — pool wait hurts more than query time.

## Separate read/write pools

- **Read pool** → replica: `SELECT acl, chunk_meta WHERE doc_id = ANY($1)`
- **Write pool** → primary: ingest metadata upserts

Never share pool between batch ingest and interactive — ingest holds connections during long transactions.
""",
    "rag-connection-proxy-pgbouncer": """
## PgBouncer for horizontally scaled RAG API

200 pods × 10 pool size = 2000 client connections → multiplex to 100 server connections on Postgres.

```ini
[databases]
rag_meta = host=postgres-primary dbname=rag

[pgbouncer]
pool_mode = transaction
max_client_conn = 2000
default_pool_size = 20
```

Use **transaction mode** for stateless retrieval handlers. **Session mode** only if using prepared statements extensively.

## Failover behavior

On Patroni failover, PgBouncer reconnects to new primary if DNS updates. RAG apps need connection retry with jitter — transient `connection reset` during 30s failover window is normal.
""",
    "rag-consent-management-records": """
## Consent record schema for uploads

```json
{
  "consent_id": "cst_8842",
  "user_id": "usr_991",
  "scope": ["embed", "team_retrieval"],
  "excludes_fine_tuning": true,
  "expires_at": "2027-01-01T00:00:00Z",
  "policy_version": "2026.03"
}
```

Ingest job rejects documents without valid `consent_id` reference when `require_consent: true` on tenant.

## Erasure propagation

GDPR erasure request:
1. Mark consent withdrawn
2. Delete chunks by `user_id` in vector index
3. Purge completion logs
4. Confirm catalog lineage updated

Block 72h re-index from backup without erasure filter — restores deleted data.
""",
    "rag-consent-screen-ux-patterns": """
## Plain-language RAG consent copy

Bad: "We may process your data to improve AI services."

Good: "Documents you upload will be searchable by members of Team Alpha until you remove them. We do not use your uploads to train models shared with other customers."

Separate toggles: upload-to-RAG vs chat history retention vs analytics.

## Revocation UX

Settings page lists indexed documents with per-doc "Remove from search" — immediate API call triggers delete pipeline, not "request processed in 30 days" without feedback.
""",
    "rag-consumer-group-rebalance": """
## Rebalance storm during K8s rollout

Scaling ingest Deployment from 10→20 pods triggers partition rebalance — publish lag spikes 2–5 min, retrieval serves stale corpus.

Mitigations:
- `cooperative-sticky` assignor
- `group.instance.id` static membership where supported
- Roll pods gradually maxSurge=1 during peak hours

## Rebalance listener flush

```java
consumer.subscribe(topics, new ConsumerRebalanceListener() {
  public void onPartitionsRevoked(Collection<TopicPartition> partitions) {
    flushInFlightEmbedBatches();  // avoid duplicate chunk IDs
  }
});
```

Alert on `records-lag-max` derivative during deploys — automated rollback if lag > threshold 10 min.
""",
    "rag-container-image-scanning-gate": """
## CI gate policy

```yaml
# .github/workflows/scan.yml
- uses: aquasecurity/trivy-action@master
  with:
    image-ref: rag-embed:${{ github.sha }}
    exit-code: 1
    severity: CRITICAL,HIGH
    ignore-unfixed: false
```

CRITICAL with exploit → block merge. HIGH → ticket required with 7-day SLA waiver max.

## CUDA base image cadence

Rebuild embed GPU image weekly on patched `nvidia/cuda` base even if app code unchanged — ML images accumulate CVEs faster than distroless API images.
""",
    "rag-container-queries-responsive": """
## Embed widget layout with @container

```css
.rag-widget {
  container-type: inline-size;
  container-name: rag;
}

@container rag (min-width: 480px) {
  .citation-panel { display: flex; width: 40%; }
}

@container rag (max-width: 479px) {
  .citation-panel { display: none; }
  .citation-accordion { display: block; }
}
```

Iframe embeds in customer portals vary width — viewport media queries break sidebar layouts.

## @supports fallback

```css
@supports not (container-type: inline-size) {
  .citation-panel { display: none; } /* mobile fallback */
}
```

Document in embed integration guide: minimum 320px container width for usable citation UX.
""",
}

EXPANSIONS.update(EXPANSIONS_PART2)


def word_count(text: str) -> int:
    return len(WORD_PAT.findall(text))


def parse_post(path: Path):
    raw = path.read_text(encoding="utf-8")
    parts = raw.split("---", 2)
    if len(parts) < 3:
        return None
    return {"path": path, "raw": raw, "fm": parts[1], "body": parts[2], "slug": path.stem}


def format_faq(faq_list):
    lines = ["faq:"]
    for q, a in faq_list:
        lines.append(f'  - q: "{q}"')
        lines.append(f'    a: "{a}"')
    return "\n".join(lines)


def update_frontmatter(fm: str, slug: str) -> str:
    fm = re.sub(r'dateModified:\s*"[^"]*"', 'dateModified: "2026-07-17"', fm)
    if slug in FAQS:
        fm = re.sub(r"faq:\n(?:  - q:.*\n    a:.*\n)+", format_faq(FAQS[slug]) + "\n", fm)
    return fm


def insert_before_resources(body: str, expansion: str) -> str:
    marker = "## Resources"
    if marker in body:
        idx = body.rfind(marker)
        return body[:idx].rstrip() + "\n\n" + expansion.strip() + "\n\n" + body[idx:]
    return body.rstrip() + "\n\n" + expansion.strip() + "\n"


SUPPLEMENTS = {
    "rag-breach-notification-playbook": """
## Regulator and customer communication boundaries

Engineering prepares factual timelines and scope estimates; legal owns external wording. Provide legal with: count of affected tenants, sample chunk IDs accessed, whether completions were logged, and whether exfiltration was read-only vs write. Never commit to "no data left our systems" until log analysis completes — RAG pipelines copy retrieved text into LLM provider logs unless zero-data-retention contracts exist.
""",
    "rag-cache-stampede-prevention": """
## Probabilistic early expiration

Probabilistic early expiration refreshes hot keys before hard TTL expiry — each read has small probability of triggering background refresh. Combined with jitter, spreads load across minutes instead of seconds. Particularly effective for embedding cache keys tied to FAQ pages queried thousands of times per hour after marketing campaign launch.
""",
    "rag-canary-analysis-flagger": """
## Wiring Flagger to corpus aliases

Flagger rollback must repoint the retrieval `corpus_version` alias, not only Kubernetes Deployment replicas. A rolled-back pod serving a bad index alias still returns wrong answers at 200 OK. Store active alias in ConfigMap; Flagger webhook or post-rollback Job flips alias when canary metrics fail.
""",
    "rag-canary-token-alerts": """
## Distinguishing test from breach

Canary alerts during CI load tests that intentionally query canary partitions need `X-Test-Run-Id` header exclusion in alert rules. Without exclusion, on-call pages on every staging deploy. Document which environments index canary tokens and which principals are expected to retrieve them.
""",
    "rag-capacity-forecasting-models": """
## Seasonal and event-driven spikes

Product launches and fiscal year-end drive RAG query spikes unrelated to steady growth — model these as multipliers on baseline forecast, not noise. Black Friday support RAG may see 8× query volume for 72 hours; capacity plan includes pre-warming embed cache and temporary HPA max bump approved in advance.
""",
    "rag-catalog-datahub-amundsen": """
## Federated search across catalog and RAG

Some teams expose DataHub search alongside RAG chat — catalog finds datasets, RAG answers questions about dataset contents. Link catalog dataset URN in chunk metadata so answers cite both human-readable title and machine lineage ID for data engineering audiences.
""",
    "rag-cdc-debezium-postgres": """
## Schema evolution with Debezium

Adding columns to `documents` table requires Debezium schema compatibility review — new nullable columns propagate automatically; renaming columns breaks consumers. Coordinate RAG ingest consumer deploy before DB migration that renames ACL columns retrieval filters depend on.
""",
    "rag-cdn-cache-purge-strategies": """
## Purge latency SLAs

Document expected purge propagation time per CDN vendor (often 30–150 seconds globally). Security retraction runbook must include verification step: request purged URL from three regions until 404 or fresh content — do not assume instant global purge.
""",
    "rag-cdn-stale-while-revalidate": """
## Vary header interactions

If RAG portal varies on `Accept-Language`, ensure CDN respects `Vary` or use separate cache keys per locale. SWR on language-agnostic HTML that embeds wrong locale strings is a common misconfiguration after i18n rollout.
""",
    "rag-cert-manager-dns01": """
## DNS propagation and LE rate limits

Let's Encrypt DNS-01 challenges fail when Route53 change hasn't propagated before self-check. Set cert-manager `dns01RecursiveNameserversOnly` and retry backoff. Staging issuer for dev clusters avoids production rate limit exhaustion during iterative Helm debugging.
""",
    "rag-certificate-transparency-monitoring": """
## Subdomain takeover and CT

CT may show cert issued for `decomm-rag-api.example.com` after DNS CNAME left pointing to unclaimed SaaS — investigate immediately even if cert is legitimate LE issuance. Pair CT monitoring with periodic DNS audit of rag-related subdomains.
""",
    "rag-changelog-compacted-topics": """
## Consumer offset reset discipline

Resetting consumer group offset on compacted topic without understanding compaction state replays stale document versions. Runbook: on offset reset, consumer must upsert by key taking max version, not blind insert.
""",
    "rag-chaos-monkey-game-days": """
## Cost guardrails during chaos

Embed API chaos without token budget caps can burn thousands of dollars in retry loops. Set per-tenant and global spend limits before game day; verify limits trigger during injection. Post-game report includes actual spend delta vs baseline hour.
""",
    "rag-chargeback-dispute-automation": """
## Network-specific evidence formats

Visa VROL and Mastercard Mastercom require different field layouts — RAG templates per network prevent submitting prose paragraphs where structured codes required. Retrieval filters `network:visa` vs `network:mastercard` on rule corpus chunks.
""",
    "rag-chatops-incident-bots": """
## Rate limiting bot retrieval

Incident channels trigger many simultaneous `/rag-runbook` invocations during Sev1 — rate limit bot retrieval per channel to avoid hammering vector DB. Queue requests with "fetching runbook..." ephemeral message.
""",
    "rag-chunk-overlap-tuning": """
## Token counting consistency

Chunk overlap tuning must use same tokenizer as embedding model — character-based splitters misestimate overlap when switching from `text-embedding-3-small` to a model with different BPE boundaries. Re-measure overlap in tokens after any embed model change.
""",
    "rag-chunking-strategies-compared": """
## Re-index cost by strategy

Semantic and agentic chunking increase index-time compute — budget 4–10× wall clock vs recursive on same corpus. Schedule strategy upgrades during maintenance window with embed GPU pool pre-scaled; communicate search quality improvement timeline to stakeholders.
""",
    "rag-circuit-breaker-bulkhead-patterns": """
## Breaker metrics in Grafana

Dashboard panel per breaker: state (closed/open/half-open), failure rate, time in current state. On-call recognizes "vector breaker open 12 min" faster than generic 503 spike. Alert if any breaker open >5 min during business hours.
""",
    "rag-citation-attribution-grounding": """
## User trust studies and citation UX

A/B test citation UI: inline expandable vs footer-only. Track verification click-through rate — low clicks with high thumbs-down suggests citations present but not usable (wrong section linked). Iterate on snippet length shown in expand panel.
""",
    "rag-cloud-trail-anomaly-alerts": """
## Cross-account and assumed-role visibility

RAG ingest may use assumed roles into customer S3 buckets — CloudTrail in customer account may not forward to your SIEM. Document shared responsibility: customer enables trail delivery for buckets RAG reads; your alerts cover only your account events.
""",
    "rag-cluster-autoscaler-node-pools": """
## GPU node pool pre-warming before reindex

Scheduled reindex Job submits 30 min before scale-up trigger — autoscaler adds GPU nodes while Job pending, avoiding cold-start on first embed batch. Cost: idle GPU minutes vs faster reindex completion — tune per monthly reindex schedule.
""",
    "rag-colbert-late-interaction": """
## Quantization for ColBERT indexes

Product quantization reduces ColBERT storage 4× with modest recall hit — evaluate PQ on legal hold corpus before full deploy. Keep full-precision index for subset of high-value documents if PQ fails eval on critical queries.
""",
    "rag-cold-start-recommendations": """
## Starter corpus packs by vertical

Ship industry starter packs (healthcare compliance templates, fintech policy stubs) tenants can opt into — accelerates cold start without cross-tenant data leak when packs are generic non-customer content. Track opt-in rate in onboarding funnel analytics.
""",
    "rag-cold-storage-tiering": """
## Legal hold overrides lifecycle

S3 lifecycle rules must respect legal hold object lock — superseded corpus with active hold stays in Standard until hold released. RAG compliance officer approves lifecycle policy exceptions; automate hold tag from catalog `legal_hold: true` metadata.
""",
    "rag-collaborative-filtering-embeddings": """
## Feedback loop hygiene

Downrank documents users clicked but immediately thumbs-downed — click alone is positive signal noise. CF training matrix should use dwell time or explicit helpfulness rating when available from RAG widget analytics.
""",
    "rag-color-contrast-apca": """
## Dark mode citation cards

Many RAG widgets default dark mode — test APCA on `#2d2d44` card background with `#8b8bff` link color common in dev themes. Fails APCA more often than white-background Storybook stories suggest.
""",
    "rag-column-encryption-pgcrypto": """
## Search on encrypted fields

If product requires searching encrypted connector names, use blind index (HMAC of normalized value) stored separately — never substring search on ciphertext. Document blind index rotation paired with encryption key rotation.
""",
    "rag-compaction-schedule-tuning": """
## Compaction vs query SLO conflict

If compaction window overlaps business hours in global product, split vector cluster by region — APAC compaction during APAC off-peak. Single global window creates predictable latency spikes for someone always.
""",
    "rag-component-library-documentation": """
## Visual regression for citation states

Chromatic or Percy snapshots on citation and warning badge variants catch CSS regressions that unit tests miss. Include dark mode and 320px width containers in snapshot matrix.
""",
    "rag-compression-lz4-zstd": """
## Kafka compression.type cluster default

Set broker `compression.type=lz4` for document ingest topics — producers inherit default. zstd on broker for archive topics replicated to cold analytics cluster only.
""",
    "rag-conftest-manifest-validation": """
## Policy test fixtures

Maintain `tests/conftest/good/` and `tests/conftest/bad/` manifest fixtures — CI runs conftest expecting N deny messages on bad set. Prevents Rego policy edits that accidentally allow `latest` tag regression.
""",
    "rag-connection-pooling-tuning": """
## ORM pool vs driver pool double pooling

Django/SQLAlchemy pool behind PgBouncer doubles pooling — set ORM pool to null or size 1 when PgBouncer in transaction mode. Misconfiguration shows as mysterious connection timeouts under moderate load.
""",
    "rag-connection-proxy-pgbouncer": """
## Prepared statement pitfalls

PgBouncer transaction mode breaks named prepared statements some ORMs create — disable prepared statements in SQLAlchemy `connect_args` or use session mode for those code paths. Symptom: `prepared statement already exists` errors sporadically under load.
""",
    "rag-consent-management-records": """
## Consent export for audits

SOC2 auditor requests proof user consented to indexing — export consent records joined to document IDs still in index. Orphan docs without consent record fail audit; automated nightly job flags orphans for deletion.
""",
    "rag-consent-screen-ux-patterns": """
## Accessibility of consent flows

Consent sheet must trap focus, announce purpose via screen reader, and expose revoke in same settings path — WCAG 2.2 focus not obscured applies to modal consent over RAG upload dropzone.
""",
    "rag-consumer-group-rebalance": """
## Partition count planning

Under-partitioned ingest topic causes large rebalance blast radius — increase partitions before peak season, accepting one-time rebalance during low traffic. Rule of thumb: partitions ≥ max consumer count expected during scale events.
""",
    "rag-container-image-scanning-gate": """
## SBOM attachment to deploy artifacts

Store Trivy SBOM JSON alongside each embed image in artifact registry — compliance asks for package list months after deploy when CVE disclosed. Link SBOM hash to deployed digest in change record.
""",
    "rag-container-queries-responsive": """
## Testing embed in customer sites

Integration test loads widget in iframe at 280px, 480px, 768px container widths — viewport fixed at 1920 to prove container queries work independent of viewport. Catches regressions when developers test full-page only locally.
""",
}


def main():
    with open("/tmp/b09_chunk_3.json") as f:
        slugs = [x["slug"] for x in json.load(f)]

    expanded = 0
    already_ok = 0
    still_under = []

    for slug in slugs:
        path = BLOG / f"{slug}.md"
        if not path.exists():
            still_under.append((slug, 0, "missing"))
            continue
        post = parse_post(path)
        if not post:
            still_under.append((slug, 0, "parse error"))
            continue

        w_before = word_count(post["body"])
        body = post["body"]
        fm = update_frontmatter(post["fm"], slug)

        if w_before >= TARGET:
            # Still update FAQ/dateModified if needed
            new_raw = f"---{fm}---{body}"
            if new_raw != post["raw"]:
                path.write_text(new_raw, encoding="utf-8")
            already_ok += 1
            continue

        if slug in EXPANSIONS and EXPANSIONS[slug].strip()[:40] not in body:
            body = insert_before_resources(body, EXPANSIONS[slug])

        if slug in SUPPLEMENTS and SUPPLEMENTS[slug].strip()[:40] not in body:
            body = insert_before_resources(body, SUPPLEMENTS[slug])

        w_after = word_count(body)
        new_raw = f"---{fm}---{body}"
        if new_raw != post["raw"]:
            path.write_text(new_raw, encoding="utf-8")
            expanded += 1
            print(f"OK {slug}: {w_before} -> {w_after}")

        if w_after < TARGET:
            still_under.append((slug, w_after, "under target"))
        elif w_before >= TARGET:
            already_ok += 1

    print(f"\nExpanded: {expanded}, Already OK: {already_ok}")
    if still_under:
        print("Still under 1200:")
        for s, w, reason in still_under:
            print(f"  {s}: {w} ({reason})")


if __name__ == "__main__":
    main()
