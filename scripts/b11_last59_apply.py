#!/usr/bin/env python3
"""Finish batch 11 last 59: strip boilerplate, expand under-1200, set dateModified."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content/blog"
SLUG_FILE = Path("/tmp/b11_last59.txt")
DATE = "2026-07-17"
TARGET = 1200
WORD = re.compile(r"\b[\w'-]+\b")

STRIP = [
    r"## Common production mistakes\n.*?(?=\n## |\Z)",
    r"## Debugging and triage workflow\n.*?(?=\n## |\Z)",
    r"## Operational checklist for teams\n.*?(?=\n## |\Z)",
    r"## Architecture and boundaries\n.*?(?=\n## |\Z)",
    r"## Accessibility requirements\n.*?(?=\n## |\Z)",
    r"## Security and privacy considerations\n.*?(?=\n## |\Z)",
    r"## Testing strategy\n.*?(?=\n## |\Z)",
    r"## Hard-won lessons shipping[^\n]*\n.*?(?=\n## |\Z)",
    r"## Failure modes when implementing[^\n]*\n.*?(?=\n## |\Z)",
    r"Treat production rollout as a measured change:.*?\n\n",
    r"The gap between reading about .*? — not a conference demo\.\n\n",
    r"I have applied these patterns across product sites where Core Web Vitals.*?\n\n",
    r"Validate in staging with production-like data volumes\..*?\n\n",
    r"Performance work without field metrics is cosplay.*?(?=\n## |\Z)",
    r"Document the timeline during triage\..*?\n\n",
    r"Document trade-offs in the PR description\..*?\n\n",
]

sys.path.insert(0, str(ROOT / "scripts"))
from batch11_expand import EXPANSIONS  # noqa: E402

# Additional unique sections (~150–450 words each) — no shared template headings
ADDONS: dict[str, str] = {
    "system-design-metrics-monitoring": """## SLO burn alerts that wake the right person

Error budget burn rate alerts should page only when user-visible SLO is at risk — not when a non-critical batch job metric spikes. Multi-window burn (e.g., 1h and 6h) reduces false positives from brief blips. Tie alert names to customer journeys: `checkout_success_rate_burn` not `prometheus_scrape_failures`. On-call runbooks link from alert annotations to dashboards filtered to the failing service and region.""",

    "system-design-news-feed": """## Cold start for new users

New accounts have empty follow graphs — pure pull ranking returns nothing interesting. Blend popular content, onboarding topic picks, and geographic trending until the follow graph reaches critical mass (~20 follows). Track engagement lift from the blend versus pure chronological; remove blend weights gradually as graph density increases. Celebrity first-post fan-out should not block new-user feed generation — separate queues with independent SLOs.""",

    "system-design-notification-system": """## Quiet hours and frequency caps

Respect user quiet hours per timezone — batch non-urgent pushes until morning unless the user opted into real-time alerts. Frequency caps prevent notification fatigue: max three marketing pushes per week, unlimited for security and transaction channels. Unsubscribe on email must not disable OTP SMS; channel preferences are independent dimensions in the user profile store.""",

    "system-design-payment-system": """## PCI scope and tokenization boundaries

Card data never touches application servers — hosted fields or tokenization SDK returns a single-use token to your backend. PCI scope shrinks to SAQ A when checkout iframe is served from the processor domain. Log payment intent IDs, never PAN fragments. Quarterly ASV scans and key rotation for API credentials remain mandatory even with outsourced card entry.

## Reconciliation and ledger invariants

Daily reconciliation jobs compare processor settlement files against internal ledger entries — mismatches trigger finance alerts before month-end close. Double-entry ledger with immutable append-only transaction log makes audit tractable. Never update balance columns in place without corresponding ledger row; investigators need history.""",

    "system-design-ride-sharing": """## Surge pricing feedback loops

Surge multipliers must update within seconds of demand/supply imbalance but display stable prices during the thirty-second confirmation window — users hate price changes mid-request. Geofence surge independently per airport, stadium, and downtown cell clusters. Cap maximum surge multiplier in product policy; uncapped surge during outages creates PR crises even when economically rational.""",

    "system-design-ticketing-booking": """## Payment timeout versus inventory hold

Hold TTL must exceed p99 payment completion time plus retry buffer — if Stripe checkout takes ninety seconds on mobile, a sixty-second hold guarantees double-booking complaints. Extend hold on payment-in-progress webhook, release on explicit cancel or timeout. Show countdown timer in UI synced to server hold expiry, not client clock.""",

    "system-design-url-shortener": """## Custom domains and TLS at edge

