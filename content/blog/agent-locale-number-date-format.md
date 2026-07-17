---
title: "AI Agents: Locale Number Date Format"
slug: "agent-locale-number-date-format"
description: "Locale Number Date Format: production patterns for ai teams — design, implementation, testing, security, and operations."
datePublished: "2026-07-05"
dateModified: "2026-07-05"
tags: ["AI", "Agent", "Locale"]
keywords: "agent, locale, number, date, format, ai, production, engineering, architecture"
faq:
  - q: "Should agents format numbers and dates themselves or delegate to the client?"
    a: "Store and transmit ISO 8601 dates and plain numeric types in APIs; format at the presentation layer with Intl APIs or equivalent. Agents may verbalize locale-aware strings in natural language responses, but structured tool outputs should stay locale-neutral for downstream parsing."
  - q: "How do you prevent LLMs from hallucinating locale-specific formats?"
    a: "Inject explicit format instructions per user locale in system prompts, post-process structured fields with Intl formatters server-side, and validate tool JSON against schemas that expect ISO dates and decimal numbers — never locale-formatted strings in machine fields."
  - q: "What breaks when mixing en-US and de-DE number parsing?"
    a: "1.234 means one thousand in Germany and one point two three four in the US. Parsing user input with the wrong locale corrupts quantities, currency, and CSV imports. Always parse with the user's active locale, never server default."
  - q: "Does Intl cover every locale requirement for agent products?"
    a: "Intl covers most formatting and parsing for numbers, dates, and currencies. Relative time, time zones, fiscal calendars, and right-to-left layout need additional libraries or rules. Test with pseudo-locales and real regional QA, not only en-US."
---
A user in Berlin asks your finance agent "What did we spend in Q1?" The model replies "Total: $1.234,56" — mixing US dollar symbol with European decimal comma. The chart tooltip shows `3/4/2025` for an event that happened April 3. Support assumes the bug is "the LLM can't do math." The real failure is locale: numbers and dates crossed the stack as ambiguous strings with no consistent formatting contract.

Agent products surface more formatted values than typical CRUD apps — currency in tool outputs, dates in retrieved documents, percentages in generated summaries, and user-typed quantities parsed into tool arguments. Getting locale wrong erodes trust faster than a wrong answer because users read formatting errors as incompetence before they evaluate content.

This article covers locale-safe architecture for agent stacks: Intl usage, API contracts, prompt boundaries, parsing user input, and testing across regions.

## Separate storage, transmission, and presentation

Three layers, three rules:

| Layer | Format | Example |
|-------|--------|---------|
| **Storage** | UTC instant + numeric types | `2025-07-05T14:30:00Z`, `1234.56` |
| **API / tools** | ISO 8601, RFC 3339, decimal numbers | `"date": "2025-04-03"`, `"amount": 1234.56` |
| **UI / NLG** | Locale-formatted strings | `3. Apr. 2025`, `1.234,56 €` |

Never persist `"04/03/2025"` unless the locale is stored beside it. Agent tools returning `"total": "$1,234.56"` force every consumer to guess whether comma is thousands separator.

```typescript
// api/schemas/invoice.ts — locale-neutral tool output
import { z } from "zod";

export const InvoiceSummarySchema = z.object({
  currency: z.string().length(3), // ISO 4217
  totalMinorUnits: z.number().int(), // cents
  periodStart: z.string().datetime(),
  periodEnd: z.string().datetime(),
});
```

Format at the edge:

```typescript
// ui/formatters.ts
export function formatMoney(
  minorUnits: number,
  currency: string,
  locale: string,
): string {
  return new Intl.NumberFormat(locale, {
    style: "currency",
    currency,
  }).format(minorUnits / 100);
}

export function formatDate(date: Date, locale: string, timeZone: string): string {
  return new Intl.DateTimeFormat(locale, {
    dateStyle: "medium",
    timeZone,
  }).format(date);
}
```

## Detecting and propagating user locale

Resolution order that survives logged-in and anonymous agent sessions:

1. Explicit user preference (`settings.locale`)
2. `Accept-Language` header on API requests
3. Account/tenant default
4. `en-US` fallback (documented, not silent assumption)

```typescript
export function resolveLocale(req: Request, user?: User): string {
  if (user?.locale) return user.locale;
  const header = req.headers.get("accept-language");
  if (header) {
    const parsed = header.split(",")[0]?.trim();
    if (parsed && Intl.DateTimeFormat.supportedLocalesOf([parsed]).length) {
      return parsed;
    }
  }
  return "en-US";
}
```

Pass `locale` and `timeZone` to agent orchestration context — not for the model to invent formats, but for server-side post-processing and prompt templates:

```typescript
const context = {
  userId: user.id,
  locale: "de-DE",
  timeZone: "Europe/Berlin",
  formattingRules: {
    dateStyle: "medium",
    currency: "EUR",
  },
};
```

## Prompt engineering for locale-aware agents

Models default to US-centric formats. System prompt excerpt:

```
Structured tool arguments MUST use:
- Dates: ISO 8601 (YYYY-MM-DD or full RFC 3339 with timezone)
- Numbers: plain decimal with dot separator (1234.56), no thousands separators
- Currency amounts: integer minor units + ISO 4217 currency code

When writing natural language for the user, use locale {{locale}} and timezone {{timeZone}}.
Example de-DE: "1.234,56 €" and "3. Apr. 2025".
Never mix US separators with European currency symbols.
```

