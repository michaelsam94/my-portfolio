---
title: "Sanctions Screening Api"
slug: "llm-sanctions-screening-api"
description: "Screening APIs sit on the critical path between agent-initiated transfers and regulatory compliance. Integration patterns, fuzzy name matching, false-positive queues, and audit trails that survive examiner review for teams running LLM features in production."
datePublished: "2025-08-14"
dateModified: "2026-07-17"
tags:
  - "AI"
  - "LLM"
keywords: "sanctions screening API, OFAC compliance, watchlist matching, fuzzy name matching, AML integration, payment compliance gate"
faq:
  - q: "Should sanctions screening block synchronously on the payment API or run asynchronously?"
    a: "Block synchronously on outbound payments, wire transfers, and any agent-initiated action that moves funds or goods to a new counterparty. Regulators expect a hold before release when a potential match exists. Async batch screening suits periodic rescreening of existing customers against updated lists — run nightly, not at click time. Never let an agent complete a transfer and screen afterward."
  - q: "How do I reduce false positives without missing true matches?"
    a: "Tune matching thresholds per entity type: individuals need higher fuzzy tolerance than corporate names. Normalize inputs — transliterate Cyrillic, strip honorifics, expand aliases — before calling the vendor API. Maintain an internal allowlist for cleared false positives with expiry dates and approver IDs. Re-screen allowlisted entities when lists update. Log every override with business justification."
  - q: "What audit evidence do examiners expect from a screening integration?"
    a: "Immutable logs showing: who was screened, which list version, raw request payload (redacted PII in copies), match score, disposition (cleared, escalated, blocked), timestamp, and system or human actor. Retain seven years minimum for US MSB/BSA contexts — confirm with your compliance officer. Agent-initiated screens must attribute to the triggering user and agent session, not just the service account."
  - q: "Can an LLM agent call a sanctions API directly via tool use?"
    a: "The agent should propose beneficiary details; a deterministic compliance service must call the screening API and gate the transaction. LLMs hallucinate names, miss transliteration rules, and cannot be the system of record for regulatory decisions. Wrap screening in a tool that returns structured pass/fail/pending — never free-text 'looks fine' responses on the payment critical path."
---
An agent workflow drafted a cross-border payout to "Mohammad Al-Rahman Trading LLC." The payment service called the screening vendor, got a 87% fuzzy match against a sanctioned entity named "Mohammed Rahman," and auto-released because the integration treated anything below 90% as clear. Compliance found the gap during a quarterly sample — not during the transaction.

Sanctions screening APIs are the membrane between software that moves fast and regulation that does not forgive ambiguity. OFAC, EU consolidated lists, UN sanctions, PEP databases — vendors wrap them in REST endpoints that return match scores, entity metadata, and list provenance. Your job is not to pick the vendor slogan; it is to integrate screening so that every agent-initiated transfer, onboarding, and counterparty change hits a deterministic gate with evidence you can reproduce under audit.

## Regulatory context in one paragraph

US persons and companies must block transactions involving sanctioned parties and report matches to OFAC. Similar regimes exist in the EU, UK, and dozens of jurisdictions. Screening is not optional for fintech, marketplaces paying sellers, payroll platforms, or any product where an agent can initiate movement of value. Penalties for willful violations reach millions; negligent integration gaps are treated as program failures, not one-off bugs.

Agents raise the stakes because they compose actions from natural language. "Pay the invoice from the PDF" becomes a beneficiary name, amount, and routing number extracted by a model — then executed by tools. Screening must sit **between** tool authorization and execution, not inside the model's reasoning loop.

## Architecture: where screening sits in the flow

```
User intent → Agent planner → Compliance gate → Payment rail
                                  │
                                  ├─ Sanctions API (sync)
                                  ├─ PEP / adverse media (optional)
                                  └─ Case management (on match)
```

The compliance gate is a dedicated service — not a middleware one-liner. It owns normalization, vendor calls, threshold logic, case creation, and audit emission. Payment rails receive a signed `ComplianceClearance` token with expiry, list version, and correlation ID.

```typescript
interface ScreeningRequest {
  correlationId: string;
  entityType: "individual" | "organization" | "vessel" | "aircraft";
  name: string;
  aliases?: string[];
  address?: Address;
  dateOfBirth?: string; // ISO 8601 for individuals
  nationalId?: string;  // hashed at rest; sent per vendor contract
  countryCode: string;
  triggeredBy: {
    userId: string;
    agentSessionId: string;
    workflowId: string;
  };
}

interface ScreeningResult {
  disposition: "clear" | "potential_match" | "confirmed_match" | "error";
  matchScore?: number;
  matchedEntities?: MatchedEntity[];
  listVersion: string;
  vendorRequestId: string;
  screenedAt: string;
}
```

