---
title: "AI Agents: Design System Versioning"
slug: "agent-design-system-versioning"
description: "Semantic versioning, release trains, and consumer contracts for design systems that ship across web, mobile, and agent-generated UIs without breaking production."
datePublished: "2026-06-17"
dateModified: "2026-06-17"
tags: ["AI", "Agent", "Design"]
keywords: "design system versioning, semver components, release train, breaking changes, agent UI generation, Figma tokens sync"
faq:
  - q: "Should design system packages follow strict semver for component APIs?"
    a: "Yes for published npm/Maven packages consumed by multiple teams. Patch for bug fixes and visual tweaks that preserve DOM structure and props. Minor for additive props, new variants, and deprecated-but-still-working APIs. Major only when you remove props, change default behavior, or alter accessibility contracts that downstream tests depend on."
  - q: "How do you version a design system when agents generate UI from the same token source?"
    a: "Pin agents to a specific design-system major version in their system prompt and tool schema. Expose a version manifest (tokens + component API snapshot) the agent reads at session start. Never let an agent pick 'latest' at runtime—generation drift is harder to detect than import drift."
  - q: "What is the minimum deprecation window before a breaking change?"
    a: "Two release cycles for internal consumers, one quarter for external SDK users. Pair deprecation with codemods, Storybook migration notes, and CI warnings on deprecated imports. If usage telemetry shows >5% of traffic still on deprecated APIs at window end, extend rather than break."
  - q: "How do mobile and web stay on compatible design system versions?"
    a: "Use a shared token package as the single source of truth and version it independently from platform component libraries. Web and mobile component libs declare compatible token ranges in their package metadata. CI fails if a mobile release requires token features the web release has not adopted yet."
---
A product team shipped a minor design system bump on Tuesday—new button padding, a renamed `variant` prop on `Card`, and a deprecated `size="compact"` path. By Thursday, three squads had green CI, but customer-facing agent chat UIs rendered misaligned action chips because the agent runtime pulled `@acme/ui@latest` while the host app pinned `@acme/ui@4.2.0`. Nobody had treated the design system as a **versioned platform contract** shared by human engineers and generative UI paths. Design system versioning is how you prevent that class of silent skew.

## Versioning layers: tokens, components, and documentation

Mature design systems expose three versioned surfaces that move at different speeds:

| Layer | What changes | Typical cadence | Consumer |
|-------|--------------|-----------------|----------|
| **Design tokens** | Color, spacing, typography primitives | Weekly minor, quarterly major | CSS, iOS, Android, Figma |
| **Component API** | Props, slots, events, a11y roles | Biweekly minor, semiannual major | App repos, Storybook, agent schemas |
| **Patterns & docs** | Usage guidance, composition recipes | Continuous | Designers, PMs, LLM prompt context |

Coupling all three to one semver number creates either paralysis (everything is major) or lies (you shipped breaking token contrast ratios under a patch). Split packages: `@acme/tokens@2.4.1`, `@acme/react@5.1.0`, `@acme/patterns-docs@2026.06`.

## Semver rules that survive design review

Write explicit rules engineers can apply without a committee:

- **Patch** — Visual adjustment with no prop/DOM change; bug fix restoring documented behavior; internal refactor with identical snapshot tests.
- **Minor** — New optional prop; new component; deprecated prop still functional with console warning in dev; token alias added without removing old names.
- **Major** — Removed or renamed prop; changed default variant; altered focus order or ARIA labeling; token removed or remapped in ways that shift contrast ratios below WCAG thresholds.

Document these in `VERSIONING.md` and enforce via changesets or semantic-release with custom analyzers that inspect Storybook prop tables, not just commit messages.

## Release trains and compatibility windows

Platform teams benefit from **predictable release trains**: cut `main` to `release/5.x` every two weeks, cherry-pick only fixes, publish from the branch. App teams pin `^5.1.0` and plan major upgrades quarterly.

