---
title: "Component Library Documentation Agents Can Actually Use"
slug: "agent-component-library-documentation"
description: "Document design-system components for human and agent consumers: Storybook MDX, prop schemas, usage constraints, MCP tool surfaces, and CI drift detection."
datePublished: "2026-06-12"
dateModified: "2026-06-12"
tags: ["Design Systems", "Documentation", "AI Agents", "Storybook"]
keywords: "component library documentation, Storybook agent integration, design system docs, component prop schema, agent UI generation"
faq:
  - q: "Why do agents need different component documentation than human developers?"
    a: "Agents do not browse Storybook visually — they consume structured text: prop types, allowed enum values, composition rules, and anti-patterns. Docs must be machine-parseable JSON Schema or TypeScript AST exports alongside human MDX. Missing 'do not nest X inside Y' constraints cause agents to generate invalid trees that type-check but break layout or a11y."
  - q: "Should component docs live in Storybook, a separate portal, or repo markdown?"
    a: "Storybook remains the source for live examples and visual states. Export a parallel `docs/api/` JSON bundle from the same source files for agents and IDE plugins. CI builds both; drift between them fails the pipeline. Avoid duplicate hand-written markdown that diverges from props."
  - q: "How do you expose component libraries to coding agents via MCP?"
    a: "Publish an MCP tool server that lists components, returns prop schemas, validates JSX snippets against composition rules, and links to Storybook story IDs. Agents call `list_components`, `get_component_spec`, and `validate_tree` before emitting UI code. Cache specs — they change less often than LLM context windows shift."
  - q: "What metadata reduces agent-generated UI bugs the most?"
    a: "Required vs optional props, default values, slot/children constraints, responsive breakpoints, accessibility roles, and paired components (Dialog requires DialogHeader). Rank constraints by failure frequency from production bug tickets — document those first in `agentHints` blocks."
---

Coding agents that build dashboards and internal tools from your design system will hallucinate props, invent variant names, and nest components in ways that break layout — unless documentation is structured for **machine consumption** as well as humans. A beautiful Storybook with screenshot-only pages helps designers; agents need typed contracts, composition grammars, and validation tools that reject invalid trees before merge.

The goal is a single source of truth that renders human docs, exports agent-readable specs, and gates CI when either drifts from component source.

## Documentation layers

Think in four layers, each generated from code where possible:

```
Layer 1: Source (React/Vue/Svelte components + TypeScript props)
    ↓
Layer 2: Human docs (Storybook MDX, descriptions, do/don't)
    ↓
Layer 3: Agent spec bundle (JSON Schema per component + composition rules)
    ↓
Layer 4: Runtime validation (MCP tools, ESLint rules, snapshot tests)
```

Layer 3 is what most design systems lack. Adding it transforms agent output from guesswork to constrained synthesis.

## Storybook as human layer

Keep interactive examples in Storybook 8+ with autodocs from prop types:

```tsx
// Button.stories.tsx
import type { Meta, StoryObj } from "@storybook/react";
import { Button } from "./Button";

const meta: Meta<typeof Button> = {
  title: "Components/Button",
  component: Button,
  tags: ["autodocs"],
  parameters: {
    docs: {
      description: {
        component:
          "Primary action control. Use `variant=\"primary\"` for one main action per surface. Do not stack more than two primary buttons.",
      },
    },
  },
  argTypes: {
    variant: {
      control: "select",
      options: ["primary", "secondary", "ghost", "danger"],
    },
    size: { control: "select", options: ["sm", "md", "lg"] },
  },
};
export default meta;
type Story = StoryObj<typeof Button>;

export const Primary: Story = { args: { variant: "primary", children: "Save" } };
export const Danger: Story = { args: { variant: "danger", children: "Delete" } };
```

MDX for narrative constraints agents cannot infer from types alone:

```mdx
{/* Button.mdx */}
import { Meta, Canvas } from "@storybook/blocks";
import * as Stories from "./Button.stories";

<Meta of={Stories} />

## Agent hints

- Maximum one `variant="primary"` per `<Card>` or `<Dialog>`.
- Never use `danger` without confirmation dialog parent.
- `disabled` buttons must include `aria-disabled` — handled by component; do not wrap in `<a>`.
```

The `## Agent hints` section is extracted at build time into the spec bundle (see below).

