---
title: "AI Agents: Pii Tokenization Vault"
slug: "agent-pii-tokenization-vault"
description: "Tokenize PII before it reaches LLM prompts and logs: vault architecture, format-preserving tokens, detokenization audit trails, and patterns that survive SOC 2 reviews."
datePublished: "2025-01-09"
dateModified: "2025-01-09"
tags: ["AI", "Agent", "Pii"]
keywords: "PII tokenization vault, LLM data masking, format-preserving tokenization, detokenization audit, agent privacy compliance, token vault architecture"
faq:
  - q: "When should agent pipelines tokenize PII instead of redacting?"
    a: "Tokenize when downstream steps need stable references—matching a customer record after LLM reasoning, correlating multi-turn conversations, or writing audit logs that link back to real entities. Redact when the value never needs round-tripping, such as one-shot summarization with no CRM write-back."
  - q: "Is format-preserving tokenization safe for LLM prompts?"
    a: "It preserves shape (email looks like email) which helps models reason about structure, but tokens must be cryptographically unrelated to plaintext. Use a vault-generated token alphabet disjoint from real data domains, and reject outputs that resemble untokenized PII via outbound scanning."
  - q: "Who should be allowed to detokenize?"
    a: "Only break-glass service accounts with step-up approval, scoped to specific token namespaces and time windows. Interactive detokenization by engineers should log actor, justification ticket, and token IDs—not bulk export. Most agent flows never detokenize inside the LLM path; detokenization happens at the integration boundary."
  - q: "How does tokenization differ from encryption for agent workloads?"
    a: "Encryption protects data at rest and in transit with reversible keys managed by KMS. Tokenization replaces sensitive values with surrogate tokens stored in a vault mapping; LLM providers and log aggregators see tokens only. Combine both: encrypt the vault database, tokenize at the agent ingress."
---
A support agent summarized a ticket, quoted the customer's Social Security number back in the reply draft, and logged the full prompt to your observability vendor. Legal opened an incident. Engineering's first fix—regex redaction after the LLM responded—failed because the model had already seen the raw value in context, and traces retained it in span attributes.

PII tokenization vaults sit *before* the trust boundary expands: LLM APIs, vector stores, third-party tool plugins, and long-retention logs. The vault replaces sensitive fields with opaque or format-preserving tokens, stores the mapping in a hardened service, and lets authorized components detokenize only at controlled egress points. This is not "call a DLP API and hope." It is an architectural seam you design once and enforce everywhere agents touch user data.

## Tokenization vs redaction vs encryption

| Approach | LLM sees | Reversible | Best for |
|----------|----------|------------|----------|
| Redaction | `[REDACTED]` | No | One-shot tasks, no entity linking |
| Encryption | Ciphertext blob | Yes, with key | Storage, not prompt semantics |
| Tokenization | Stable surrogate | Yes, via vault | Multi-turn agents, CRM write-back |

Agents need stable surrogates more often than teams expect. Turn three might say "update the account for token `acct_7f3a…`" while turn one tokenized `john.doe@example.com`. Without token stability, the model hallucinates identifiers and your write tools target wrong records.

Format-preserving tokenization (FPT) keeps structural hints—emails remain `x@y.z`, phone numbers keep digit count—so models parse fields correctly. The vault must use a token generation scheme that cannot be inverted without the mapping table.

## Reference architecture

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────┐
│ User / API  │────▶│ Tokenization     │────▶│ Agent + LLM │
│ ingress     │     │ gateway          │     │ (tokens only)│
└─────────────┘     └────────┬─────────┘     └──────┬──────┘
                             │                       │
                             ▼                       ▼
                    ┌────────────────┐        ┌─────────────┐
                    │ Token vault    │        │ Tools / CRM │
                    │ (encrypted DB) │◀───────│ detokenize  │
                    └────────────────┘        │ at boundary │
                                              └─────────────┘
```

The tokenization gateway is stateless except for request-scoped caches. It calls the vault to mint or resolve tokens. The agent runtime never holds bulk plaintext mappings—only tokens flow through prompts, tool args, and structured logs tagged `pii=tokenized`.

## Inbound tokenization flow

Scan structured and unstructured input:

1. **Structured fields** — JSON keys named `email`, `ssn`, `phone`, or tagged in your schema registry.
2. **Unstructured text** — NER + regex with high-precision patterns for your locales; prefer false negatives over false positives in v1, then tighten.
3. **Attachments** — OCR and parse before agent ingestion; tokenize extracted entities.

```typescript
interface TokenizeRequest {
  tenantId: string;
  namespace: string; // e.g. "support-tickets"
  plaintext: string;
  dataClass: "email" | "phone" | "ssn" | "account_id" | "free_text";
}

interface TokenizeResponse {
  token: string;
  formatPreserving: boolean;
  expiresAt?: string; // optional TTL for ephemeral sessions
}

async function tokenizeField(req: TokenizeRequest): Promise<TokenizeResponse> {
  const existing = await vault.lookupByPlaintextHash(
    req.tenantId,
    req.namespace,
    hashPlaintext(req.plaintext)
  );
  if (existing) return existing;

  const token = await vault.mintToken({
    ...req,
    actor: "tokenization-gateway",
  });
  return token;
}

