---
title: "AI Agents: Fx Rate Caching"
slug: "agent-fx-rate-caching"
description: "Caching foreign exchange rates for agent billing, expense tools, and multi-currency reasoning — TTL strategies, ECB/OANDA providers, stale-while-revalidate, and audit requirements for financial agents."
datePublished: "2025-09-06"
dateModified: "2025-09-06"
tags: ["AI", "Agent"]
keywords: "FX rate caching, foreign exchange, agent billing, currency conversion, stale-while-revalidate, Redis cache, multi-currency, financial agents"
faq:
  - q: "How stale can cached FX rates be for agent billing tools?"
    a: "Payment capture and invoicing typically require rates no older than the provider's official daily fix or the transaction timestamp window your finance team defines — often 24 hours for reporting, minutes for trading-adjacent flows. Document the staleness bound in API responses and never silently use expired rates for money movement without explicit user or policy consent."
  - q: "Should agents call FX APIs directly or use a centralized rate service?"
    a: "Centralize. A dedicated rate service with one cache layer avoids every tool and sub-agent hammering OANDA or ECB endpoints, enforces consistent rounding rules, and gives finance a single audit trail. Agents consume your internal /rates API, not third-party URLs."
  - q: "What cache key structure works for multi-tenant FX lookups?"
    a: "Key on (base_currency, quote_currency, rate_source, rate_date_or_bucket). Include provider and as-of timestamp in the value payload, not just the numeric rate. Tenants sharing a global cache is fine for market rates; tenant-specific spreads belong in a separate layer applied after cache hit."
  - q: "How do you handle weekends and market holidays when caches go stale?"
    a: "Major reference rates (ECB daily fix) do not update on weekends. Cache TTL should extend through known non-trading periods, and responses should flag rate_type=last_official_close with the fixing date. Agents reasoning about 'today's rate' on Saturday must cite Friday's close explicitly."
---
Agents that reason about money — expense categorization, cross-border invoicing, travel reimbursement, procurement comparisons — inevitably call `convert 450 EUR to USD` somewhere in the tool chain. Without caching, every turn hits an external FX API. With naive caching, finance discovers weeks later that refunds used Friday's rate on Monday's settlements. **FX rate caching** for agent systems is a contract between market data reality, user expectations, and audit requirements — not a Redis tutorial with a five-minute TTL copied from a blog post.

Financial agents amplify ordinary caching mistakes. A human opening a currency app once a day tolerates slight staleness. An agent loop invoking a `get_exchange_rate` tool forty times in a multi-step reconciliation burns API quota, adds latency to every turn, and may read subtly different rates if the cache is keyed wrong. Worse: two tools in the same agent run hit different cache entries and produce inconsistent totals the model presents as fact.

## Reference rates versus tradable rates

Not all FX numbers are interchangeable. Agent tools must declare which rate type they serve:

| Rate type | Source examples | Typical use in agents |
|-----------|-----------------|----------------------|
| Mid-market reference | ECB daily, Open Exchange Rates | Expense reports, estimates |
| Bid/ask tradable | Bank treasury, Stripe FX | Payment capture, refunds |
| Historical fix | WM/Reuters 4pm fix | Accounting period close |

Mixing mid-market in a quote and bid/ask in settlement creates reconciliation gaps finance will attribute to "the AI." Cache keys must include `rate_type` and `provider`. Responses must surface both numeric rate and metadata the model can cite to users.

```json
{
  "base": "EUR",
  "quote": "USD",
  "rate": "1.08734",
  "rate_type": "mid",
  "provider": "ecb",
  "as_of": "2025-09-05T14:15:00Z",
  "fixing_date": "2025-09-05",
  "cache_hit": true,
  "max_staleness_seconds": 86400
}
```

Agents prompting users should prefer natural language grounded in `fixing_date`: "Using ECB mid-market rate as of 5 Sep 2025 (1 EUR = 1.0873 USD)."

## Cache architecture for agent platforms

Centralize behind an internal **Rate Service** rather than embedding provider clients in each tool:

```
  Agent tools / LLM function calls
           │
           ▼
    ┌──────────────┐     miss     ┌─────────────┐
    │  Rate API    │ ───────────► │ Redis cache │
    │  (your svc)  │ ◄─────────── │  (cluster)  │
    └──────┬───────┘     hit      └─────────────┘
           │ miss + lock
           ▼
    ┌──────────────┐
    │ ECB / OANDA  │
    │  provider    │
    └──────────────┘
```