## Agent spec bundle generation

Export machine-readable specs from TypeScript using `react-docgen-typescript` or `ts-morph`:

```typescript
// scripts/build-component-spec.ts
import docgen from "react-docgen-typescript";
import fs from "fs";
import path from "path";
import { parseAgentHints } from "./parse-agent-hints";

const parser = docgen.withCustomConfig("./tsconfig.json", {
  propFilter: (prop) => !prop.parent?.fileName.includes("node_modules"),
});

const componentsDir = "./src/components";
const out: Record<string, ComponentSpec> = {};

for (const file of fs.readdirSync(componentsDir)) {
  if (!file.endsWith(".tsx")) continue;
  const filePath = path.join(componentsDir, file);
  const docs = parser.parse(filePath);
  const exportName = docs[0].displayName;

  out[exportName] = {
    description: docs[0].description,
    props: Object.fromEntries(
      Object.entries(docs[0].props).map(([name, p]) => [
        name,
        {
          type: p.type.name,
          required: p.required,
          defaultValue: p.defaultValue?.value ?? null,
          description: p.description,
        },
      ])
    ),
    agentHints: parseAgentHints(filePath.replace(".tsx", ".mdx")),
    stories: listStoryIds(exportName),
  };
}

fs.writeFileSync("./docs/api/components.json", JSON.stringify(out, null, 2));
```

Example output fragment:

```json
{
  "Button": {
    "description": "Primary action control.",
    "props": {
      "variant": {
        "type": "enum",
        "required": false,
        "defaultValue": "secondary",
        "enum": ["primary", "secondary", "ghost", "danger"]
      },
      "size": {
        "type": "enum",
        "required": false,
        "defaultValue": "md",
        "enum": ["sm", "md", "lg"]
      },
      "children": { "type": "ReactNode", "required": true }
    },
    "agentHints": [
      "Maximum one variant=primary per Card or Dialog",
      "Never use danger without confirmation dialog parent"
    ],
    "stories": ["Components/Button/Primary", "Components/Button/Danger"]
  }
}
```

Commit `components.json` or publish as npm package `@corp/design-system-spec`.

## Composition rules as a grammar

Prop types alone miss parent-child legality. Define explicit composition rules:

```typescript
// docs/api/composition-rules.ts
export const compositionRules: CompositionRule[] = [
  {
    parent: "Dialog",
    requiredChildren: ["DialogHeader", "DialogBody"],
    optionalChildren: ["DialogFooter"],
    forbiddenChildren: ["Dialog"],
  },
  {
    parent: "Card",
    maxChildren: { component: "Button", props: { variant: "primary" }, count: 1 },
  },
  {
    parent: "FormField",
    requiredChildren: ["Label"],
    acceptsTextInput: true,
  },
];

export function validateTree(node: UiNode): ValidationError[] {
  const errors: ValidationError[] = [];
  const rule = compositionRules.find((r) => r.parent === node.type);
  if (!rule) return errors;

  for (const req of rule.requiredChildren ?? []) {
    if (!node.children?.some((c) => c.type === req)) {
      errors.push({ code: "MISSING_CHILD", message: `${node.type} requires ${req}` });
    }
  }
  // ... maxChildren, forbiddenChildren
  return errors;
}
```

Agents call `validate_tree` before returning JSX. Humans get the same rules via ESLint custom plugin in IDE.

## MCP tool surface for agents

Expose design system docs through MCP so Cursor and other agents fetch authoritative specs:

```typescript
// mcp-design-system/server.ts
import { Server } from "@modelcontextprotocol/sdk/server";
import spec from "../docs/api/components.json";
import { validateTree } from "../docs/api/composition-rules";

const server = new Server({ name: "design-system", version: "1.0.0" });

server.tool("list_components", {}, async () => ({
  content: [{ type: "text", text: JSON.stringify(Object.keys(spec)) }],
}));

server.tool("get_component_spec", { component: { type: "string" } }, async ({ component }) => {
  const entry = spec[component];
  if (!entry) throw new Error(`Unknown component: ${component}`);
  return { content: [{ type: "text", text: JSON.stringify(entry, null, 2) }] };
});

server.tool("validate_tree", { tree: { type: "object" } }, async ({ tree }) => {
  const errors = validateTree(tree as UiNode);
  return {
    content: [{
      type: "text",
      text: errors.length ? JSON.stringify(errors) : "valid",
    }],
  };
});
```

