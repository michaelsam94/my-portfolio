#!/usr/bin/env python3
from pathlib import Path

# Unique final sections — one per slug still under 1200 words
FINAL = {
"agent-tax-calculation-vat-gst": """
## Stripe Tax vs custom rules engine

Teams under $5M ARR often start with Stripe Tax or Paddle as merchant of record to defer nexus research. When you graduate to Avalara AvaTax for multi-entity structures, agent tools stay identical — only the `TaxService` adapter swaps. Run dual-write shadow mode for one billing cycle comparing line-level tax amounts; finance signs off before cutover. Agent prompts and UI strings never mention provider names to end users unless white-label contract requires transparency.
""",
"agent-timeseries-anomaly-alerting": """
## SLO dashboards for agent product reviews

Weekly product review should include one slide on agent SLIs: success rate, p95 latency, token anomaly flags fired, and false positive rate on tenant spikes. Tie anomaly thresholds to business events — product launch +200% traffic is expected; update baseline override with start/end datetime rather than muting alerts globally. Document overrides in incident ticket for audit trail.
""",
"agent-synthetic-media-labeling": """
## User-generated upload vs model-generated

When users upload photos for agent inpainting, final manifest must chain `c2pa.ingredient` for upload hash and `c2pa.edited` for model pass — support queries distinguish customer photo from wholly synthetic output. DMCA and impersonation workflows route differently; conflating labels creates legal exposure in deepfake disputes.
""",
"agent-subresource-integrity-hashes": """
## Supply chain SBOM linkage

Link SRI manifest entries to CycloneDX component hash in release artifact — security team correlates CVE in dependency with exact deployed JS bundle hash. When Dependabot PR bumps library, CI regenerates SRI in same pipeline job that builds production HTML template, preventing drift between package-lock and deployed integrity attribute.
""",
"agent-token-budget-compression": """
## Compression interaction with tool approval records

Tool approval JSON and user consent timestamps must be copied verbatim into a `non_compressible` list in the compressor — never summarized into prose. Regulators reviewing agent-mediated trades ask for exact approval payload hash; summarization destroys evidentiary value even if model still "remembers" outcome textually.
""",
"agent-storybook-visual-regression": """
## Dark mode badge contrast on approval cards

Compliance demos often run dark theme; red danger border on `#1a1a1a` background failed WCAG while light theme snapshots passed Chromatic. Add dedicated `ApprovalCardDarkDanger` story with a11y addon assertion on contrast ratio ≥ 4.5:1 for border and label text — pixel diff alone missed accessibility regression.
""",
"agent-toil-reduction-automation": """
## Change failure rate for automation

Track deploy frequency and failure rate of automation Lambdas separately from product services — broken janitor script causes more toil than manual SQL if it cancels healthy runs. Feature flag `janitor.enabled` default true with metric `janitor_cancelled_healthy` should stay zero; alert if positive.
""",
"agent-table-bloat-vacuum-tuning": """
## Read replica lag during vacuum on primary

Heavy autovacuum on primary generates WAL volume spiking replica apply lag — agent read-heavy dashboards querying replica show stale message counts during vacuum storm. Monitor `pg_stat_replication.replay_lag` correlated with `n_dead_tup` on primary; schedule aggressive vacuum during low read replica dependency window.
""",
"agent-synonym-graph-expansion": """
## Synonym injection attacks

Malicious tenant admin could propose synonym edge equating competitor trademark to their product — human approval queue for graph writes in multi-tenant SaaS. Rate-limit synonym API; audit log `who_added_edge` for enterprise compliance customers reviewing retrieval behavior quarterly.
""",
"agent-subscription-billing-dunning": """
## Dunning email localization

Past_due emails must pull currency and amount from Stripe invoice object — localized template per locale with legal footer variants. Agent-generated email body prohibited for dunning; only merge fields from billing service prevent wrong language decimal separators confusing EU customers.
""",
"agent-stream-processing-windowing": """
## Window boundary clock skew tests

Integration test sends events with `event_time` one second before and after window boundary — assert correct bucket assignment and single emission after lateness closes. CI fails if daylight saving transition bug regresses bucketing for US Eastern tenants on March second Sunday.
""",
"agent-two-tower-retrieval": """
## Negative sampling bias toward head queries

Hard negative mining overweighted by head queries makes tail product names retrieve worse after retrain — stratify mining by query frequency decile and cap negatives per decile in weekly training batch. Eval report MRR sliced by decile before promoting new tower to production alias.
""",
"android-background-location-policy": """
## Work profile and location

Android work profile may deny location to personal apps but grant work app — test dual-profile enrollment on Pixel with work policy disabling background location while personal fitness app still runs; document unsupported matrix in enterprise admin guide to set expectations for MDM customers.
""",
"agent-vector-index-rebuild": """
## Staging index query load test

Before alias swap, run k6 load test against staging index endpoint with production-shaped QPS for 30 minutes — HNSW graphs that recall well at low QPS may degrade under concurrent search during Black Friday agent traffic. Compare p99 latency staging vs production old index at equal load.
""",
"android-assist-structure-extraction": """
## Samsung Internet and third-party WebView

Login WebView in Samsung Internet custom tab may differ from Chrome WebView autofill — QA matrix includes Samsung device with Samsung Pass enabled. AssistStructure dump compared between engines when autofill bug reported only on Galaxy devices.
""",
"android-16-edge-to-edge-enforcement": """
## SDK 35 migration timeline

Pin targetSdk upgrade sprint with design QA sign-off on all activities — SDK bump without edge-to-edge layout pass ships broken UI faster because platform removes opt-out. Create Figma overlay showing system bar and cutout safe zones designers reference for new screens.
""",
"agent-vulnerability-triage-sla": """
## SLA exception for zero-day active exploit

When CISA adds CVE affecting your stack with known exploitation, Tier 0 clock starts at catalog publish time even if internal triage incomplete — pre-allocated war room channel and comms template activated before full CVSS analysis completes.
""",
"agent-tokenization-payment-vault": """
## Agent-initiated subscription upgrade

Upgrade tool creates Checkout Session or Subscription update with proration — never pass prorated amount from model arithmetic. Return hosted URL for any payment method change requiring user presence; server webhook updates entitlements after `checkout.session.completed`.
""",
"agent-summarization-map-reduce": """
## Reduce stage model temperature audit

Reduce pass at temperature >0.3 introduced contradictory executive summaries in legal corpus eval — lock reduce and verify passes to 0–0.1. Map pass may use slightly higher temperature for phrasing variety in bullets without merging contradictory legal obligations.
""",
"agent-watermark-late-data": """
## Flink side output monitoring

Alert when side output late event rate exceeds 5% of total events for 15 minutes — indicates mobile SDK bug or regional clock skew cluster. Dashboard slice by `app_version` dimension on event metadata to pinpoint release regression without widening global lateness for all tenants.
""",
"android-download-manager-resume": """
## DownloadManager and scoped storage path

On Android 10+, `setDestinationInExternalPublicDir` deprecated — use app-specific dir or MediaStore for user-visible downloads. Wrong destination path causes STATUS_FAILED after OS upgrade; migration guide moves pending downloads table paths on app upgrade hook.
""",
"agent-view-transitions-spa-mp": """
## View transition and focus management for agent chat

When transitioning from thread list to active chat, move focus to message input after `viewTransition.finished` — keyboard users on hybrid tablet/desktop agents expect focus in composer not back on list item. Respect `prefers-reduced-motion` by skipping transition and focusing immediately.
""",
"agent-waf-bot-management": """
## Bot allowlist for monitoring synthetics

Datadog/Synthetic tests from cloud IPs flagged as bots — maintain allowlist rule on `http.request.headers[\"x-datadog-synthetic\"]` or fixed egress IP list updated from vendor quarterly. False bot block on synthetics pages on-call while real users unaffected.
""",
"android-activity-recognition-api": """
## AR API unavailable on GMS-less devices

Gracefully disable auto-pause feature when `ActivityRecognition.getClient` connection fails on Huawei — show settings toggle disabled with explanation rather than crash loop registering transitions. Feature flag remote config disables AR on known incompatible device model list updated from Play device catalog analytics.
""",
}

def wc(text):
    import re
    body = re.sub(r'^---.*?---\n', '', text, count=1, flags=re.S)
    return len(re.findall(r'\w+', body))

for slug, extra in FINAL.items():
    path = Path(f"content/blog/{slug}.md")
    text = path.read_text()
    if wc(text) >= 1200:
        print(f"skip {slug} {wc(text)}")
        continue
    marker = "\n## Resources\n"
    path.write_text(text.replace(marker, extra + marker))
    print(f"ok {slug} -> {wc(path.read_text())}")
