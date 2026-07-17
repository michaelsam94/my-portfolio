#!/usr/bin/env python3
"""Expand batch11 chunk2 posts under 1200 words with topic-specific sections."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content" / "blog"
TARGET = 1200
WORD = re.compile(r"\b[\w'-]+\b")

EXPANSIONS: dict[str, str] = {
    "vector-db-filtering-pre-post": """
## Production monitoring for filtered search

Track these metrics per filter type in your vector serving layer:

- **Filter selectivity** — ratio of vectors matching predicate; alert when tenant corpus shrinks below threshold while global corpus grows
- **Result count deficit** — queries returning fewer than requested k; histogram by tenant size
- **Recall@k canary** — nightly job comparing filtered ANN vs brute force on stratified sample
- **Latency split** — ANN traversal time vs post-filter discard time vs metadata fetch time

Dashboard example: p95 latency for `tenant_id` filters on shared index should stay within 2× unfiltered baseline. If latency explodes, payload indexes may be missing on filter fields.

When migrating from post-filter to pre-filter, run shadow mode for two weeks—log both result sets and diff IDs. Disagreement rate above 5% warrants investigation before cutover.

## Case study: date-range filters on news archive

A media site indexed 20 years of articles with `published_at` metadata. Users searched "similar stories" within last 30 days. Post-filter with k=10 returned zero results 34% of the time because recent articles were globally distant in embedding space from query vector dominated by trending topics.

Fix: pre-filter with `published_at > now() - interval '30 days'` reduced candidate pool to 80k vectors; ANN recall@10 recovered to 94%. Editorial team stopped complaining that "search is broken on recent news."

Date-range filters are almost always pre-filter candidates—the selective predicate is predictable and business-critical.
""",
    "vector-db-pgvector-postgres": """
## Connection pooling with pgvector workloads

PgBouncer in transaction mode works for short vector queries but breaks prepared statements unless configured. Session mode preserves prepared statements at cost of pool efficiency. For high QPS vector search:

- Keep embedding generation **outside** the database connection—compute vector in app, pass as parameter
- Use prepared statements for repeated query shape: `ORDER BY embedding <=> $1 LIMIT 10`
- Set `statement_timeout` on search role to prevent runaway sequential scans
- Separate read replica for search if writes cause replication lag affecting freshness SLAs

Neon's serverless Postgres and similar platforms support pgvector—verify HNSW index persistence and autoscaling behavior under index build load.

## Vacuum, bloat, and index health

Heavy UPDATE on embedding columns bloats HNSW indexes. Schedule `VACUUM (ANALYZE)` on tables after bulk re-embed jobs. Monitor `pg_stat_user_tables.n_dead_tup`. For major model migrations, sometimes faster to `CREATE TABLE chunks_v2`, bulk load, swap names in transaction, drop old table—than UPDATE-in-place on millions of rows.

```sql
SELECT schemaname, relname, n_live_tup, n_dead_tup, last_autovacuum
FROM pg_stat_user_tables
WHERE relname = 'chunks';
```

Reindex after bulk delete if query planner chooses sequential scan—check with `EXPLAIN (ANALYZE, BUFFERS)`.

## Hybrid search with Postgres full text

Combine vector and keyword without leaving Postgres:

```sql
SELECT id, content,
  ts_rank_cd(search_vector, plainto_tsquery('english', $2)) AS text_rank,
  embedding <=> $1 AS vector_dist
FROM documents
WHERE tenant_id = $3
  AND search_vector @@ plainto_tsquery('english', $2)
ORDER BY (0.3 * ts_rank_cd(search_vector, plainto_tsquery('english', $2))
         - 0.7 * (embedding <=> $1))
LIMIT 10;
```

Tune weights from click logs. GIN index on `tsvector` column; HNSW on embedding—both must be maintained. For production hybrid at scale, consider dedicated engines—but pgvector hybrid suffices for many SaaS MVPs.
""",
    "vector-search-ivf-pq-index": """
## Faiss operational patterns

If you self-host Faiss indices:

- **Index factory strings** — `IVF4096,PQ64` encodes nlist and PQ params; document chosen string per corpus version
- **Training sample size** — minimum 256 × nlist vectors for stable k-means; undersampling causes empty lists
- **nprobe tuning service** — expose nprobe as runtime config; A/B test recall vs latency without reindex
- **Memory map** — `index.read_index(path, faiss.IO_FLAG_MMAP)` serves indices larger than RAM at latency cost