```json
{
  "name": "@acme/react",
  "version": "5.2.0",
  "peerDependencies": {
    "@acme/tokens": "^2.4.0"
  },
  "acme": {
    "releaseTrain": "2026-Q2",
    "compatibleAgents": ["agent-ui-schema@3.x"],
    "breakingChangePolicy": "https://design.acme.com/versioning"
  }
}
```

Expose `compatibleAgents` so agent infrastructure refuses to pair an outdated UI schema with a newer component library.

## Consumer contracts: manifests and lockfiles

Every consuming app—and every agent runtime—should record a **design system lock manifest**:

```typescript
// design-system.lock.json — committed beside package-lock.json
export interface DesignSystemLock {
  tokens: { name: string; version: string; checksum: string };
  react: { name: string; version: string };
  figmaLibrary: { fileKey: string; publishedVersion: string };
  agentSchema: { version: string; componentAllowlist: string[] };
}

export function assertCompatible(
  lock: DesignSystemLock,
  published: { tokens: string; react: string }
): void {
  const [lockMajor] = lock.react.version.split(".");
  const [pubMajor] = published.react.split(".");
  if (lockMajor !== pubMajor) {
    throw new Error(
      `Design system major mismatch: app locks ${lock.react.version}, CI resolved ${published.react}`
    );
  }
}
```

Run `assertCompatible` in CI after `npm ci` and before visual regression suites. Agents load the same manifest at cold start; tool calls that emit JSX must validate against `componentAllowlist`.

## Coordinating Figma, code, and agent prompts

Designers publish Figma libraries with version numbers. Automate sync so a Figma publish triggers a tokens PR, not the reverse:

```yaml
# .github/workflows/figma-tokens-sync.yml
on:
  repository_dispatch:
    types: [figma-library-published]
jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npm run tokens:pull -- --figma-version ${{ github.event.client_payload.version }}
      - run: npm run tokens:diff -- --fail-on-breaking
      - run: npm run changeset version
```

`tokens:diff --fail-on-breaking` compares token renames and removed keys against your semver policy. If contrast ratios regress, fail the pipeline even when designers labeled the change "cosmetic."

For agents, snapshot the token JSON and component prop JSON Schema into the prompt cache:

```typescript
const designContext = await loadDesignSystemContext({
  lockFile: "design-system.lock.json",
  include: ["tokens", "componentSchemas", "deprecatedProps"],
});

const systemPrompt = `
You generate UI using ONLY components and tokens from this manifest v${designContext.version}.
Deprecated props (do not use): ${JSON.stringify(designContext.deprecatedProps)}
`;
```

## Migration tooling: codemods and dual publishing

Breaking changes without mechanical migration burn trust. Ship codemods alongside majors:

```bash
npx @acme/codemod v5-button-variant --path ./src
```

For large ecosystems, **dual-publish** deprecated APIs for one minor cycle:

```tsx
/** @deprecated Use variant="primary" — removed in v6 */
export type ButtonSize = "compact" | "default";

export function Button({ size, variant, ...rest }: ButtonProps) {
  const resolvedVariant =
    variant ?? (size === "compact" ? "primary" : "secondary");
  if (process.env.NODE_ENV !== "production" && size !== undefined) {
    console.warn("Button: `size` is deprecated; use `variant`");
  }
  return <button data-variant={resolvedVariant} {...rest} />;
}
```

Track deprecated usage with build telemetry (opt-in) or ESLint rules (`no-deprecated-design-system-props`) so you know when to cut the major.

## Visual regression as a versioning gate

Unit tests catch logic; **visual regression** catches unintended design drift. Treat Chromatic/Percy baselines as part of the version contract:

- Patch releases must have zero unexpected diffs on stable stories.
- Minor releases document accepted diffs in the PR with designer approval attached.
- Major releases reset baselines intentionally with a labeled "baseline-reset" changeset.

```typescript
// storybook.test.ts — fail CI on unreviewed visual change
test("design system stories match approved baselines", async () => {
  const report = await chromatic.run({
    projectToken: process.env.CHROMATIC_TOKEN,
    onlyChanged: true,
    exitZeroOnChanges: false,
  });
  expect(report.changeCount).toBe(0);
});
```