Cursor rule snippet for teams:

```
Before generating UI with @corp/design-system:
1. Call get_component_spec for each component used.
2. Call validate_tree on the proposed JSX AST.
3. Do not use props not listed in spec.
4. Apply all agentHints verbatim.
```

## CI drift detection

Pipeline stages:

```yaml
jobs:
  docs-sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npm ci
      - run: npm run build:component-spec
      - run: git diff --exit-code docs/api/components.json
      - run: npm run storybook:build
      - run: npm run test:composition-rules
```

Failing `git diff` on `components.json` forces engineers to regenerate specs when props change — agents never read stale `variant` enums.

Add snapshot tests for each Storybook story's default args — catches visual/API drift:

```typescript
import { composeStories } from "@storybook/react";
import * as ButtonStories from "./Button.stories";

const { Primary } = composeStories(ButtonStories);

test("Primary story args match spec defaults", () => {
  const spec = require("../../docs/api/components.json").Button;
  expect(Primary.args.variant).toBe(spec.props.variant.defaultValue ?? "secondary");
});
```

## Writing effective agent hints

Prioritize hints from production failure modes:

| Bug pattern | Agent hint |
|-------------|------------|
| Double primary CTA | Max one primary button per surface |
| Modal without focus trap | Dialog must include DialogHeader |
| Icon-only button no label | IconButton requires `aria-label` |
| Table horizontal scroll on mobile | DataTable needs `responsive=\"stack\"` below md breakpoint |

Format hints as imperative, testable statements — not prose paragraphs. Limit to 5–7 per component; link to MDX for edge cases.

Anti-pattern documentation matters as much as happy paths:

```json
{
  "Button": {
    "antiPatterns": [
      { "pattern": "<Button><Link href=\"/x\">", "reason": "Use LinkButton instead for navigation" },
      { "pattern": "variant=\"primary\" size=\"sm\" for destructive", "reason": "Use danger variant" }
    ]
  }
}
```

## Versioning and changelog for agents

When design system ships breaking prop renames, agents trained on old specs generate broken code. Publish semver with machine-readable changelog:

```json
{
  "version": "4.2.0",
  "breaking": [],
  "deprecated": [
    { "component": "Button", "prop": "kind", "replacement": "variant", "removeIn": "5.0.0" }
  ]
}
```

MCP tool `get_changelog(since_version)` lets agents upgrade generated code during refactors.

## Measuring documentation quality

Track agent-specific metrics:

- **Spec fetch rate**: MCP `get_component_spec` calls per agent session
- **Validation failure rate**: `validate_tree` errors / generations
- **Post-merge fix rate**: PRs tagged `agent-generated` needing follow-up commits
- **Undocumented prop usage**: ESLint rule catching props absent from spec

Drop components with high validation failure rates into doc sprint queue — usually missing hints or wrong enum export.

## Human docs still matter

Agents do not replace Storybook for design review. Keep:

- Visual regression via Chromatic or Percy
- Accessibility manual notes on complex organisms
- Figma code connect links in MDX

The spec bundle supplements; it does not delete designer-facing narrative.

## The takeaway

Component library documentation for the agent era is a build artifact: TypeScript props → JSON spec + composition grammar + MCP tools + CI drift gates. Invest once in extraction pipelines; every agent session thereafter reads the same contracts humans see in Storybook. Undocumented constraints become `agentHints`; repeated agent failures become new rules in `validate_tree`.

## Resources

- [Storybook autodocs](https://storybook.js.org/docs/writing-docs/autodocs)
- [react-docgen-typescript](https://github.com/styleguidist/react-docgen-typescript)
- [Model Context Protocol specification](https://modelcontextprotocol.io/)
- [Adobe Spectrum — documenting for API consumers](https://spectrum.adobe.com/page/design-system-documentation/)
- [ESLint custom rules for design system enforcement](https://eslint.org/docs/latest/extend/custom-rules)