Snapshot indices to object storage after build. Rebuild pipeline should be reproducible from embedding parquet files plus factory string in git.

## When PQ compression fails visually

Product thumbnails and UI screenshots encoded with aggressive PQ show visible artifacts in similarity search—"find similar looking button" returns wrong matches. For visual similarity, prefer full-precision or HNSW without PQ on smaller corpora; use PQ on text embedding indices where semantic fuzziness absorbs quantization error.

Run perceptual spot checks: query with known nearest neighbor IDs after PQ migration; if ground truth neighbors disappear from top-10, increase code size or reduce compression.
""",
    "vex-vulnerability-triage-sbom": """
## CSAF and machine-readable advisories

CSAF 2.0 JSON advisories extend VEX with product tree, remediations, and references consumable by enterprise GRC tools. Export CSAF alongside CycloneDX SBOM for customers requiring automated ingestion into ServiceNow or Kenna.

Structure releases:

```
release-1.4.2/
  sbom.cdx.json
  vex-1.4.2.csaf.json
  checksums.sha256
```

Sign with cosign or GPG. Customers verify integrity before merging into their vulnerability management database.

## Developer workflow integration

Pre-commit hooks generating SBOM on every build are noisy—generate SBOM at release tag, attach to GitHub Release assets. Dependabot and Renovate handle day-to-day dependency bumps; SBOM diff between releases shows component changes for security review.

Train engineers: **not_affected** requires justification text a stranger understands in six months. "Doesn't apply" is not documentation.

## Reducing scanner noise without lying

Common legitimate not_affected cases:

- CVE in devDependency tooling not in runtime container
- Vulnerable function never called—support with static analysis report link
- Distro package version flagged but vendor backport applied—link distro security notice

Questionable cases needing patch anyway:

- Network-facing parser CVE even if "we don't use that code path"—attack surface arguments fail audits
- Critical CVSS in direct dependency with available fix—patch first, VEX later
""",
    "view-transitions-api": """
## Framework integration details

**Vue Router:**

```javascript
router.beforeResolve(async (to, from) => {
  if (!document.startViewTransition) return true;
  return new Promise((resolve) => {
    document.startViewTransition(async () => {
      resolve(true);
      await router.isReady();
    });
  });
});
```

**Next.js App Router** — View Transitions API integration is evolving; use `document.startViewTransition` wrapping `router.push` in client components for soft navigations within same layout. Cross-layout transitions may need `@view-transition` meta for MPA-style navigations.

**Astro** — mostly MPA; cross-document view transitions apply when enabling `@view-transition { navigation: auto; }` in shared layout CSS.

## Performance measurement

View transitions add snapshot and animation cost. Profile on low-end devices—animating large DOM snapshots can frame-drop. Scope transitions to layout shell; avoid transitioning data-heavy tables. Use Chrome Performance panel → Frames during transition; target 60fps or reduce duration under `prefers-reduced-motion`.

If INP regresses after adding transitions, default to instant navigation on interactive dashboards; keep transitions on marketing pages only.
""",
    "voice-agents-stt-tts-pipelines": """
## Latency breakdown instrumentation

Log structured timestamps per session:

```json
{
  "utterance_end": 1710000000100,
  "stt_final": 1710000000250,
  "llm_first_token": 1710000000450,
  "tts_first_byte": 1710000000520,
  "audio_play_start": 1710000000580
}
```

Aggregate p50/p95 per stage weekly. Teams optimize LLM while STT dominates—data prevents misfocus.

## Multi-language and code-switching

STT models vary by locale—route by user language setting, not browser default alone. Code-switching (English product terms in Hindi sentences) challenges monolingual models; choose STT with multilingual training or accept higher error rate with confirmation prompts ("Did you say X?").

TTS voice selection affects brand—cache generated audio for fixed system phrases (greeting, error messages) to skip synthesis latency on every session open.
""",
    "vue-3-composition-api-patterns": """
## Advanced composable patterns

**Composable with arguments and defaults:**

