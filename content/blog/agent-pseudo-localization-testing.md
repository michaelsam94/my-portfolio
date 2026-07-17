---
title: "AI Agents: Pseudo Localization Testing"
slug: "agent-pseudo-localization-testing"
description: "Catch truncated agent UI strings, broken RTL layouts, and missing i18n keys before real translation—using pseudo-locale expansion in CI and staging."
datePublished: "2026-07-09"
dateModified: "2026-07-09"
tags: ["AI", "Agent", "Pseudo"]
keywords: "pseudo localization, pseudolocale, i18n testing, string expansion, agent UI i18n, RTL layout testing, localization CI"
faq:
  - q: "What is pseudo-localization versus real translation?"
    a: "Pseudo-localization transforms your base-language strings in software—adding accents, brackets, and length padding—without human translators. It exposes hard-coded English, layout truncation, and missing keys early. Real translation validates meaning; pseudo-loc validates engineering readiness."
  - q: "How much longer should pseudo-locale strings be?"
    a: "A common rule is 30–40% expansion plus delimiter wrapping like «⟦ text ⟧» so untranslated strings stand out visually. German and Finnish often exceed 40% in real life—agent products with dense tool labels may test 50% expansion on critical screens."
  - q: "Where does pseudo-loc fit in CI for agent products?"
    a: "Run a pseudo-loc build on every PR for web and mobile shells, snapshot critical flows (chat input, tool approval dialogs, error toasts), and fail if new keys lack entries or if visual regression exceeds thresholds. Keep English production builds as default for perf tests."
  - q: "Does pseudo-loc help LLM-generated user-facing text?"
    a: "Only for static UI chrome—buttons, menus, settings—not for model output. For dynamic agent replies, separate tests cover language detection and template wrapping. Pseudo-loc still catches truncated labels around the chat surface and permission prompts."
---
The German launch looked ready on paper: PO files uploaded, LQA scheduled, marketing assets localized. Within a day, support collected screenshots of clipped "Werkzeug bestätigen" buttons, overlapping sidebar labels in the agent console, and a permissions modal showing raw key names like `agent.tools.approve_title`. Translators were blamed until an engineer flipped staging to pseudo-locale over lunch and reproduced every bug in English—just with «⟦ bŕàçĸêţêđ ⟧» characters and strings 40% longer than design spec.

Pseudo-localization testing is the cheapest internationalization insurance agent teams skip because chat demos ship in English. Agent UIs accumulate strings fast: tool confirmation dialogs, streaming status chips, retrieval source labels, error recovery hints. Each sits inside flex layouts tuned on a 13" MacBook. Pseudo-loc stress-tests those layouts before you pay for translation and before German nouns break your grid.

## What pseudo-localization does

Given a source string:

```
Approve tool call
```

A pseudo-locale transform might produce:

```
«⟦ Âþþŕöṽê ŧööļ çäļļ ⟧»   
```

Mechanisms in play:

1. **Delimiter wrapping** — visually flags strings that bypassed the i18n layer (no brackets = hard-coded).
2. **Accent mutation** — proves Unicode rendering and font coverage.
3. **Length expansion** — pads with filler characters to simulate verbose languages.
4. **Optional RTL mirroring** — pseudo-Arabic mode catches alignment bugs before true RTL translation.

None of this validates translation quality. It validates that your **engineering surface** can display localized text without functional regression.

## Building a pseudo-locale transform

Keep transforms deterministic and unit-tested:

```typescript
// pseudo.ts — deterministic expansion for en-XA style locale
const EXPANSION_FACTOR = 1.4;
const PAD_CHAR = "·";

export function pseudoLocalize(text: string): string {
  if (!text.trim()) return text;

  const expanded = expandLength(text, EXPANSION_FACTOR);
  const accented = applyDiacritics(expanded);
  return `«⟦ ${accented} ⟧»`;
}

function expandLength(text: string, factor: number): string {
  const target = Math.ceil(text.length * factor);
  const padLen = Math.max(0, target - text.length);
  const left = Math.floor(padLen / 2);
  const right = padLen - left;
  return PAD_CHAR.repeat(left) + text + PAD_CHAR.repeat(right);
}

function applyDiacritics(text: string): string {
  const map: Record<string, string> = {
    a: "ä", e: "ë", i: "ï", o: "ö", u: "ü",
    A: "Ä", E: "Ë", I: "Ï", O: "Ö", U: "Ü",
    c: "ç", s: "š", n: "ñ",
  };
  return [...text].map((c) => map[c] ?? c).join("");
}
```

Wire this into your i18n loader when `locale === 'en-XA'` (Microsoft-style pseudo locale) or `en-PLOC` internally.

```typescript
// i18n init
import i18n from "i18next";
import { pseudoLocalize } from "./pseudo";

i18n.init({
  lng: process.env.NEXT_PUBLIC_LOCALE ?? "en",
  resources: { en: { translation: enStrings } },
  postProcess: [],
});

if (process.env.NEXT_PUBLIC_LOCALE === "en-XA") {
  i18n.use({
    type: "postProcessor",
    name: "pseudo",
    process: (value: string) => pseudoLocalize(value),
  });
}
```

## Agent-specific surfaces to test first

Not every screen deserves equal priority. Start where truncation causes **wrong actions**:

| Surface | Why it matters |
|---------|----------------|
| Tool approval dialog | Long tool names + args; mis-clicks authorize bad calls |
| Permission scopes | Legal copy; clipping hides data use disclosure |
| Streaming status | Narrow chips truncate model/thinking labels |
| Error recovery | Users miss "Retry" vs "Cancel" when clipped |
| Retrieval citations | Source titles overflow card layouts |
| Settings / API keys | Form labels collide in dense admin panels |

