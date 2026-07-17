---
title: "AI Agents: Design Tokens Style Dictionary"
slug: "agent-design-tokens-style-dictionary"
description: "Build a Style Dictionary pipeline that transforms design tokens into platform outputs for web, iOS, Android, and agent UI runtimes—with validation, transforms, and CI gates."
datePublished: "2026-06-10"
dateModified: "2026-06-10"
tags: ["AI", "Agent", "Design"]
keywords: "style dictionary, design tokens, token transforms, multi-platform build, Figma tokens, agent UI theming"
faq:
  - q: "Why use Style Dictionary instead of hand-maintaining platform token files?"
    a: "Hand-maintained CSS, Swift, and Kotlin constants diverge within weeks. Style Dictionary applies one canonical JSON/YAML source through transforms and formatters so every platform gets mathematically identical values. You fix a contrast bug once in tokens.json, not three times in platform repos."
  - q: "How should token names be structured for agent-generated UI?"
    a: "Use category-type-item-variant semantics: color-background-surface-default, spacing-inline-md. Agents parse predictable names better than abbreviated designer shorthand. Publish a machine-readable glossary JSON alongside builds so LLM tool schemas can validate token references."
  - q: "What transforms are worth custom-building?"
    a: "Color contrast pairs for accessibility, rem-to-dp scaling for Android, reference resolution for aliased tokens, and dark-mode derivative generation from a single seed palette. Skip custom transforms for simple string passthrough—use built-in name/cti transforms first."
  - q: "How do you catch breaking token changes in CI?"
    a: "Run a diff job that classifies renames, removals, and value shifts against semver rules. Fail builds on removed keys or contrast ratio regressions. Emit a JSON changelog artifact agents and mobile teams consume to know what changed before they bump the package."
---
Designers updated the brand palette in Figma on Monday. By Wednesday, iOS still showed the old primary blue, the marketing site CSS had the new hex values, and agent-generated dashboards referenced `color-brand-primary` that now resolved to a shade two steps darker than legal approved in the accessibility audit. Nobody had a **single build pipeline** turning Figma variables into checked artifacts. Style Dictionary is the workhorse that closes that gap—if you treat token compilation as production infrastructure, not a one-off export script.

## Canonical source: W3C format and references