```typescript
export function useFetch<T>(url: MaybeRef<string>, options?: RequestInit) {
  const data = ref<T | null>(null)
  const error = ref<Error | null>(null)
  const loading = ref(false)

  async function execute() {
    loading.value = true
    try {
      const res = await fetch(toValue(url), options)
      data.value = await res.json()
    } catch (e) {
      error.value = e as Error
    } finally {
      loading.value = false
    }
  }

  watch(() => toValue(url), execute, { immediate: true })
  return { data, error, loading, execute }
}
```

**Shared state via composable factory:**

```typescript
const createState = () => {
  const count = ref(0)
  return { count, increment: () => count.value++ }
}
let instance: ReturnType<typeof createState> | null = null
export function useSharedCounter() {
  if (!instance) instance = createState()
  return instance
}
```

Use sparingly—prefer Pinia for truly global state.

## SSR considerations

`onMounted` only runs client-side—fetch in setup without guarding runs on server too. Use `import.meta.env.SSR` or Nuxt's `useAsyncData` for isomorphic data. Mismatch between server HTML and client hydration causes warnings—align initial ref values with server-rendered content.

## DevTools and debugging

Vue DevTools 6 shows setup state, composable sources when using `<script setup>`. Name components with `defineOptions({ name: 'UserList' })` for traceability in profiler.
""",
    "wasm-workloads-kubernetes": """
## Comparison with container cold starts on same cluster

Benchmark methodology:

1. Deploy equivalent HTTP handler—JSON echo—in WASM (Spin) and Alpine container
2. Scale deployment to zero (KEDA) or flood with unique URLs preventing cache
3. Measure p50/p95 cold start over 1000 requests from idle
4. Include image pull time for containers from empty node pool

Document node pool warmup—first request after cluster autoscale dominates tail latency for both models.

## wasmCloud vs SpinKube decision matrix

| Factor | SpinKube | wasmCloud |
|--------|----------|-----------|
| Primary model | HTTP components | Capability providers |
| Kubernetes native | Yes (operator) | Hosts on K8s, lattice separate |
| Best for | Request/response WASM | Distributed actors + NATS |
| Learning curve | Lower for web devs | Higher, more concepts |

Teams already on Fermyon Spin locally migrate to SpinKube naturally. wasmCloud suits edge-to-cloud symmetric deployments with declarative capability links.

## Future: component mesh

WASI 0.2 component model enables composing WASM modules—watch for Kubernetes runtimes supporting component packaging. Early adopters should pin toolchain versions; component ABI still moves.
""",
    "web-accessibility-aria-patterns": """
## Landmarks and document structure

Combine ARIA with semantic landmarks:

```html
<header role="banner">...</header>
<nav aria-label="Main">...</nav>
<main id="main">...</main>
<aside aria-label="Related articles">...</aside>
<footer role="contentinfo">...</footer>
```

One `main` per page. Multiple `nav` elements need distinct `aria-label` values—"Main", "Footer", "Account".

Heading hierarchy: do not skip levels for styling—h1 once, h2 sections, h3 subsections. Screen reader users navigate by heading rotor.

## aria-describedby for hints and errors

```html
<input id="pw" aria-describedby="pw-hint pw-error" />
<p id="pw-hint">Minimum 12 characters</p>
<p id="pw-error" role="alert" hidden>...</p>
```

Space-separated IDs in `aria-describedby` concatenate announcements. Toggle error visibility and `hidden` attribute together.

## Dialog and menu roles without implementation bugs

If using ARIA menu pattern, implement full keyboard spec or use native `<select>`. Half-implemented `role="menu"` is worse than styled native controls—audit with APG checklist before shipping.
""",
    "web-accessibility-keyboard-navigation": """
## Focus order in complex layouts

Mega-menus, split buttons, and comboboxes need documented keyboard specs in design system docs—developers should not reverse-engineer from Figma.

**Split button:**

- Tab focuses primary action button
- Arrow down or separate Tab to overflow menu trigger
- Enter on trigger opens menu, first item focused

**Modal wizards:** focus first field on step change; announce step progress via `aria-current="step"`.

## Internationalization and keyboard

RTL layouts mirror visual order—tab order must follow RTL reading order using logical properties (`margin-inline-start`) and DOM order matching localized layout.