Dynamic model output stays in the user's language; pseudo-loc covers **chrome** around the stream.

## CI integration patterns

**Build matrix:**

```yaml
# .github/workflows/i18n.yml
jobs:
  pseudo-loc-screenshots:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npm ci
      - run: npm run build -- --locale=en-XA
      - run: npx playwright test tests/i18n/pseudo-loc.spec.ts
```

Playwright spec visits critical routes, asserts no literal English outside allowed zones, and compares screenshots to baselines with perceptual diff tolerance.

**Key parity check** — fail if English keys ⊄ pseudo bundle:

```python
# scripts/check_i18n_keys.py
import json, sys

en = json.load(open("locales/en.json"))
xa = json.load(open("locales/en-XA.json"))  # or generated overlay

missing = set(en) - set(xa)
if missing:
    print("Missing pseudo-loc keys:", sorted(missing)[:20])
    sys.exit(1)
```

Generate `en-XA.json` in CI from `en.json` via script rather than maintaining by hand.

## RTL and plural edge cases

Pseudo-Arabic (`ar-XA`) with `dir=rtl` on `<html>` catches:

- Icon buttons that do not flip but should (or vice versa)
- Chat bubbles aligned LTR while shell is RTL
- Scroll containers anchoring wrong edge

Pluralization breaks independently of length:

```json
{
  "agent.tools.selected": "{count, plural, one {# tool selected} other {# tools selected}}"
}
```

English hides malformed ICU messages; pseudo-loc runs with `count=0,1,2,5` in tests:

```typescript
expect(i18n.t("agent.tools.selected", { count: 5, lng: "en-XA" }))
  .toMatch(/«⟦.*5.*⟧»/);
```

Agent products love dynamic counts—queued tools, attached files, memory entries.

## What pseudo-loc will not catch

- culturally wrong idioms (translation problem)
- LLM replies that ignore locale headers (orchestration problem)
- locale-aware date/number formatting bugs unless tests pass `Intl` locales explicitly
- platform fonts missing glyphs for real Japanese or Arabic (needs native script spot checks)

Combine pseudo-loc with a **pilot locale** (often German or Brazilian Portuguese) before broad rollout.

## Staging toggle for designers

Give design and PM a staging feature flag:

```
?locale=en-XA
```

They catch truncation without developer proxies. Document the URL param in your internal handbook; remove from production marketing sites to avoid confusing SEO.

## Measuring success

Track pseudo-loc CI failures over time. A spike after a UI refactor is expected; chronic failures mean i18n is not owned. Goal: zero missing keys on main, screenshot diffs reviewed in PR like any visual change.

When the German launch reopened after pseudo-loc fixes, clipped buttons disappeared—not because translators shortened words, but because engineering gave strings room to grow. That is the point.

## Mobile agent clients: Compose, SwiftUI, Flutter

Native shells introduce constraints web pseudo-loc misses:

**Dynamic type / font scaling.** iOS Dynamic Type and Android fontScale can exceed pseudo-loc padding. Run screenshot tests at `fontScale=1.3` in addition to `en-XA`.

```kotlin
// Compose preview-driven pseudo-loc check
@Preview(locale = "en-XA", fontScale = 1.3f)
@Composable
fun ToolApprovalDialogPreview() {
    AppTheme(locale = pseudoLocale()) {
        ToolApprovalDialog(
            toolName = stringResource(R.string.agent_tool_calendar_create),
            onApprove = {},
            onDeny = {},
        )
    }
}
```

**Truncated `Text` with maxLines=1.** Chat product patterns love single-line ellipses. Pseudo-loc exposes them immediately—either allow wrap on approval dialogs or shorten keys at design time.

**Accessibility strings.** VoiceOver reads full pseudo-expanded text; verify TalkBack does not stall on absurdly long chip labels. Cap expansion on `contentDescription` if needed while keeping visible labels expanded.

Flutter's `flutter gen-l10n` supports synthetic locales via `supportedLocales` including `Locale('en', 'XA')` and a custom delegate wrapping ARB strings.

## Coordinating with translation vendors

Export pseudo-loc screenshots in PRs labeled "layout reference only—do not translate." Vendors otherwise waste cycles on «⟦ Âþþŕöṽê ⟧» strings. Your TMS should filter locale `en-XA` from production translation jobs while keeping it in engineering builds.

Provide translators context for agent terminology—"tool," "session," "memory" may have domain-specific glossary entries. Pseudo-loc proves layout; glossary proves semantics.

## Accessibility overlap

Pseudo-loc complements WCAG checks: accent mutation reveals mojibake when fonts lack combining characters; expansion stress-tests reflow required by 1.4.10. It does not replace contrast or focus order tests.

Screen reader locale should follow the same `en-XA` toggle in QA builds so engineers hear untranslated keys as spoken English without brackets—another signal hard-coded strings exist.

## Resources

- [Microsoft — Pseudo-localization](https://learn.microsoft.com/en-us/globalization/internationalization/pseudo-localization)
- [Google i18n — ICU MessageFormat](https://unicode-org.github.io/icu/userguide/format_parse/messages/)
- [FormatJS — react-intl testing patterns](https://formatjs.io/docs/testing/)
- [Playwright — visual comparisons](https://playwright.dev/docs/test-snapshots)
- [W3C — Internationalization best practices](https://www.w3.org/International/techniques/developing-specs)