Store tokens in the [Design Tokens Community Group format](https://design-tokens.github.io/community-group/format/) so Figma plugins, Tokens Studio, and Style Dictionary v4 agree on structure:

```json
{
  "color": {
    "brand": {
      "primary": {
        "$type": "color",
        "$value": "{color.palette.blue.600}",
        "$description": "Primary actions, links"
      }
    },
    "palette": {
      "blue": {
        "600": { "$type": "color", "$value": "#2563eb" }
      }
    }
  },
  "spacing": {
    "inline": {
      "md": { "$type": "dimension", "$value": "16px" }
    }
  }
}
```

References (`{color.palette.blue.600}`) let you retheme by editing palette leaves while semantic tokens stay stable—critical for white-label agent products where tenant brand swaps palette, not component code.

## Style Dictionary config: platforms and build graph

A typical multi-platform `config.js`:

```javascript
import StyleDictionary from "style-dictionary";

const sd = new StyleDictionary({
  source: ["tokens/**/*.json"],
  platforms: {
    css: {
      transformGroup: "css",
      buildPath: "build/css/",
      files: [{ destination: "variables.css", format: "css/variables" }],
    },
    scss: {
      transformGroup: "scss",
      buildPath: "build/scss/",
      files: [{ destination: "_tokens.scss", format: "scss/variables" }],
    },
    ios: {
      transformGroup: "ios-swift",
      buildPath: "build/ios/",
      files: [{ destination: "DesignTokens.swift", format: "ios/swift/class.swift" }],
    },
    android: {
      transformGroup: "android",
      buildPath: "build/android/",
      files: [{ destination: "DesignTokens.kt", format: "android/kotlin" }],
    },
    json: {
      buildPath: "build/json/",
      files: [{ destination: "tokens-flat.json", format: "json/flat" }],
    },
  },
});

await sd.buildAllPlatforms();
```

The flat JSON output is what **agent runtimes** ingest—no platform-specific units, just resolved values and metadata for validation.

## Custom transforms: rem scaling and dark mode

Built-in transforms handle naming; production systems need **domain transforms**:

```javascript
// sd-transforms.js
StyleDictionary.registerTransform({
  name: "size/remToDp",
  type: "value",
  transitive: true,
  filter: (token) => token.$type === "dimension",
  transform: (token) => {
    const px = parseFloat(token.$value);
    return `${Math.round(px * 1)}dp`; // 1px = 1dp baseline; tune per design grid
  },
});

StyleDictionary.registerTransform({
  name: "color/darkModeInvert",
  type: "value",
  filter: (token) => token.path[0] === "color" && token.path.includes("surface"),
  transform: (token, config) => {
    if (!config.useDarkMode) return token.$value;
    // resolve and apply curated dark surface map, not naive invert
    return darkSurfaceMap[token.name] ?? token.$value;
  },
});
```

Generate dark tokens as a second build pass with `useDarkMode: true` rather than maintaining duplicate JSON—single source, derived outputs.

## Token validation before build

Catch designer mistakes before they reach mobile binaries:

```javascript
import Ajv from "ajv";
import contrast from "wcag-contrast";

function validateTokens(tokens) {
  const ajv = new Ajv();
  const schema = { /* DTCG subset + your org extensions */ };
  if (!ajv.validate(schema, tokens)) throw new Error(ajv.errorsText());

  const pairs = [
    ["color.text.primary", "color.background.surface.default"],
    ["color.text.inverse", "color.background.brand.primary"],
  ];
  for (const [fg, bg] of pairs) {
    const ratio = contrast(getColor(tokens, fg), getColor(tokens, bg));
    if (ratio < 4.5) {
      throw new Error(`Contrast fail ${fg} on ${bg}: ${ratio.toFixed(2)}`);
    }
  }
}
```

Wire `validateTokens` into `prebuild` so CI fails when a well-meaning saturation bump breaks WCAG AA.

## Agent integration: flat glossary and tool schemas

Agents should not guess token names. Publish `tokens-glossary.json`:

```json
{
  "version": "2.4.1",
  "tokens": {
    "color.background.surface.default": {
      "value": "#ffffff",
      "type": "color",
      "usage": "Page and card backgrounds",
      "platforms": ["web", "ios", "android", "agent"]
    }
  }
}
```

Generate OpenAI/Anthropic tool parameter enums from keys:

```typescript
function buildThemeToolSchema(glossary: TokenGlossary) {
  const backgroundColors = Object.keys(glossary.tokens).filter((k) =>
    k.startsWith("color.background.")
  );
  return {
    name: "set_panel_theme",
    parameters: {
      type: "object",
      properties: {
        background: { type: "string", enum: backgroundColors },
      },
      required: ["background"],
    },
  };
}
```

When the model proposes `color.background.surface.defalt` (typo), schema validation rejects before render.

## Figma → tokens sync pipeline

Automate the designer-to-engineer handoff:

```yaml
# tokens-sync.yml
jobs:
  pull-figma:
    steps:
      - run: npx @tokens-studio/figma-export --output tokens/figma-raw.json
      - run: node scripts/normalize-figma-to-dtcg.js
      - run: node scripts/merge-with-core-tokens.js  # preserve semantic layer
      - run: npm run tokens:validate
      - run: npm run tokens:build
      - run: node scripts/token-changelog.js --semver-check
```

`token-changelog.js` diffs previous `build/json/tokens-flat.json` against new output:

```javascript
const diff = tokenDiff(previousFlat, nextFlat);
if (diff.removed.length) {
  console.error("BREAKING: removed tokens", diff.removed);
  process.exit(1);
}
if (diff.contrastRegressions.length) {
  console.error("BREAKING: contrast regressions", diff.contrastRegressions);
  process.exit(1);
}
writeFileSync("TOKEN_CHANGELOG.json", JSON.stringify(diff, null, 2));
```

Mobile and agent teams subscribe to `TOKEN_CHANGELOG.json` in their bump PRs.

## Monorepo packaging and consumption

Publish tokens as an npm package with platform entry points:

```json
{
  "name": "@acme/design-tokens",
  "version": "2.4.1",
  "exports": {
    "./css": "./build/css/variables.css",
    "./scss": "./build/scss/_tokens.scss",
    "./json": "./build/json/tokens-flat.json",
    "./glossary": "./build/json/tokens-glossary.json"
  },
  "files": ["build/**"]
}
```

Web apps import CSS; agents fetch JSON at startup; iOS/Android consume artifacts via CocoaPods/Maven internal mirrors refreshed on publish webhooks.

## Performance and cacheability

Full rebuilds on every commit waste CI minutes. Hash inputs and cache builds:

```javascript
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";

function tokensInputHash(globPaths) {
  const h = createHash("sha256");
  for (const file of globPaths.sort()) {
    h.update(readFileSync(file));
  }
  return h.digest("hex");
}
```

Skip `buildAllPlatforms` when hash matches `.tokens-build-cache`—but always rebuild on `main` merges to avoid stale artifacts.

## Multi-brand and tenant theming for agents

SaaS agents often need per-tenant themes without separate npm packages. Build **theme overlays**:

```json
{
  "extends": "@acme/design-tokens/json",
  "overrides": {
    "color.brand.primary": { "$value": "#e11d48" }
  }
}
```

Runtime merge:

```typescript
function resolveTheme(base: TokenMap, overlay: TokenMap): TokenMap {
  return deepMerge(structuredClone(base), overlay);
}
```

Cache resolved themes by `(tenantId, tokensVersion)` in Redis with TTL aligned to token publish events.

## Testing strategy

- **Snapshot tests** on generated CSS custom properties for stable releases.
- **Property tests** that every semantic color resolves to a hex matching regex `^#[0-9a-f]{6}$`.
- **Cross-platform parity** job comparing web computed style against iOS/Android golden files for a fixed set of tokens.
- **Agent contract tests** feeding intentionally invalid token names to tool handlers expecting structured errors.

## Common failures I have seen

1. **Transform order bugs** — `size/rem` runs before reference resolution, producing `NaNrem`. Document transform groups explicitly.
2. **Figma raw names** — Exporting `Primary/Blue/600` without normalization breaks CTI transforms. Normalize in `normalize-figma-to-dtcg.js`.
3. **Silent float drift** — iOS uses CGFloat rounding differently than CSS subpixel rendering. Accept documented epsilon in parity tests.
4. **Agent stale cache** — Host loads tokens once per process lifetime; publish webhook must invalidate agent worker pools.

## The takeaway

Style Dictionary turns design tokens into a compiled artifact with the same rigor as application code: validated inputs, custom transforms, semver-aware diffs, and platform outputs consumed by web, mobile, and agent runtimes alike. Invest in the pipeline once; stop reconciling three sources of truth every brand refresh.

## FAQ

### Why use Style Dictionary instead of hand-maintaining platform token files?

Hand-maintained CSS, Swift, and Kotlin constants diverge within weeks. Style Dictionary applies one canonical JSON/YAML source through transforms and formatters so every platform gets mathematically identical values. You fix a contrast bug once in tokens.json, not three times in platform repos.

### How should token names be structured for agent-generated UI?

Use category-type-item-variant semantics: color-background-surface-default, spacing-inline-md. Agents parse predictable names better than abbreviated designer shorthand. Publish a machine-readable glossary JSON alongside builds so LLM tool schemas can validate token references.

### What transforms are worth custom-building?

Color contrast pairs for accessibility, rem-to-dp scaling for Android, reference resolution for aliased tokens, and dark-mode derivative generation from a single seed palette. Skip custom transforms for simple string passthrough—use built-in name/cti transforms first.

### How do you catch breaking token changes in CI?

Run a diff job that classifies renames, removals, and value shifts against semver rules. Fail builds on removed keys or contrast ratio regressions. Emit a JSON changelog artifact agents and mobile teams consume to know what changed before they bump the package.

## Resources

- [amzn.github.io/style-dictionary](https://amzn.github.io/style-dictionary/) — Style Dictionary documentation
- [design-tokens.github.io/community-group/format/](https://design-tokens.github.io/community-group/format/) — W3C Design Tokens format
- [docs.tokens.studio](https://docs.tokens.studio/) — Tokens Studio for Figma sync
- [github.com/tokens-studio/figma-plugin](https://github.com/tokens-studio/figma-plugin) — Figma Tokens Studio plugin
- [www.npmjs.com/package/wcag-contrast](https://www.npmjs.com/package/wcag-contrast) — WCAG contrast ratio library for CI validation