Keyboard shortcuts (`/` to focus search) need documented discovery and must not conflict with assistive technology or browser shortcuts—allow rebinding in settings.
""",
    "web-accessibility-screen-reader-testing": """
## Test case template for releases

```
Feature: [name]
Tester: [name]
Date: [date]
SR/Browser: NVDA 2024.2 / Firefox 128

Steps:
1. ...
Expected announcement: "..."
Actual: "..."

Pass/Fail:
WCAG ref:
```

Store in ticket system linked to feature PR. Regression suite for tier-1 flows runs quarterly minimum.

## Synthetic speech vs real SR

Automated speech synthesis of accessibility tree (some CI tools) catches missing names but not confusing structure. Use synthesis for smoke; human SR for sign-off.

## JAWS considerations

Enterprise B2B may require JAWS testing—licensing cost applies. JAWS-specific behaviors (forms mode, virtual cursor) differ from NVDA; do not assume fix for one fixes all.
""",
    "web-color-functions-oklch": """
## Design token migration checklist

1. Export Figma styles to OKLCH tokens (Figma supports OKLCH natively in 2025+)
2. Replace `:root` CSS variables in one PR per app shell
3. Run visual regression on marketing + app chrome
4. Update Storybook swatches for designers
5. Document token naming: `--color-brand-500` not `--blue`

## Print and forced-colors modes

```css
@media print {
  :root { --brand: oklch(30% 0.05 250); }
}

@media (forced-colors: active) {
  .button { border: 2px solid ButtonText; }
}
```

OKLCH does not exempt you from Windows High Contrast—test `forced-colors` separately.

## OKLCH in Canvas and WebGL

CSS OKLCH does not automatically propagate to canvas—convert with color.js if drawing charts programmatically for consistent brand colors between DOM and canvas layers.
""",
    "web-components-2026": """
## Enterprise adoption patterns

Large orgs publish web component design systems as npm packages with:

- Custom elements manifest for IDE autocomplete
- Storybook for WC docs
- React/Vue/Angular wrapper packages maintained in monorepo
- Semver for breaking attribute changes

Governance: design tokens versioned separately from component semver—token breaking change may not require major component bump if fallbacks exist.

## Micro-frontend integration

Single-spa and Module Federation hosts load WC bundles as side-effect imports:

```javascript
await import('https://cdn.example.com/ds-components/1.4.0/index.js');
document.body.appendChild(document.createElement('ds-header'));
```

Version multiple WC bundles on same page carefully—duplicate custom element registration throws. Namespace prefixes (`ds-v2-button`) for major versions if parallel versions required during migration.

## Security: shadow DOM is not a security boundary

Malicious host page can still pass dangerous attributes or social-engineer users outside shadow. Sanitize attributes reflected into shadow, validate slotted content if rendered unsafely, CSP on host page still required.
""",
    "web-components-form-association": """
## Integration with form-associated native elements

Custom elements participate in `form.elements` and submit with form:

```javascript
console.log([...form.elements].map(e => e.name));
// includes 'star-rating' when associated
```

`ElementInternals.labels` updates when label association changes—useful for dynamic forms.

## ValidationMessage and i18n

Browser-native validation UI from `reportValidity()` may not match app locale. Custom validation UI still uses internals API for validity state while rendering translated messages:

```javascript
this._internals.setValidity({ customError: true }, t('rating.required'));
this.dispatchEvent(new CustomEvent('ds-invalid', { bubbles: true }));
```

## Testing form reset and restore

`setFormValue(value, state)` second argument preserves restore state for bfcache and form reset—serialize widget internal state as JSON for complex widgets so back-navigation restores star selections correctly.
""",
    "web-components-shadow-dom": """
## constructable stylesheets at scale

Share one adopted stylesheet across component instances:

```javascript
const sheet = new CSSStyleSheet();
await sheet.replace(stylesText);
class DsCard extends HTMLElement {
  connectedCallback() {
    this.shadowRoot.adoptedStyleSheets = [sharedSheet];
  }
}
```

Reduces memory vs inline `<style>` per instance on pages with hundreds of cards.

## Slot change events

Listen for slotted content changes:

```javascript
const slot = this.shadowRoot.querySelector('slot');
slot.addEventListener('slotchange', () => {
  const nodes = slot.assignedNodes({ flatten: true });
  this._updateFromSlottedContent(nodes);
});
```