## Agent-specific pitfalls

Agents amplify versioning mistakes because they compose components creatively:

1. **Schema lag** — Agent tool definitions reference `Modal` props removed two minors ago. Fix: generate tool schemas from Storybook `argTypes` in CI.
2. **Token hallucination** — Model invents `color-brand-450` not in tokens. Fix: validate generated class names against token allowlist before render.
3. **Cross-tenant leakage** — Multi-tenant agent host caches one design context for all tenants. Fix: namespace manifests per tenant/white-label brand.

```typescript
function validateGeneratedClasses(classNames: string[], tokenKeys: Set<string>): string[] {
  const invalid = classNames.filter(
    (c) => c.startsWith("color-") && !tokenKeys.has(c.replace("color-", ""))
  );
  if (invalid.length) throw new ValidationError(`Unknown tokens: ${invalid.join(", ")}`);
  return classNames;
}
```

## Operational ownership

Assign a **design system on-call** rotation separate from product on-call. Alerts worth paging:

- npm publish succeeded but Storybook deploy failed (docs/schema drift).
- Token contrast checker failed on `main` for more than one hour.
- Agent UI validation error rate exceeds 2% of sessions after a design system publish.

Runbooks should include rollback: unpublish is impossible on npm, so yank broken patch releases and publish a revert patch within SLA documented in your versioning policy.

## Governance without committees

Use a lightweight **RFC template** for majors: motivation, migration plan, codemod availability, consumer survey results, accessibility impact statement. Require two consuming-team approvals for majors affecting shared primitives (`Button`, `TextField`, `FocusRing`).

Minor releases can flow through automated changesets if visual and API diff gates pass. This keeps velocity for additive work while majors get scrutiny.

## The takeaway

Design system versioning is platform engineering: semver discipline, independent token versioning, lock manifests for apps and agents, automated Figma-to-code pipelines, and visual regression gates. Teams that treat the design system as "just a component library" get broken agent UIs and fearful quarterly upgrades. Teams that version each layer explicitly ship smaller diffs and recover from bad releases in hours, not sprints.

## FAQ

### Should design system packages follow strict semver for component APIs?

Yes for published npm/Maven packages consumed by multiple teams. Patch for bug fixes and visual tweaks that preserve DOM structure and props. Minor for additive props, new variants, and deprecated-but-still-working APIs. Major only when you remove props, change default behavior, or alter accessibility contracts that downstream tests depend on.

### How do you version a design system when agents generate UI from the same token source?

Pin agents to a specific design-system major version in their system prompt and tool schema. Expose a version manifest (tokens + component API snapshot) the agent reads at session start. Never let an agent pick "latest" at runtime—generation drift is harder to detect than import drift.

### What is the minimum deprecation window before a breaking change?

Two release cycles for internal consumers, one quarter for external SDK users. Pair deprecation with codemods, Storybook migration notes, and CI warnings on deprecated imports. If usage telemetry shows >5% of traffic still on deprecated APIs at window end, extend rather than break.

### How do mobile and web stay on compatible design system versions?

Use a shared token package as the single source of truth and version it independently from platform component libraries. Web and mobile component libs declare compatible token ranges in their package metadata. CI fails if a mobile release requires token features the web release has not adopted yet.

## Resources

- [semver.org](https://semver.org/) — Semantic versioning specification
- [design-tokens.github.io/community-group/format/](https://design-tokens.github.io/community-group/format/) — Design Tokens Format Module
- [storybook.js.org/docs/writing-tests/visual-testing](https://storybook.js.org/docs/writing-tests/visual-testing) — Storybook visual testing
- [github.com/changesets/changesets](https://github.com/changesets/changesets) — Changesets for monorepo versioning
- [www.w3.org/WAI/WCAG22/quickref/](https://www.w3.org/WAI/WCAG22/quickref/) — WCAG 2.2 quick reference for contrast regressions