Enterprise customers bring `links.customer.com` CNAME to your edge. Automate ACME certificate issuance per custom domain; failed cert provisioning blocks domain activation, not silent HTTP fallback. Resolve slug lookup after Host header — same slug can map differently per custom domain namespace. Analytics segment by domain for billing and abuse isolation.""",

    "system-design-video-streaming": """## CDN cache key design for segments

HLS segment URLs must be cache-friendly: include bitrate rung and sequence number, avoid session IDs in path. Origin shield in front of packager reduces thundering herd when popular live event starts. Monitor origin egress — viral VOD can exceed origin capacity if CDN cache hit ratio drops below 95%.""",

    "terraform-drift-detection": """## Attribution and change correlation

Tag every manual console change with incident ticket ID in resource tags when possible. Drift plans without attribution waste triage time. Integrate CloudTrail or audit logs with drift alerts — show who changed the security group rule before asking Terraform to revert it.""",

    "terraform-modules-composition": """## Composition over deep nesting

Modules nested more than three levels become opaque — consumers cannot predict plan diffs. Flatten to two levels: environment wrapper calling service modules. Pass structured objects for related settings (`database = { instance_class, storage_gb }`) instead of twelve scalar variables with implicit coupling.""",

    "terraform-state-management-backends": """## State migration without downtime

Moving state between backends uses `terraform init -migrate-state` with verified backup first. For split-monolith refactors, use `terraform state mv` in CI with plan gate — moving resources between states without code change produces no-op plans only if addresses match. Never delete old state until new state successfully applies in production.""",

    "terraform-testing-policy-as-code": """## Plan-based testing in CI

Run `terraform plan -json` on every PR and feed to OPA/Conftest. Assert: no `delete` on production databases, all S3 buckets have encryption, security groups deny 0.0.0.0/0 on port 22. Store plan artifacts for thirty days — post-incident review compares plan to what actually applied.""",

    "terraform-workspaces-environments": """## When workspaces are enough

Workspaces fit personal dev sandboxes and ephemeral preview environments in one account with identical IAM boundaries. Name workspaces explicitly — `dev-alice` not `default`. Never use workspace name as sole prod guard; combine with `terraform.workspace` conditionals that refuse apply when backend key matches prod pattern from unapproved CI role.

Separate AWS accounts per environment remain best practice for regulated workloads. Workspaces share IAM credentials of the runner — a compromised dev laptop with prod workspace access is game over. Structure CI so prod workspace apply requires OIDC role assumption from main branch only, with manual approval gate and plan artifact hash verification.""",

    "testing-compose-uis-v2": """## Screenshot and semantics together

Semantics tests catch broken behavior; screenshot tests catch visual regressions Compose semantics miss — gradient backgrounds, padding shifts. Keep screenshot scope to design-system components, not full screens with dynamic timestamps.""",

    "testing-mutation-testing": """## Equivalent mutants and timeout mutants

Some mutants are semantically equivalent — changing `i++` to `++i` in a loop with no side effects. Stryker marks these timed-out or equivalent; do not chase 100% score. Focus on conditional boundary mutants in pricing and tax logic — those survive when tests only check happy path outputs.""",

    "testing-playwright-e2e": """## Network conditioning in CI

Run one smoke spec per PR on default network and nightly suite with `slow3G` emulation for checkout flow. Service workers and HTTP/3 behave differently under throttle — catches timeouts unit tests miss. Record trace on first retry only to balance artifact storage.""",

    "testing-property-based-testing": """## Shrinking readable counterexamples

Hypothesis shrinking produces minimal failing inputs — teach devs to read shrunk output, not re-run with fixed seed only. Store `@example` decorators for every shrunk case in regression suite so CI catches reintroduction without full property search.""",

    "testing-snapshot-testing-tradeoffs": """## Snapshot review discipline

Require PR reviewer to expand snapshot diff hunk and confirm intentional UI change. CI fails if snapshot file changes without `SNAPSHOT_UPDATE` label on PR. Prefer inline snapshots for small JSON — easier review than separate `.snap` files lost in noise.""",

    "testing-test-data-builders": """## Immutable builders in parallel tests

Builders that mutate shared default instances cause order-dependent failures under parallel test runners. Each `build()` returns fresh object graph — clone defaults in builder constructor. Document required fields that have no sensible default so compile-time or runtime errors surface early.""",

    "testing-test-doubles-mocks-stubs": """## Contract tests against provider mocks

When mocking Stripe or SendGrid, verify mock response shapes against recorded fixtures from sandbox API monthly — provider API drift silently breaks tests that still pass with outdated mock JSON. Prefer HTTP-level mocks (MSW) over mocking SDK internals.""",

    "testing-unit-vs-integration-balance": """## Test pyramid budget

