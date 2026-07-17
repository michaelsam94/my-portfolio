# Part 1: slugs from b11g_12.txt (1-10)
BODIES_PART1 = {
"testing-contract-testing-microservices": {
    "title": "Contract Testing Microservices",
    "seoTitle": "Contract Testing for Microservices: Pact, Consumer-Driven Contracts, and CI Gates",
    "description": "Consumer-driven contract testing with Pact catches breaking API changes before deploy — provider verification, broker gates, message pacts, and when integration tests still matter.",
    "datePublished": "2025-12-22",
    "tags": ["Testing", "Microservices", "CI/CD", "Architecture"],
    "keywords": "contract testing microservices, Pact consumer driven contracts, provider verification, API contract testing, breaking change detection",
    "faq": [
        {"q": "What is contract testing?", "a": "Contract testing verifies that a service provider and consumer agree on request/response shape without running both services together. Consumer-driven contracts mean consumers define expected interactions; providers prove compliance in CI."},
        {"q": "How is contract testing different from integration testing?", "a": "Integration tests run consumer and provider in a shared environment — slow and flaky at scale. Contract tests run in isolation: consumers generate pact files; providers replay those requests against real handler code."},
        {"q": "When should you adopt Pact?", "a": "Adopt when multiple teams publish internal APIs, integration suites are slow or environment-contended, and breaking changes have caused production incidents. Skip for monoliths or fewer than three cross-service dependencies."},
    ],
    "body": r'''The orders service deployed a rename from `customerId` to `customer_id`. The notification service parsed JSON with strict keys. Production was quiet for four hours until a batch job fired and every email failed. Integration tests missed it because staging mocked notifications. A consumer-driven contract test would have failed the orders PR when provider verification ran.

Contract testing is not about replacing unit tests or E2E. It is about the API surface two teams share — tested fast, in isolation, on every commit.

## Why integration suites stop scaling

At ten microservices, pairwise integration tests seem manageable. At forty, the combinatorics explode. Every consumer needs every provider running — or a stub that drifts from reality. Stubs lie; pacts do not.

| Symptom | Root cause | Contract testing response |
|---|---|---|
| Staging-only failures | Environment drift | Verify against provider code, not mocks |
| Friday deploy fear | Unknown blast radius | `can-i-deploy` gate before prod |
| Silent field renames | No consumer in CI loop | Consumer pact fails provider verification |
| Flaky cross-service tests | Shared DB contention | Isolated provider verification job |

The goal is not 100% coverage of service interactions. Cover the **contract surface** — paths, status codes, headers, body schema — that has historically broken.

## Consumer-driven flow

```
1. Consumer test defines expected interaction → generates pact JSON
2. Pact published to broker (Pactflow, self-hosted)
3. Provider CI pulls consumer pacts → verification against provider codebase
4. Broker marks compatibility; can-i-deploy gate before production
```

Consumer owns expectations. Provider proves compliance. This inversion matters politically: the team that feels API pain writes the test.

## Pact consumer example (JavaScript)

```javascript
import { PactV3, Matchers } from "@pact-foundation/pact";

const { like, eachLike } = Matchers;
const provider = new PactV3({
  consumer: "NotificationService",
  provider: "OrdersService",
});

describe("GET /orders/:id", () => {
  it("returns order for notification", async () => {
    await provider
      .given("order 42 exists")
      .uponReceiving("a request for order 42")
      .withRequest({
        method: "GET",
        path: "/orders/42",
        headers: { Accept: "application/json" },
      })
      .willRespondWith({
        status: 200,
        headers: { "Content-Type": "application/json" },
        body: {
          id: like(42),
          customer_id: like("cust_abc"),
          status: like("shipped"),
          line_items: eachLike({ sku: like("SKU-1"), qty: like(1) }),
        },
      })
      .executeTest(async (mockServer) => {
        const order = await fetchOrder(mockServer.url, 42);
        expect(order.customer_id).toBeDefined();
      });
  });
});
```

Matchers (`like`, `eachLike`, `regex`) express schema intent without brittle exact values. The generated pact file captures what the notification service actually needs — not every field orders exposes.

## Provider verification

Provider tests replay consumer pacts against the real routing layer — Express app, FastAPI router, Spring `@RestController` — not a hand-written mock.

```python
# pytest + pact-python verifier
from pact import Verifier

def test_orders_honors_notification_pacts():
    verifier = Verifier("OrdersService", host_name="localhost", port=8080)
    verifier.verify_pacts(
        "https://broker.example.com/pacts/provider/OrdersService/latest",
        provider_states_setup_endpoint="http://localhost:8080/_pact/provider-states",
    )
```

**Provider states** seed data preconditions: `"order 42 exists"`. Without them, verification passes vacuously or fails on missing fixtures. Invest in a shared seed API used by both integration tests and pact verification — duplicating seed logic guarantees drift.

## Broker workflow and can-i-deploy

```
Consumer PR  → consumer tests → publish pact (dev version)
Provider PR  → verify pacts    → broker marks compatible/incompatible
Release      → can-i-deploy?  → block if incompatible matrix
```

Wire `can-i-deploy` for **both** sides. A consumer cannot ship expecting a field the provider removed. A provider cannot ship removing a field consumers still require.

Version tagging matters: tag pacts with git SHA or semver. "Latest" alone loses traceability when debugging which consumer broke which deploy.

## Message pacts for async boundaries

HTTP pacts cover REST. Kafka and SQS need **message pacts**: consumers define expected payload shape; providers verify published messages match.

```json
{
  "consumer": "AnalyticsService",
  "provider": "OrdersService",
  "messages": [{
    "description": "order completed event",
    "metadata": { "contentType": "application/json" },
    "contents": {
      "event_type": "order.completed",
      "order_id": "ord_123",
      "customer_id": "cust_abc",
      "total_cents": 4999
    }
  }]
}
```

Message pacts verify structure, not ordering or delivery guarantees. Pair with targeted integration tests for ordering-sensitive flows (payment before shipment).

## Contract vs integration vs E2E

| Layer | Proves | Cost | When |
|---|---|---|---|
| Unit | Function logic | ms | Always |
| Contract | API shape agreement | seconds | Every cross-service boundary |
| Integration | Services + real DB together | minutes | Critical paths, 5–10 flows |
| E2E | Full user journey | tens of minutes | Smoke on release |

Contract tests sit in the gap integration tests fill poorly: **many service pairs, fast feedback, no shared staging contention**.

## Organizational patterns that work

**One pact per consumer-provider pair**, not one mega-pact per service. Smaller pacts merge cleanly in the broker matrix.

**Provider verification on main**, not only on release branches. Late discovery wastes a sprint.

**Breaking change process**: deprecate field → dual-publish both names → consumer migrates → provider removes old field across two deploy windows. Pact enforces the sequence.

**Dashboard the matrix**. Red cells are living documentation. When someone asks "what breaks if we rename `status`?", verification history answers — not a stale wiki page.

## When contract testing is the wrong tool

Monoliths with internal module boundaries do not need Pact — unit and integration tests suffice. Early prototypes where API shape changes daily will fight broker overhead. Services with a single consumer and co-located teams may prefer a shared OpenAPI diff in CI.

Contract testing shines when **ownership splits across teams** and **API stability is a product commitment**.

## Measuring success

Track provider verification pass rate, time-to-detect breaking changes (pact failure vs production alert), and staging environment hours saved. If verification is always green and production still breaks API contracts, consumers are not writing pacts for the fields that actually matter — review incident postmortems for missing coverage.

Contract testing turns implicit API promises into executable tests. The notification service never again learns about a field rename from a 2 AM batch job failure.''',
},

"storybook-chromatic-visual-testing": {
    "title": "Storybook and Chromatic Visual Regression Testing",
    "seoTitle": "Storybook Chromatic Visual Testing: CI Snapshots, Baselines, and Flake Control",
    "description": "Chromatic captures Storybook stories as visual snapshots in CI — baseline review workflows, flake mitigation, component isolation, and when visual diffs beat unit assertions.",
    "datePublished": "2026-01-15",
    "tags": ["Testing", "Storybook", "Frontend", "CI/CD"],
    "keywords": "Storybook Chromatic visual testing, visual regression CI, component snapshot testing, UI regression detection",
    "faq": [
        {"q": "What does Chromatic test that Jest cannot?", "a": "Chromatic captures rendered pixels and layout — CSS regressions, font loading shifts, responsive breakpoints, and theme token drift that DOM assertions miss entirely."},
        {"q": "How do you handle intentional visual changes?", "a": "Chromatic presents a diff UI in PR checks. Reviewers accept baselines per-story. Accepted changes become the new baseline; rejected changes block merge."},
        {"q": "How do you reduce Chromatic flake?", "a": "Disable animations in stories, mock dates and locales, use fixed viewports, stub web fonts with fallback stacks, and avoid stories that depend on live API data."},
    ],
    "body": r'''A one-line CSS change to `line-height` on our button component shifted checkout CTA alignment by three pixels. Unit tests passed — they assert React props, not pixels. Design QA caught it manually two days later. Chromatic would have flagged the diff in the PR within minutes.

Visual regression testing closes the gap between "component renders" and "component looks correct." Storybook isolates components; Chromatic snapshots them in CI.

## The failure mode visual tests catch

```
Unit test:  <Button variant="primary"> renders ✓
Visual test: Button shadow clipped at 320px viewport ✗
```

CSS is global. A token rename in the design system propagates silently until a human squints at Figma vs production. Visual diffs make layout regressions binary: changed or not.

## Storybook as the test surface

Each story is a **frozen UI state** — loading, error, empty, overflowing text, dark mode. Chromatic uploads Storybook builds and captures each story at configured viewports.

```tsx
// Button.stories.tsx
import type { Meta, StoryObj } from "@storybook/react";
import { Button } from "./Button";

const meta: Meta<typeof Button> = {
  title: "Components/Button",
  component: Button,
  parameters: {
    chromatic: {
      viewports: [320, 768, 1280],
      delay: 300, // wait for font load
    },
  },
};
export default meta;

type Story = StoryObj<typeof Button>;

export const Primary: Story = { args: { variant: "primary", children: "Continue" } };
export const Disabled: Story = { args: { variant: "primary", disabled: true, children: "Continue" } };
export const LongLabel: Story = { args: { children: "Save payment method for future purchases" } };
```

Stories should represent **states users hit**, not demo props. Empty cart, 47-character username truncation, and skeleton loaders matter more than "Default."

## CI integration

```yaml
# .github/workflows/chromatic.yml
- name: Publish to Chromatic
  uses: chromaui/action@v11
  with:
    projectToken: ${{ secrets.CHROMATIC_PROJECT_TOKEN }}
    onlyChanged: true
    exitZeroOnChanges: false
```

`onlyChanged` limits snapshots to stories affected by the diff — critical at 800+ stories. Without it, every PR re-snapshots everything and CI times balloon.

PR checks show a Chromatic link: green (no diff), yellow (changes need review), red (build failure). Reviewers accept or reject per-story. Accepted baselines persist; rejected changes require code fixes.

## Baseline workflow

```
Main branch     → baseline snapshots (source of truth)
Feature branch  → capture → diff against baseline
Reviewer        → accept (new baseline) or reject (fix code)
Merge           → accepted snapshots become main baseline
```

Branch baselines fork from main at merge-base. Long-lived feature branches accumulate drift — rebase frequently or accept-all on merge creates noisy review batches.

## Flake sources and fixes

| Flake source | Fix |
|---|---|
| CSS animations | `parameters.chromatic.pauseAnimationAtEnd = true` |
| Web fonts | Self-host fonts; `font-display: optional` in stories |
| Date/time | Mock `Date.now` in story decorators |
| Random IDs | Seed or stub UUID generation |
| Lazy images | Use static placeholder URLs in stories |
| Portal modals | Set `chromatic.ignoreSelectors` for known overlays |

Animation flake is the most common. A spinner that never stops produces different pixels every capture.

```tsx
// .storybook/preview.tsx decorator
export const decorators = [
  (Story) => {
    document.documentElement.classList.add("chromatic-disable-animations");
    return <Story />;
  },
];
```

```css
.chromatic-disable-animations *, .chromatic-disable-animations *::before, .chromatic-disable-animations *::after {
  animation-duration: 0s !important;
  transition-duration: 0s !important;
}
```

## Component isolation vs page-level snapshots

Chromatic works at story granularity — one component state per snapshot. Page-level Playwright screenshots catch integration layout issues stories miss (header + sidebar + content interaction).

Use both:

- **Chromatic**: design system components, variant matrices, theme modes
- **Playwright visual**: 5–10 critical user journeys (login, checkout, settings)

Duplicating every page in Storybook is expensive. Duplicating every button variant in Playwright is slow.

## Design token regression

When design tokens change, Chromatic diffs explode across hundreds of stories. That is the point — but review fatigue follows.

Mitigate with:

1. **Token change PRs** isolated from feature PRs
2. **Component-level stories first** — catch token issues before page composites
3. **Theming decorator** that applies light/dark in one Chromatic run

```tsx
export const AllThemes: Story = {
  render: () => (
    <>
      <ThemeProvider theme="light"><Button>Light</Button></ThemeProvider>
      <ThemeProvider theme="dark"><Button>Dark</Button></ThemeProvider>
    </>
  ),
};
```

## Cost and scope governance

Chromatic bills on snapshot count × viewports. An undisciplined Storybook becomes a CI tax.

Rules that keep cost sane:

- Cap viewports at 2–3 per story unless responsive behavior is the story's purpose
- Delete orphaned stories when components deprecate
- Use `chromatic.ignore` for stories that duplicate coverage
- `onlyChanged` on every PR

Track snapshot count in CI metrics. Alert when it grows >10% quarter-over-quarter without component count growth.

## Accessibility pairing

Visual regression does not replace accessibility testing. A contrast regression may show as a subtle color diff Chromatic reviewers miss.

Pair Chromatic with axe in Storybook:

```tsx
import { withA11y } from "@storybook/addon-a11y";
export default { decorators: [withA11y] };
```

Run axe on the same stories Chromatic captures. Contrast failures block merge even if pixels look "close enough."

## When not to use Chromatic

Highly dynamic content — live charts, maps, video players — produce noisy diffs unless heavily stubbed. Third-party embeds (Stripe Elements, Google Maps) should be mocked in stories, not snapshotted live.

Visual testing also cannot verify behavior — a button that looks correct but lost its click handler needs interaction tests (Storybook interaction tests or component testing library).

## Team workflow

Designers review Chromatic diffs for intentional token changes. Engineers review for unintended regressions. Establish a SLA: visual diffs reviewed within 4 hours of PR open — stale diffs block merges and frustrate everyone.

Document "acceptable diff" criteria: sub-pixel antialiasing on Retina vs CI runners may need threshold tuning via Chromatic's `diffThreshold`.

Visual regression turns "looks fine on my laptop" into an auditable, CI-enforced contract between design and engineering.''',
},

}