Dynamic slotted forms need slotchange handlers to wire up labels and validation.

## Light DOM CSS piercing for legacy

When migrating from non-shadow components, document which global CSS rules must become `--token` variables or `::part()` exposures—grep host app stylesheets for component tag selectors before enabling shadow.
""",
    "web-dialog-element-modal": """
## Animation without breaking focus

Animate `::backdrop` opacity and dialog `transform` only—do not `display:none` during exit animation; listen `close` event after CSS animation completes via `animationend` if delaying `close()` call.

```css
dialog::backdrop { transition: opacity 0.2s; }
dialog[open]::backdrop { opacity: 1; }
```

## Form submission patterns

Multi-step dialogs can nest forms—only one `method="dialog"` form per dialog typically. For complex flows, use regular form with explicit `dialog.close()` on success after fetch.

## Analytics and dialog events

Track open/close with `toggle` event (where supported) or wrap `showModal`/`close` calls—funnel analysis on confirmation dialogs requires knowing cancel vs confirm rates via `returnValue` logging, not guesswork from page views.
""",
    "web-forms-native-validation": """
## Integration with design systems

Design system inputs should expose `validity` state to CSS:

```css
.ds-input:user-invalid { border-color: var(--error); }
.ds-input:user-valid { border-color: var(--success-subtle); }
```

Pair with `aria-invalid` toggled in `invalid` event listener—native and ARIA stay synchronized.

## Server-side mirror

Duplicate rules server-side—never trust client validation alone. Share constraint definitions via OpenAPI or shared Zod schema code-generated to HTML attributes where possible.

## Progressive enhancement without JS

Without JS, native validation still works on submit—ensure form works with full page POST for critical flows (login, payment) even in enhanced SPA mode.
""",
    "web-htmx-server-driven-ui": """
## Caching partials

Fragment caches keyed by `(route, user_segment, page)` reduce server render cost:

```python
@cache.memoize(timeout=60)
def render_contact_table(page, tenant_id):
    return render_template('_contact_rows.html', ...)
```

Invalidate on mutation via `HX-Trigger` calling cache bust endpoint or versioned ETags in `HX-Headers`.

## WebSocket + htmx extension

htmx websockets extension swaps messages into DOM—useful for live dashboards without full SPA. Still sanitize HTML fragments from server; XSS in partial templates is critical severity.

## Comparison with Hotwire/Turbo

Rails Turbo Drive similar to htmx philosophy—teams on Rails often use Turbo; htmx fits Python, Go, PHP, Java templates equally. Choose based on server stack, not religious preference.
""",
    "web-islands-partial-hydration": """
## Client island communication

Islands sharing state without full SPA:

- **Custom events** on `document` for loose coupling
- **URL search params** for shareable filter state
- **Tiny shared store** (nanostores) imported only by islands that need it

Avoid prop drilling across island boundaries through global window hacks.

## Edge deployment

Astro on Cloudflare Pages deploys static HTML at edge; islands hydrate at edge or client depending on adapter. Verify `client:visible` Intersection Observer works when HTML served from CDN—no difference, but test lazy hydration with real mobile viewports.

## Bundle analysis per island

Each island is separate JS entry—run analyzer per island chunk. React island importing entire `@mui/material` defeats purpose; import path-level or use lighter primitives.
""",
    "web-performance-back-forward-cache": """
## Interaction with SPA frameworks

Next.js client navigations do not use bfcache for in-app routing—bfcache applies when leaving site or full document navigation. Educate stakeholders: bfcache optimizes back from detail page to listing after full navigation, not Router.back() within SPA shell unless it triggers history navigation with document unload.

## Prerender and bfcache

Speculation Rules prerendering interacts with bfcache—test combination on Chrome; prerendered pages may have different cache eligibility. Monitor `notRestoredReasons` after enabling speculation rules.
""",
    "web-performance-bundle-splitting": """
## Module federation caveat

Module Federation shares dependencies at runtime across micro-frontends—reduces duplicate React but adds runtime orchestration complexity. Measure LCP impact of federation bootstrap before adopting for performance reasons alone.

## Service worker precaching vs splitting