Target 70% unit, 20% integration, 10% E2E by execution time, not file count. When integration suite exceeds fifteen minutes, split by domain team ownership — checkout team owns checkout Testcontainers suite. Failed integration test blocks deploy of that domain's services only with monorepo path filters.""",

    "testing-vitest-react-testing-library": """## Component test isolation from router

Wrap components under test with MemoryRouter supplying initial entry — testing without router when component calls `useNavigate` throws obscure errors. Export test-utils wrapper from one module; do not copy-paste Provider stacks into every spec.""",

    "timeseries-downsampling-retention": """## Legal hold on metrics data

Compliance may require retaining raw billing metrics seven years while operational metrics roll off in thirty days. Tag series with retention class at ingestion — mixing classes in one bucket complicates lifecycle policies. Downsampling jobs must never aggregate across retention class boundaries.""",

    "timeseries-influxdb-vs-timescale": """## Hybrid query patterns

Dashboards joining hourly CPU averages with Postgres customer tier need federated query or ETL export. Timescale continuous aggregates materialize hourly rollups SQL-native; Influx requires export to Parquet then Athena. Pick based on where analysts already write SQL.""",

    "timeseries-prometheus-remote-write": """## WAL replay after crash

Prometheus WAL replay on restart can take minutes with high cardinality — size remote-write queue for worst-case restart window. Runbook: if replay exceeds SLA, temporarily scale scrape interval on non-critical jobs to reduce WAL backlog.""",

    "typescript-generics-constraints": """## infer keyword in conditional types

Use `infer R` inside conditional types to extract return types from function generics — powers typed `fetchJson<T>` wrappers. Constraints with `extends keyof` prevent passing unrelated union members. When constraints grow complex, split into helper type aliases for readability in error messages.""",

    "typescript-satisfies-operator": """## satisfies with discriminated unions

Theme config objects use `satisfies Record<string, ThemeToken>` while preserving literal keys for autocomplete. Combined with `as const` on nested values, designers get typed token names without losing string literal inference for CSS variable generation.""",

    "typescript-strict-mode-migration": """## noImplicitReturns in async functions

Async functions implicitly return `Promise<void>` — missing return in branch still violates noImplicitReturns when other branches return value. Explicit `return undefined` or restructure guards. Enable in CI per-directory once src/legacy is excluded via tsconfig references.""",

    "typescript-utility-types-app-patterns": """## Omit vs Pick for API versioning

Public API v2 responses use `Pick<User, 'id' | 'displayName' | 'avatarUrl'>` — explicit allowlist safer than `Omit<User, 'internalNotes'>` when new sensitive fields added to User later. Document which utility type pattern each API layer uses in style guide.""",

    "web-performance-http3-quic-benefits": """## QUIC head-of-line blocking in practice

HTTP/3 multiplexes streams without TCP head-of-line blocking — benefits appear on lossy Wi-Fi where TCP retransmits block all streams. On clean datacenter links, H3 may perform similarly to H2. Measure with WebPageTest compare H2 vs H3 from residential locations, not just office fiber.

Zero-RTT resumption risks replay attacks — disable for mutating requests at CDN config even if spec allows idempotent GET replay. Monitor QUIC version negotiation failures; corporate proxies that intercept UDP may force fallback to TCP.""",

    "websocket-heartbeat-ping-pong": """## Proxy idle timeouts versus heartbeat interval

AWS ALB idle timeout defaults sixty seconds — heartbeat interval must be under half that (e.g., twenty-five seconds) with jitter to prevent synchronized pings. Document proxy chain end-to-end: CDN → load balancer → app server each may have different idle limits.

Ping payload size matters on metered connections — empty ping frames, not JSON blobs. Server-side: track last pong timestamp per connection; close stale connections before file descriptor exhaustion during reconnect storms.""",

    "websocket-reconnection-backoff": """## Session resumption after reconnect

After backoff reconnect succeeds, client must replay missed messages — use server-side sequence numbers or CRDT sync protocol. Blind reconnect without cursor resumption duplicates chat messages users already saw.

Cap maximum backoff (e.g., thirty seconds) so users are not left permanently disconnected. Reset backoff counter after stable connection lasting five minutes. Combine with visibility API — pause reconnect attempts when tab backgrounded to save battery on mobile.""",

    "terraform-modules-composition": """## Testing modules in isolation

Use `terraform test` or Terratest to apply modules against LocalStack or ephemeral cloud accounts. Assert outputs match expected shapes after apply. Module CI should run plan-only against consumer fixture configurations — breaking output renames fail before downstream environments pick up new version.""",

    "terraform-state-management-backends": """## Encryption and access logging

S3 state buckets require SSE-KMS or SSE-S3, versioning enabled, and public access blocked at account level. CloudTrail data events on state bucket object reads catch unauthorized access. Restrict `s3:GetObject` on state to CI role and break-glass admin role only — developer laptops do not need direct state download.""",

    "terraform-testing-policy-as-code": """## Exception workflow

Policies need documented exception path — temporary waiver tag with expiry date and approver email. Permanent exceptions become policy updates, not shadow tags. Review waiver inventory monthly; expired waivers fail CI until resource complies or waiver renewed with justification.""",

    "typescript-generics-constraints": """## Generic defaults and inference pitfalls

Default type parameters (`T = string`) simplify call sites but hide inference failures until downstream usage. Explicit constraints on callback generics (`<T extends HTMLElement>`) catch passing wrong DOM ref type at compile time. When inference fails with inscrutable errors, introduce named intermediate type alias — error messages improve dramatically.""",

    "web-workers-offloading-compute": """## Transferable buffers and copy cost

`postMessage` structured clone copies large ArrayBuffers — use transferable list to move ownership without copy: `worker.postMessage({ buf }, [buf.buffer])`. Main thread loses access after transfer; clone handle semantics if both sides need read-only view. Measure serialization overhead; sometimes WASM in worker beats JSON stringify of huge objects.""",

    "webauthn-passkeys-server": """## Credential backup and PRF extension

Synced passkeys (Apple/Google) behave differently from device-bound security keys — recovery flows must account for platform account loss. WebAuthn PRF extension derives application-specific keys from passkey — useful for encrypting user data without separate key escrow. Feature-detect extension support; fallback for authenticators that reject PRF inputs.""",

    "websocket-heartbeat-ping-pong": """## Browser tab throttling interaction

Background tabs throttle timers — heartbeat driven by `setInterval` may fire late, causing false stale detection. Prefer server-initiated ping or `WebSocket` protocol-level ping if library supports it. On visibility change to visible, send immediate ping to verify connection before user submits form.""",

    "xss-prevention-csp-trusted-types": """## Trusted Types policy naming

Register policies with descriptive names (`default`, `dompurify-html`) — DevOps dashboards correlate CSP violation reports to policy. `trustedTypes.createPolicy` runs at app bootstrap before third-party scripts load. Violation report-uri should include `sample` field review process — noisy reports from browser extensions filtered by user-agent patterns.""",
}