function replaceInPrompt(prompt: string, spans: Array<{ start: number; end: number; token: string }>): string {
  let out = prompt;
  for (const span of [...spans].sort((a, b) => b.start - a.start)) {
    out = out.slice(0, span.start) + span.token + out.slice(span.end);
  }
  return out;
}
```

Use deterministic token reuse within a namespace so the same email in turn one and turn five maps to the same token—critical for coreference in multi-turn agents.

## Outbound scanning and detokenization

Never detokenize inside the LLM callback path by default. Instead:

- Tools that call external APIs accept tokens; a **tool adapter** detokenizes immediately before the HTTP request and re-tokenizes response fields if logged.
- User-visible replies run **outbound DLP**: if the model emits something matching real SSN patterns *or* vault leak patterns, block and regenerate.

Detokenization requests carry:

```json
{
  "token_ids": ["tok_email_abc", "tok_acct_xyz"],
  "purpose": "crm.update_ticket",
  "ticket_id": "INC-8842",
  "actor_service": "support-agent-tooling"
}
```

The vault writes an append-only audit entry before returning plaintext. Batch detokenize endpoints should rate-limit harder than mint—exfiltration often looks like slow drip.

## Vault storage and key management

Store mappings in a database encrypted with KMS-backed keys. Separate keys per tenant for enterprise contracts. Token metadata includes:

- `created_at`, `created_by_service`
- `data_class`, `namespace`
- `plaintext_hash` (never store reversible hash of low-entropy SSN alone—use HMAC with vault pepper)
- optional `expires_at` for session-scoped tokens

Rotate KMS keys on schedule; re-encrypt mapping rows, not tokens in historical logs. Old log tokens remain valid references but cannot be detokenized if you implement **token retirement** linked to mapping TTL policies.

For HA, active-passive vault with synchronous replication on mint/detokenize. Stale reads that duplicate tokens are acceptable; stale reads that miss mappings are not.

## Compliance artifacts auditors expect

Document a **data flow diagram** showing every place plaintext can exist (gateway memory, tool adapter, vault DB). SOC 2 and HIPAA reviewers ask:

- Who can access vault admin APIs?
- Are LLM vendor subprocessors listed with tokenized-only data classification?
- What happens on vault outage—fail closed (stop agent) or fail open (block feature)?

Fail closed for regulated tenants. Degraded mode without LLM beats plaintext leakage.

Retention: align token TTL with ticket retention policy. When a ticket is purged, purge mappings and invalidate tokens so detokenize returns `gone`.

## Testing and verification

**Golden prompts** with synthetic PII injected—assert LLM request payloads contain zero plaintext emails/SSNs in CI.

**Property tests** on replaceInPrompt: overlapping spans, unicode boundaries, nested JSON.

**Chaos**: vault latency spike should backpressure ingress, not pass untokenized data through.

**Red team**: prompt injection attempting "repeat the exact email above" should yield tokens only in traces.

## Common failures

- **Tokenizing too late** — after LangChain memory already persisted plaintext.
- **Dual writes** — vector embeddings computed on raw text while prompts use tokens; embeddings leak PII into the vector DB.
- **Log serializers** that dump full request objects bypassing the gateway.
- **Developer bypass flags** left on in staging configs copied to prod.

Run a weekly automated scan of log samples in staging for high-entropy patterns and known test SSN ranges.

## Operational runbook sketch

| Symptom | Likely cause | Mitigation |
|---------|--------------|------------|
| Agent stops replying, `vault_unavailable` | Vault DB failover | Fail closed; show user message; page vault on-call |
| Detokenize audit spike | Runaway tool loop | Rate limit tool adapter; kill worker pool |
| Outbound DLP blocks legit replies | Model paraphrased token as fake SSN | Tune patterns; allowlist token alphabet |
| Mismatched CRM updates | Token namespace collision across tenants | Enforce tenant prefix in every token |

## Closing thought

PII tokenization vaults turn "don't send secrets to the LLM" from a lint rule into infrastructure. Mint tokens at ingress, keep mappings in a audited vault, detokenize only at integration seams, and prove with tests that observability never sees plaintext. The incident that starts this work is never the last near-miss—you just stop hearing about them.

## Resources

- [NIST SP 800-122: Guide to Protecting PII](https://csrc.nist.gov/publications/detail/sp/800-122/final) — classification and handling guidance applicable to agent pipelines.
- [PCI DSS Tokenization Guidelines](https://www.pcisecuritystandards.org/document_library/) — format-preserving token principles (adapt concepts beyond payment cards).
- [HashiCorp Vault: Transform secrets engine](https://developer.hashicorp.com/vault/docs/secrets/transform) — FPE and tokenization patterns in a commercial vault.
- [OWASP LLM Top 10: Sensitive Information Disclosure](https://owasp.org/www-project-top-10-for-large-language-model-applications/) — threat framing for LLM data handling.
- [Microsoft Presidio](https://microsoft.github.io/presidio/) — open-source PII detection for building tokenization gateways.