Workbox precache main shell; runtime cache route chunks on first visit. Version precache manifest on deploy—stale SW serving old chunk hashes causes load failures; `skipWaiting` + `clientsClaim` strategy documented in SW migration runbook.
""",
    "web-performance-core-web-vitals": """
## Setting team SLOs

Example internal SLOs tied to CrUX:

- Marketing origin: LCP p75 < 2.0s, CLS < 0.05, INP < 150ms
- App authenticated shell: INP p75 < 200ms (LCP less SEO-critical)

Error budget: two consecutive weeks failing CrUX "Good" threshold triggers perf sprint before new feature work on affected templates.

## Competitive benchmarking

PageSpeed Insights compares origin to similar sites—use for stakeholder communication, not absolute targets. Retail peers with heavier images may have worse LCP; beat your own baseline week-over-week first.
""",
    "web-performance-font-loading": """
## Variable fonts loading

Single variable WOFF2 reduces requests vs multiple weights—preload once with `font-weight: 100 900` range in `@font-face`. Subset variable fonts aggressively; full axis font may exceed multiple static files.

## Legal and licensing

Verify font license allows self-hosting and subsetting—Adobe Fonts subscription may prohibit extraction. Open-source fonts (Inter, Source Sans) simplify pipeline.

## Font loading API advanced

```javascript
const font = new FontFace('Inter', 'url(/fonts/inter.woff2)');
await font.load();
document.fonts.add(font);
```

Imperative loading for comic-style progressive enhancement—show custom font only after load completes without FOIT using `document.fonts.ready` promise before measuring LCP text.
""",
    "web-performance-image-formats-avif": """
## Screenshot and UI imagery

AVIF lossy compression blurs small text in marketing screenshots—use WebP lossless or PNG for UI captures with text. Photos and hero photography benefit most from AVIF.

## Email clients

Most email clients ignore AVIF—serve JPEG in `<img>` for transactional email; AVIF for web only.

## Image CDNs and origin shield

Transform at CDN edge on first request caches AVIF variant at PoP—origin serves single JPEG master. Configure quality rungs (q=45, q=55, q=65) and let CDN negotiate.
""",
    "web-performance-inp-interaction": """
## Interaction targets worth profiling first

From CrUX and RUM, prioritize:

1. Primary CTA buttons (add to cart, submit, save)
2. Menu open/close (hamburger, dropdown)
3. Autocomplete and combobox keyboard navigation
4. Drag-and-drop alternatives lacking keyboard path (fix a11y + INP together)

## scheduler.postTask prioritization

Where supported, user-visible updates get `user-blocking` priority; background prefetch `background`:

```javascript
scheduler.postTask(() => updateUI(), { priority: 'user-blocking' });
```

Falls back to `setTimeout` in unsupported browsers—feature detect.
""",
    "web-performance-lcp-optimization": """
## Soft navigations and LCP

Chrome Soft Navigation LCP experimental API tracks LCP on client-side navigations—if building SPA, monitor soft LCP separately from hard navigation CrUX. Soft LCP often worse due to JS-rendered content; SSR route shells help.

## Resource load delay vs duration

LCP attribution splits:

- **Time to first byte** — server/CDN
- **Resource load delay** — gap between TTFB and resource start (discovery blocked)
- **Resource load duration** — download
- **Element render delay** — parse/layout after resource ready

Fix largest bucket first—teams often optimize image compression while discovery delay dominates because CSS blocked preload.
""",
}


def body_words(text: str) -> int:
    parts = text.split("---", 2)
    body = parts[2] if len(parts) >= 3 else text
    return len(WORD.findall(body))


def main():
    expanded = 0
    for slug, addition in EXPANSIONS.items():
        path = BLOG / f"{slug}.md"
        if not path.exists():
            continue
        raw = path.read_text()
        wc = body_words(raw)
        if wc >= TARGET:
            continue
        # avoid double-append
        first_heading = addition.strip().split("\n")[0]
        if first_heading in raw:
            continue
        new_raw = raw.rstrip() + "\n" + addition.strip() + "\n"
        path.write_text(new_raw)
        new_wc = body_words(new_raw)
        print(f"expanded {slug}: {wc} -> {new_wc}")
        expanded += 1
    print(f"Expanded {expanded} files")


if __name__ == "__main__":
    main()