def wc(text: str) -> int:
    return len(WORD.findall(text))


def parse(raw: str) -> tuple[str, str]:
    parts = raw.split("---", 2)
    return parts[1], parts[2].lstrip("\n")


def strip_body(body: str) -> str:
    for pat in STRIP:
        body = re.sub(pat, "", body, flags=re.S)
    return re.sub(r"\n{3,}", "\n\n", body).strip()


def update_fm(fm: str) -> str:
    if re.search(r"^dateModified:", fm, re.M):
        return re.sub(r'^dateModified:.*$', f'dateModified: "{DATE}"', fm, flags=re.M)
    return fm.rstrip() + f'\ndateModified: "{DATE}"'


def insert_before_resources(body: str, section: str) -> str:
    if section.split("\n")[0] in body:
        return body
    if "## Resources" in body:
        return body.replace("## Resources", section + "\n\n## Resources", 1)
    return body + "\n\n" + section


def write_post(slug: str, fm: str, body: str) -> int:
    path = BLOG / f"{slug}.md"
    path.write_text(f"---\n{fm.strip()}\n---\n\n{body.strip()}\n", encoding="utf-8")
    return wc(body)


def main() -> None:
    slugs = [s.strip() for s in SLUG_FILE.read_text().splitlines() if s.strip()]
    results = []
    for slug in slugs:
        path = BLOG / f"{slug}.md"
        raw = path.read_text(encoding="utf-8")
        fm, body = parse(raw)
        body = strip_body(body)
        for src in (EXPANSIONS, ADDONS):
            if slug in src:
                body = insert_before_resources(body, src[slug])
        fm = update_fm(fm)
        count = write_post(slug, fm, body)
        results.append({"slug": slug, "words": count, "ok": count >= TARGET})

    ok = sum(1 for r in results if r["ok"])
    failed = [r for r in results if not r["ok"]]
    samples = sorted(results, key=lambda x: -x["words"])[:5]
    print(f"Completed: {ok}/{len(slugs)}")
    if failed:
        print(f"Under {TARGET}: {len(failed)}")
        for r in failed:
            print(f"  {r['slug']}: {r['words']}")
    print("Sample word counts:")
    for r in samples:
        print(f"  {r['slug']}: {r['words']}")

if __name__ == "__main__":
    main()
