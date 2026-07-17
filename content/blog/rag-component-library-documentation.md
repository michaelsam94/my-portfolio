---
title: "RAG: Component Library Documentation"
slug: "rag-component-library-documentation"
description: "Document RAG UI component libraries with Storybook—streaming response renderers, citation blocks, source preview cards, and retrieval status indicators with live props and accessibility notes."
datePublished: "2026-06-11"
dateModified: "2026-07-17"
tags: ["AI", "Rag", "Component"]
keywords: "component library, Storybook, RAG UI, design system, citation component, streaming text, documentation, React components"
faq:
  - q: "What RAG-specific components need documentation beyond standard design systems?"
    a: "RAG products have unique UI patterns: streaming markdown response renderers, citation/source attribution blocks, retrieved chunk preview cards, confidence indicators, retrieval loading states, and query input with suggestion chips. Standard button and form docs don't cover these— they need dedicated stories with realistic RAG data fixtures."
  - q: "How should Storybook document streaming response components?"
    a: "Use play functions and args to simulate streaming token arrival—show partial response, mid-stream, and complete states. Document aria-live behavior for screen readers. Include stories for markdown edge cases: code blocks, tables, and inline citations that RAG responses commonly contain."
  - q: "What accessibility documentation belongs in RAG component stories?"
    a: "Document APCA contrast values for each theme variant, aria-live region configuration for streaming text, keyboard navigation for citation links, and focus management when new retrieval results append. Include axe-core automated checks in Storybook test runner for every story."
---
Engineers kept reimplementing citation blocks slightly differently in every RAG feature—margin off by 2px, source link color not matching dark mode, streaming cursor behavior inconsistent. The component library had Button, Input, and Modal documented in Storybook. It did not have CitationBlock, StreamingResponse, or RetrievalStatus. Six months of UI inconsistency ended when RAG-specific components got first-class Storybook documentation with realistic fixtures, interaction tests, and accessibility notes baked into every story.

Component library documentation for RAG products must cover retrieval-specific UI patterns that generic design systems omit. Storybook is the standard vehicle—stories become living documentation, visual regression baselines, and accessibility test fixtures.

## RAG component inventory

Components unique to or heavily customized for RAG interfaces:

| Component | Variants to document |
|-----------|---------------------|
| `StreamingResponse` | Empty, streaming, complete, error |
| `CitationBlock` | Single source, multi-source, collapsed |
| `SourcePreviewCard` | With snippet, without snippet, unavailable |
| `RetrievalStatus` | Searching, found N sources, no results, failed |
| `QueryInput` | Default, with suggestions, with history |
| `ConfidenceBadge` | High, medium, low, unknown |
| `MarkdownRenderer` | Code, tables, lists, inline citations |
| `ChunkHighlight` | Relevant passage highlighted in source |
| `FeedbackWidget` | Thumbs up/down on response quality |

Each needs stories for light/dark theme and mobile viewport.

## Storybook story structure for RAG components

```tsx
// components/CitationBlock/CitationBlock.stories.tsx
import type { Meta, StoryObj } from "@storybook/react";
import { CitationBlock } from "./CitationBlock";
import { ragFixtures } from "../../fixtures/rag";

const meta: Meta<typeof CitationBlock> = {
  title: "RAG/CitationBlock",
  component: CitationBlock,
  parameters: {
    layout: "padded",
    docs: {
      description: {
        component:
          "Displays retrieved source attribution for RAG response chunks. " +
          "Meets APCA Lc 60+ for citation text. Supports keyboard navigation.",
      },
    },
  },
  tags: ["autodocs"],
  argTypes: {
    source: { description: "Retrieved document source metadata" },
    snippet: { description: "Relevant chunk excerpt" },
    collapsed: { control: "boolean" },
  },
};

export default meta;
type Story = StoryObj<typeof CitationBlock>;

export const SingleSource: Story = {
  args: {
    source: ragFixtures.sources[0],
    snippet: ragFixtures.snippets.refundPolicy,
    collapsed: false,
  },
};

export const MultipleSources: Story = {
  args: {
    sources: ragFixtures.sources.slice(0, 3),
    collapsed: true,
  },
};

export const DarkMode: Story = {
  args: SingleSource.args,
  parameters: { backgrounds: { default: "dark" } },
  decorators: [(Story) => <div className="dark"><Story /></div>],
};
```