Post-process NLG when stakes are high (finance, legal):

```typescript
function sanitizeAgentNumbers(text: string, locale: string): string {
  // Replace known bad patterns from evals — extend per locale
  return text.replace(/\$(\d{1,3}(,\d{3})+(\.\d+)?)/g, (_, num) => {
    const value = parseFloat(num.replace(/,/g, ""));
    return formatMoney(Math.round(value * 100), "USD", locale);
  });
}
```

Prefer **structured output** (JSON mode / tool calls) for numeric facts; render prose from structured fields.

## Parsing user input safely

When users type "1.234" or "1,234.56" into agent chat for tool invocation:

```typescript
export function parseLocalizedNumber(input: string, locale: string): number {
  const parts = new Intl.NumberFormat(locale).formatToParts(1234567.89);
  const group = parts.find((p) => p.type === "group")?.value ?? ",";
  const decimal = parts.find((p) => p.type === "decimal")?.value ?? ".";

  const normalized = input
    .trim()
    .replace(new RegExp(`\\${group}`, "g"), "")
    .replace(new RegExp(`\\${decimal}`), ".");

  const value = Number(normalized);
  if (Number.isNaN(value)) {
    throw new ValidationError(`Invalid number for locale ${locale}: ${input}`);
  }
  return value;
}
```

For dates typed in natural language ("next Tuesday", "04/03/2025"), use locale-aware parsers (`@internationalized/date`, `luxon`, or Temporal when available) with explicit disambiguation prompts when parse confidence is low:

```
Agent: Did you mean 3 April 2025 or 4 March 2025? Please confirm (DD.MM.YYYY).
```

## Time zones and agent scheduling

Agents scheduling meetings or reporting "today's" metrics must anchor to user `timeZone`:

```typescript
import { Temporal } from "@js-temporal/polyfill";

export function startOfDayInZone(instant: Temporal.Instant, timeZone: string) {
  return instant.toZonedDateTimeISO(timeZone).toPlainDate();
}
```

Server logs and tool traces stay UTC. User-facing strings always include implied or explicit zone for absolute times: `5. Juli 2025, 14:30 MESZ`.

Relative time ("2 hours ago") uses `Intl.RelativeTimeFormat` with periodic refresh in UI — do not bake relative strings into stored agent messages; they stale.

## RAG and document locale mismatches

Retrieved chunks may contain US-formatted tables while the user expects DE formats. Mitigations:

- Tag source documents with locale metadata at ingest.
- Instruct the model to normalize when quoting figures, or present both: `USD 1,234.56 (≈ 1.134,22 € am 5. Juli 2025)`.
- For Excel/CSV tools, detect delimiter and decimal locale from file metadata before parsing.

## RTL and layout

Arabic and Hebrew locales need RTL layout in agent UI shells — not just translated strings. Use logical CSS properties (`margin-inline-start`), set `dir="rtl"` on container when `locale.startsWith("ar")`, and verify streaming markdown mirrors correctly. `Intl` does not fix layout; test agent chat components in RTL with pseudo-locales.

## Testing strategy

**Unit tests** per locale matrix:

```typescript
describe.each([
  ["en-US", "1,234.56", 1234.56],
  ["de-DE", "1.234,56", 1234.56],
  ["fr-FR", "1 234,56", 1234.56],
])("parseLocalizedNumber %s", (locale, input, expected) => {
  it(`parses ${input}`, () => {
    expect(parseLocalizedNumber(input, locale)).toBe(expected);
  });
});
```

**Snapshot tests** for formatters with frozen `timeZone` — `Europe/Berlin` in CI, not runner local.

**Pseudo-localization** — stretch strings and flip brackets to catch truncation before translation ship.

**LLM evals** — golden prompts per locale verifying tool JSON uses ISO dates and numeric types while NLG matches locale conventions.

**Manual QA** — one native speaker review per target market quarterly; automated tests miss cultural nuance ( fiscal year, week numbering ).

## Common production failures

**Server locale in Docker.** `LANG=C` breaks parsing tests that pass on MacBooks. Set `LC_ALL` in containers explicitly for test jobs; keep production formatting driven by user locale, not server env.

**Spreadsheet export without locale.** CSV opened in German Excel misreads comma decimals. Offer localized CSV (`;` separator) or XLSX with cell formats.

**Caching formatted strings.** CDN-caching HTML with `€1.234,56` baked in serves wrong currency to next user. Cache locale-neutral data; format client-side or at edge with `Vary: Accept-Language`.

**Model fine-tune on US English only.** Retrieval-augmented agents inherit format habits from corpus; reinforce with system prompts and structured output validation.

## The takeaway

Locale number and date formatting in agent products is a cross-stack contract: ISO and numeric types internally, Intl (or equivalent) at presentation, explicit locale propagation into prompts and parsers, and tests that cover de-DE comma decimals as thoroughly as en-US. Fix the boundaries and agents stop "hallucinating" formats they were never given deterministic tools to produce.

## Resources

- [MDN: Intl.NumberFormat](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Intl/NumberFormat) — number and currency formatting
- [MDN: Intl.DateTimeFormat](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Intl/DateTimeFormat) — date and time formatting
- [Unicode CLDR](https://cldr.unicode.org/) — locale data underlying Intl
- [Temporal proposal](https://tc39.es/proposal-temporal/docs/) — modern date/time API for JS
- [W3C Internationalization](https://www.w3.org/International/i18n-drafts/nav/about) — RTL, language tags, and best practices