Never pass vendor responses directly to the LLM for "interpretation." The agent sees `{ disposition: "pending_review", caseId: "CASE-8842" }` — not raw watchlist JSON with similar names the model might paraphrase incorrectly.

## Calling vendor APIs: patterns that hold up

Major vendors (ComplyAdvantage, Dow Jones Risk & Compliance, Refinitiv World-Check, OFAC-API.com, etc.) expose similar REST shapes: POST `/screenings` with entity attributes, GET `/screenings/{id}` for async enrichment, webhooks on list updates.

```python
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential_jitter

class SanctionsClient:
    def __init__(self, base_url: str, api_key: str):
        self.client = httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=httpx.Timeout(10.0, connect=3.0),
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential_jitter(initial=0.5, max=8))
    def screen(self, payload: dict) -> dict:
        response = self.client.post("/v2/screenings", json=payload)
        if response.status_code == 429:
            response.raise_for_status()  # retry after backoff
        response.raise_for_status()
        return response.json()


def compliance_gate(req: ScreeningRequest, client: SanctionsClient) -> ScreeningResult:
    normalized = normalize_entity(req)  # transliteration, alias expansion
    raw = client.screen(normalized.to_vendor_payload())
    result = map_vendor_response(raw)
    emit_audit_event(req, result)
    if result.disposition == "potential_match":
        case_id = case_management.open_case(req, result)
        result.case_id = case_id
    return result
```

**Timeouts**: Screening on the payment critical path needs a hard ceiling — typically 3–10 seconds. On timeout, disposition is `error`, payment is held, and ops is alerted. Fail open is not an option for outbound transfers.

**Retries**: Retry idempotent vendor reads and transient 5xx/429 responses with jitter. Do not retry a screening that returned `potential_match` — you will duplicate cases.

**List version pinning**: Store `listVersion` on every clearance. When OFAC publishes a Friday afternoon update, batch rescreening jobs query customers screened against older versions.

## Name matching: why scores lie

Fuzzy matching compares normalized strings using algorithms — Levenshtein distance, phonetic encoding (Soundex, Double Metaphone), n-gram overlap. Arabic patronymics, Korean family-name-first order, LLC suffixes, and transliteration variants ("Muhammad" / "Mohamed" / "Mohammed") produce score inflation and deflation in equal measure.

Normalization pipeline before the API call:

```typescript
function normalizeForScreening(name: string, locale?: string): string {
  let n = name.trim().normalize("NFKC");
  n = stripHonorifics(n); // Mr, Dr, Sheikh — vendor-specific lists vary
  n = collapseWhitespace(n);
  n = transliterate(n, locale); // ICU transliteration rules
  n = removeCorporateSuffixes(n); // LLC, Ltd, GmbH — optional per entity type
  return n.toUpperCase();
}
```

Threshold policy belongs in configuration, not code constants:

```yaml
# screening-thresholds.yaml — reviewed by compliance quarterly
thresholds:
  individual:
    auto_clear_below: 75
    manual_review_above: 75
    auto_block_above: 95
  organization:
    auto_clear_below: 80
    manual_review_above: 80
    auto_block_above: 92
  payment_rail: ach_outbound
```

Individual and organization thresholds differ because corporate names collide more innocently ("Global Trading Ltd" is not rare). Document why each number was chosen — examiners ask.

## False positives and the human queue

Most matches are false positives. Operations teams drowning in alerts start clicking clear without review — that is a compliance failure mode.

Build a case queue with:

- Match score, list source, matched alias, side-by-side comparison UI
- Customer history: prior cleared false positives for same entity
- SLA timers: potential matches block payout until disposition within N hours
- Four-eyes rule: one analyst clears, senior approves overrides above a dollar threshold

```sql
CREATE TABLE screening_cases (
  id              UUID PRIMARY KEY,
  correlation_id  UUID NOT NULL,
  disposition     TEXT NOT NULL CHECK (disposition IN ('open', 'cleared', 'escalated', 'blocked')),
  match_score     NUMERIC(5,2),
  list_version    TEXT NOT NULL,
  assigned_to     TEXT,
  cleared_by      TEXT,
  cleared_at      TIMESTAMPTZ,
  justification   TEXT, -- required on manual clear
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_cases_open ON screening_cases (disposition) WHERE disposition = 'open';
```