## Realistic RAG fixtures

Centralize test data reflecting production RAG output:

```typescript
// fixtures/rag.ts
export const ragFixtures = {
  sources: [
    {
      id: "doc-refund-policy-v3",
      title: "Refund Policy — Updated March 2026",
      url: "https://docs.example.com/refund-policy",
      corpusVersion: "v47",
      confidence: 0.92,
    },
    {
      id: "doc-shipping-faq",
      title: "Shipping FAQ",
      url: "https://docs.example.com/shipping",
      corpusVersion: "v47",
      confidence: 0.78,
    },
  ],
  snippets: {
    refundPolicy:
      "Customers may request a full refund within 30 days of purchase. " +
      "Digital products are eligible if not yet downloaded.",
    shipping:
      "Standard shipping takes 5–7 business days. Express shipping available.",
  },
  streamingResponse: {
    partial: "Based on our refund policy, you can request a ",
    complete:
      "Based on our refund policy, you can request a full refund within " +
      "30 days of purchase for digital products not yet downloaded.",
  },
  retrievalStates: {
    searching: { status: "searching" as const, query: "refund policy" },
    found: { status: "found" as const, count: 3, query: "refund policy" },
    empty: { status: "empty" as const, query: "xyzzy nonsense query" },
    error: { status: "error" as const, message: "Retrieval service unavailable" },
  },
};
```

Fixtures evolve with corpus—version fixture file when response format changes.

## Streaming response stories with play functions

Simulate token-by-token arrival:

```tsx
// components/StreamingResponse/StreamingResponse.stories.tsx
export const StreamingAnimation: Story = {
  args: { text: "", isStreaming: true },
  play: async ({ canvasElement, args }) => {
    const tokens = ragFixtures.streamingResponse.complete.split(" ");
    const canvas = within(canvasElement);

    for (const token of tokens) {
      args.text += token + " ";
      args.isStreaming = true;
      await new Promise((r) => setTimeout(r, 100));
    }
    args.isStreaming = false;
  },
};

export const StreamingComplete: Story = {
  args: {
    text: ragFixtures.streamingResponse.complete,
    isStreaming: false,
    citations: ragFixtures.sources.slice(0, 2),
  },
};
```

Document expected aria-live behavior in story description:

```tsx
parameters: {
  docs: {
    description: {
      story:
        "During streaming, aria-live='polite' announces new content to screen readers. " +
        "Complete state moves citations into focusable region.",
    },
  },
},
```

## Accessibility documentation in stories

Embed contrast and a11y info in docs:

```tsx
// components/CitationBlock/CitationBlock.a11y.stories.tsx
export const AccessibilityNotes: Story = {
  parameters: {
    docs: {
      description: {
        story: `
**Contrast (APCA):**
- Citation text on light bg: Lc 78 ✓
- Citation text on dark bg: Lc 82 ✓

**Keyboard:**
- Tab to source link
- Enter opens source in new tab

**Screen reader:**
- Source announced as "Source 1 of 2: Refund Policy"
        `,
      },
    },
  },
  args: SingleSource.args,
};
```

Automated axe checks in test runner:

```tsx
// .storybook/test-runner.ts
import { injectAxe, checkA11y } from "axe-playwright";

export async function preVisit(page) {
  await injectAxe(page);
}

export async function postVisit(page, context) {
  await checkA11y(page, "#storybook-root", {
    detailedReport: true,
  });
}
```

## MDX documentation pages

Long-form component docs alongside stories:

```mdx
{/* components/CitationBlock/CitationBlock.mdx */}
import { Meta, Story, Canvas, Controls } from "@storybook/blocks";
import * as CitationBlockStories from "./CitationBlock.stories";

<Meta of={CitationBlockStories} />

# CitationBlock

Displays retrieved source attribution in RAG responses.

## Usage

\`\`\`tsx
<CitationBlock
  source={retrievedSource}
  snippet={chunkText}
  onSourceClick={(url) => window.open(url)}
/>
\`\`\`

## When to use

- Always show citations when RAG response includes retrieved context
- Collapse to count badge when >3 sources

## Do not

- Hide citations behind hover (accessibility)
- Use color alone to indicate source confidence

<Canvas of={CitationBlockStories.SingleSource} />
<Controls of={CitationBlockStories.SingleSource} />
```

## Visual regression with Chromatic

RAG components have many theme/state combinations—automate visual diff:

```yaml
# chromatic.config.json
{
  "projectToken": "chroma_xxx",
  "buildScriptName": "build-storybook",
  "onlyChanged": true,
  "externals": ["public/**"]
}
```

CI on every PR:

```yaml
- name: Publish to Chromatic
  run: npx chromatic --exit-zero-on-changes
```

Catches citation block dark mode regression before merge.

## Component API consistency

Document standard props across RAG components:

```typescript
// types/rag-component-props.ts
interface RAGComponentBase {
  /** Theme variant */
  variant?: "light" | "dark" | "auto";
  /** Corpus version for debugging display */
  corpusVersion?: string;
  /** Test ID for e2e */
  "data-testid"?: string;
}

interface CitationBlockProps extends RAGComponentBase {
  source: RetrievedSource;
  snippet?: string;
  collapsed?: boolean;
  onSourceClick?: (url: string) => void;
}
```

Consistent API patterns reduce documentation burden—once `variant` is documented for one component, others follow.

## Contribution guidelines

Document how to add new RAG components:

1. Create component in `components/RAG/`
2. Add fixtures to `fixtures/rag.ts`
3. Write stories: default, variants, dark mode, mobile, a11y
4. Add MDX page with usage guidelines
5. Verify axe checks pass
6. Submit Chromatic review

PR template checklist:

```markdown
- [ ] Storybook stories for all variants
- [ ] Realistic RAG fixtures (not lorem ipsum)
- [ ] Dark mode story
- [ ] Accessibility notes in docs
- [ ] axe checks pass
- [ ] Chromatic review approved
```

## Keeping docs current with RAG pipeline changes

RAG response format evolves—citation structure adds fields, streaming protocol changes. Documentation drift causes UI bugs:

- **Fixture versioning:** `ragFixtures v2` when API response schema changes
- **Storybook CI:** build Storybook on every PR, fail on TypeScript errors in stories
- **Link to API schema:** document which corpus/response version fixtures represent
- **Quarterly review:** design + engineering audit stories against production UI

Component library documentation is the contract between RAG backend response format and frontend rendering. Invest in RAG-specific stories—not just generic design tokens—to keep retrieval UI consistent and accessible.

## Design-dev handoff with Storybook links

Link Storybook URLs in Figma component descriptions and Jira tickets. Designers reference specific story URLs when specifying RAG UI behavior; engineers implement against the same story. Reduces "that's not what I meant" rework on citation block layouts. Publish Storybook to static hosting on every main branch merge—product and support teams use it as UI reference without local dev setup.

## Versioning component library with RAG API schema

When RAG API response schema increments (new citation fields, confidence format change), release component library minor version with updated prop types. Document breaking changes in Storybook changelog page. Consumers (frontend apps) pin component library version aligned with RAG API version they target—version mismatch causes rendering bugs for new citation metadata fields. Semantic versioning: patch for visual fixes, minor for new optional props, major for breaking prop changes.

## Resources

- Storybook autodocs and MDX documentation
- Storybook test runner with axe-playwright
- Chromatic visual regression for Storybook
- Inclusive Components by Heydon Pickering