The Rate API applies rounding policy (banker's rounding, decimal places per currency pair), tenant spreads if applicable, and staleness policy before returning to tools.

```typescript
interface RateRequest {
  base: string;
  quote: string;
  rateType: "mid" | "bid" | "ask";
  asOf?: Date; // historical lookup
}

interface CachedRate {
  rate: string;
  asOf: string;
  provider: string;
  fetchedAt: number;
}

const TTL_BY_TYPE: Record<string, number> = {
  mid: 3600,       // 1 hour intraday refresh
  bid: 300,        // 5 min for payment-adjacent
  ask: 300,
};

async function getRate(req: RateRequest): Promise<CachedRate> {
  const key = `fx:${req.rateType}:${req.base}:${req.quote}:${floorHour(req.asOf)}`;
  const cached = await redis.get<CachedRate>(key);
  if (cached && !isExpired(cached, TTL_BY_TYPE[req.rateType])) {
    return { ...cached, cache_hit: true };
  }

  return singleflight(key, async () => {
    const fresh = await provider.fetch(req);
    const normalized = applyRounding(fresh, req.base, req.quote);
    await redis.set(key, normalized, { ex: TTL_BY_TYPE[req.rateType] * 2 });
    return { ...normalized, cache_hit: false };
  });
}
```

**Singleflight** (or Redis lock with short TTL) prevents cache stampede when a popular pair expires during a traffic spike — common when many agents batch-process month-end expenses simultaneously.

## Stale-while-revalidate for external provider outages

Hard expiry that blocks requests when OANDA times out breaks agent flows mid-conversation. **Stale-while-revalidate (SWR)** serves the last known good rate while async refresh runs, with explicit staleness signalled:

```python
async def get_rate_swr(pair: CurrencyPair) -> RateResponse:
    entry = await cache.get(pair.key)
    now = time.time()

    if entry is None:
        return await fetch_and_cache(pair)

    age = now - entry.fetched_at
    if age < pair.soft_ttl:
        return entry.to_response(stale=False)

    if age < pair.hard_ttl:
        asyncio.create_task(refresh_pair(pair))  # background revalidate
        return entry.to_response(stale=True, stale_seconds=int(age))

    # hard expired — must refresh synchronously or fail closed
    try:
        return await fetch_and_cache(pair)
    except ProviderUnavailable:
        if pair.allow_stale_on_outage:
            return entry.to_response(stale=True, outage_fallback=True)
        raise RateUnavailable("FX provider down; cannot quote settlement amount")
```

`allow_stale_on_outage` should default **false** for payment tools and **true** for informational estimates — policy per tool, not global. The agent system prompt or tool description must tell the model how to phrase stale-rate caveats.

## Historical rates for accounting agents

Agents closing books ask for "USD/EUR on 2025-06-30," not spot. Historical lookups cache **immutably** — a past fixing never changes once published. Key by date; TTL is infinite after provider confirms finality.

Separate hot cache (today's intraday bucket) from cold storage (historical table or object store). Postgres with `(pair, fixing_date)` primary key works for years of daily fixes at negligible size. Agents scanning twelve months of statements query historical service, not live provider historical API on every row.

## Multi-currency agent tool design

One fat `convert_currency` tool beats three overlapping tools (`get_rate`, `convert`, `list_currencies`). The tool should accept amount, base, quote, and `purpose: "estimate" | "settlement"` to route staleness policy.

```python
def convert(amount: Decimal, base: str, quote: str, purpose: str) -> dict:
    rate_resp = rate_service.get_rate(
        base, quote,
        rate_type="mid" if purpose == "estimate" else "bid",
        allow_stale=(purpose == "estimate"),
    )
    converted = (amount * Decimal(rate_resp.rate)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_EVEN
    )
    return {
        "input": {"amount": str(amount), "currency": base},
        "output": {"amount": str(converted), "currency": quote},
        "rate_metadata": rate_resp.to_dict(),
        "purpose": purpose,
    }
```

Log every conversion with `rate_metadata` for audit. Finance disputes trace to a specific fixing, not "the agent guessed."

## Rounding and precision traps

Float arithmetic in agent tools causes cent-level drift across line items. Use `Decimal` end-to-end; cache string-encoded rates from provider JSON without float conversion. Document **banker's rounding** (ROUND_HALF_EVEN) to match finance systems.

Edge case: **zero-decimal currencies** (JPY, KRW). Applying two-decimal rounding before multiply errors totals. Rounding policy belongs in one module consumed by all tools — not reimplemented per agent workflow.

## Compliance and audit trail

Regulated contexts require proving which rate was used, when it was fetched, and from which provider. Store immutable **conversion records** append-only:

| Field | Purpose |
|-------|---------|
| `run_id` / `tool_call_id` | Link to agent session |
| `tenant_id` | Isolation |
| `pair`, `rate`, `provider`, `as_of` | Reproduce calculation |
| `stale`, `cache_hit` | Explain user-visible caveats |
| `purpose` | Estimate vs settlement |

Retention aligns with financial record policy — often seven years. Cache entries expiring from Redis do not delete audit records.

## Testing FX cache behavior

Clock injection tests verify TTL boundaries: at `soft_ttl - 1`, response is fresh; at `soft_ttl + 1`, SWR triggers background refresh. Provider mock failures verify fail-closed settlement vs fail-open estimates.

Consistency test: parallel tool calls in one agent run return identical rate metadata for the same pair and bucket. Fuzz currency pair normalization (`usd` vs `USD`, invalid ISO codes).

## Observability

Metrics: `fx_cache_hit_ratio`, `fx_provider_latency_ms`, `fx_stale_served_total`, `fx_singleflight_coalesced`. Alert on provider error rate and cache hit ratio drop (symptom of key churn or TTL misconfiguration).

Dashboard panel: staleness histogram at serve time — p95 staleness creeping up signals refresh job failure before users notice wrong "today" labels.

## Closing

FX rate caching for agents is financial infrastructure disguised as a performance optimization. Centralize rates behind one service, key caches by pair + type + time bucket, separate estimate staleness from settlement fail-closed behavior, and return metadata the model can cite. The expensive failure mode is not a cache miss — it is two tools in one answer using different rates, or a settlement executed on an undeclared stale quote.

## Resources

- [European Central Bank: Euro Foreign Exchange Reference Rates](https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html)
- [ISO 4217 Currency Codes](https://www.iso.org/iso-4217-currency-codes.html)
- [Stripe: FX Quotes API](https://docs.stripe.com/payments/currencies/localize-prices/fx-quotes-api)
- [Open Exchange Rates Documentation](https://docs.openexchangeRates.org/)
- [Martin Fowler: Patterns of Distributed Systems — Single Leader Replication (applies to rate authority)](https://martinfowler.com/articles/patterns-of-distributed-systems/single-leader-replication.html)