Allowlist cleared false positives with expiry — re-screen on list update or after 90 days, whichever comes first. Permanent allowlists without rescreening fail audits.

## Agent-specific integration rules

When agents initiate payments or onboard counterparties:

1. **Extract structured entities** from documents using deterministic parsers where possible; use LLM extraction only with schema validation (Zod/JSON Schema) and human confirmation above limits.
2. **Screen before showing success** to the user. UI copy: "Payment pending compliance review" beats "Payment sent" followed by clawback.
3. **Attribute every screen** to `userId`, `agentSessionId`, and `workflowId`. Auditors trace agent autonomy back to human accountability.
4. **Disable tool execution on pending disposition.** The payment tool checks clearance token validity:

```typescript
async function executePaymentTool(ctx: ToolContext, input: PaymentInput): Promise<void> {
  const clearance = await compliance.getClearance(input.beneficiaryId);
  if (!clearance || clearance.disposition !== "clear") {
    throw new ToolBlockedError("beneficiary_not_cleared", {
      disposition: clearance?.disposition ?? "missing",
      caseId: clearance?.caseId,
    });
  }
  if (clearance.expiresAt < new Date()) {
    throw new ToolBlockedError("clearance_expired");
  }
  await paymentRail.submit(input, { complianceRef: clearance.id });
}
```

5. **Never let the model override a block.** Tool policies ignore prompt injection claiming "compliance already approved."

## Observability and rescreening at scale

Metrics that matter:

- `screening_latency_seconds` p50/p95 by entity type
- `screening_disposition_total{disposition}` — ratio of potential_match to clear
- `screening_vendor_errors_total` — 429, 5xx, timeout
- `cases_queue_depth` and `case_age_hours` — backlog SLAs
- `payments_blocked_total{reason}` — blocked vs pending vs cleared-after-review

Alert when error rate exceeds 1% for 5 minutes or case queue age exceeds SLA. Dashboard list version lag: "98% of active customers screened against list version ≥ X."

Batch rescreening after list updates:

```python
def enqueue_rescreen(stale_before: datetime, list_version: str) -> None:
    customers = db.query(
        "SELECT id FROM beneficiaries WHERE last_screened_at < %s OR list_version != %s",
        (stale_before, list_version),
    )
    for batch in chunked(customers, 500):
        queue.publish("rescreen.batch", {"beneficiary_ids": [c.id for c in batch]})
```

Rate-limit batch jobs against vendor quotas. Spread rescreens over hours, prioritize high-risk and high-volume beneficiaries first.

## Testing without triggering regulatory incidents

Vendor sandboxes return canned matches for test entities — use them. Maintain fixture names that trigger `potential_match` and `confirmed_match` in CI.

Contract tests assert your mapper handles vendor schema changes. Golden-file tests for normalization: "Sheikh Mohammad bin Rashid Al Maktoum" → expected normalized form.

Game-day exercises: vendor outage → payments hold, cases queue, no silent fail-open. List update simulation → rescreen job completes, one seeded beneficiary re-flags.

## What examiners will ask for

Prepare exports before they ask:

- Sample of 25 cleared potential matches with analyst justification
- Evidence of list update rescreening within your documented SLA
- Agent-initiated transaction trail from user prompt to clearance token to payment rail reference
- Override log: who cleared, when, score, list version, dollar amount

Sanctions screening APIs are commodity infrastructure. The integration — normalization, thresholds, case workflow, audit, agent gating — is where programs succeed or fail. Build the compliance service first; let agents compose on top of a rail that already knows how to say no.

## Resources

- [OFAC — Sanctions List Search and downloads](https://ofac.treasury.gov/sanctions-list-service) — Official SDN and consolidated list sources
- [FinCEN — BSA requirements for money services businesses](https://www.fincen.gov/resources/statutes-regulations/guidance) — US AML program expectations
- [EU — Consolidated Financial Sanctions list](https://data.europa.eu/data/datasets/consolidated-list-of-persons-groups-and-entities-subject-to-eu-financial-sanctions) — EU screening data source
- [Wolfsberg Group — Payment Transparency Standards](https://wolfsberg-principles.com/) — Industry due diligence guidance for payment screening
- [ISO 20022 — Payment initiation message standards](https://www.iso20022.org/iso-20022-message-definitions) — Structured beneficiary fields that improve match accuracy
