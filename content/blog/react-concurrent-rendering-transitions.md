---
title: "Concurrent Rendering and Transitions"
slug: "react-concurrent-rendering-transitions"
description: "Understand React concurrent rendering and useTransition: non-blocking updates, interruptible rendering, and keeping UI responsive during expensive state changes."
datePublished: "2025-02-09"
dateModified: "2025-02-09"
tags: ["React", "Web", "Concurrent", "Performance"]
keywords: "React concurrent rendering, useTransition, startTransition, interruptible rendering, React 18 concurrent, non-blocking updates"
faq:
  - q: "What is concurrent rendering in React?"
    a: "Concurrent rendering lets React interrupt, pause, and resume rendering work instead of blocking the main thread until a full tree reconciliation completes. Urgent updates like typing and clicking render immediately; non-urgent updates like filtering a large list can be deferred and interrupted if a newer urgent update arrives. The UI stays responsive during expensive re-renders."
  - q: "When should I use useTransition?"
    a: "Wrap state updates that cause expensive re-renders but are not immediately visible to the user — search filtering, tab switching with heavy content, sorting large datasets. Keep direct user input updates (keystrokes, checkbox toggles) as urgent renders outside transitions. If users notice lag on the update you wrapped, it was probably urgent and should not be in a transition."
  - q: "Does useTransition make rendering faster?"
    a: "No. Transitions do not reduce total render work — they deprioritize it so urgent work runs first. The expensive render still happens; it just does not block typing or animations while it does. For actually faster renders, memoize components, virtualize lists, or reduce the work per render."
---

You type in a search box and the letters stutter because every keystroke triggers a re-render of 5,000 filtered list items synchronously. The input feels broken even though the filter logic is correct. React's concurrent rendering model separates urgent updates (what you type) from non-urgent updates (the filtered results), so the input stays smooth while the list catches up.

## Urgent vs non-urgent updates

React 18+ categorizes state updates:

- **Urgent** — direct user interaction: typing, clicking, hovering. Must render immediately or the UI feels frozen.
- **Non-urgent** — derived state: filtered lists, search results, tab content loading. Can wait without the user noticing.

Without concurrent features, all updates render synchronously in arrival order. A slow render from a filter blocks the next keystroke.

## useTransition in practice

```tsx
import { useState, useTransition, useMemo } from "react";

function SearchableList({ items }: { items: Item[] }) {
  const [query, setQuery] = useState("");
  const [filteredQuery, setFilteredQuery] = useState("");
  const [isPending, startTransition] = useTransition();

  const filtered = useMemo(
    () => items.filter(item =>
      item.name.toLowerCase().includes(filteredQuery.toLowerCase())
    ),
    [items, filteredQuery]
  );

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    setQuery(e.target.value);                    // urgent: input stays responsive
    startTransition(() => {
      setFilteredQuery(e.target.value);          // non-urgent: filter can wait
    });
  }

  return (
    <div>
      <input value={query} onChange={handleChange} />
      {isPending && <span>Filtering...</span>}
      <List items={filtered} />
    </div>
  );
}
```

`setQuery` renders immediately — the input shows the new character. `setFilteredQuery` runs inside `startTransition` — React can interrupt the resulting list re-render if the user types again before it finishes.

## What isPending tells you

`isPending` is true from when the transition starts until the deferred render commits. Use it for subtle loading indicators:

```tsx
<div style={{ opacity: isPending ? 0.7 : 1 }}>
  <List items={filtered} />
</div>
```

Do not use `isPending` to disable the input — the input is the urgent update and should never be blocked by the deferred one.

## startTransition without the hook

For transitions outside React components or event handlers that do not need pending state:

```tsx
import { startTransition } from "react";

function handleTabClick(tabId: string) {
  startTransition(() => {
    setActiveTab(tabId);
  });
}
```

Same deprioritization, no `isPending` tracking.

## Concurrent rendering under the hood

React's concurrent renderer can:

- **Interrupt** a low-priority render if a high-priority update arrives.
- **Split** rendering work across multiple frames via `requestIdleCallback`-like scheduling.
- **Discard** stale renders — if the user types "abc" quickly, React may skip rendering results for "a" and "ab."

This is not parallelism (still one thread) — it is cooperative scheduling that yields to the browser between work units.

## Common patterns

**Search with deferred results:**

```tsx
const [query, setQuery] = useState("");
const [deferredQuery, setDeferredQuery] = useState("");

function onSearch(value: string) {
  setQuery(value);
  startTransition(() => setDeferredQuery(value));
}

const results = useMemo(() => search(deferredQuery), [deferredQuery]);
```

**Tab switching with heavy panels:**

```tsx
function selectTab(tab: string) {
  startTransition(() => setActiveTab(tab));
}
```

**Server data refetching:**

```tsx
function handleRefresh() {
  startTransition(async () => {
    const data = await fetchData();
    setData(data);
  });
}
```

## useDeferredValue as an alternative

When you do not control the state setter (props from parent, context), defer the value itself:

```tsx
import { useDeferredValue } from "react";

function Results({ query }: { query: string }) {
  const deferredQuery = useDeferredValue(query);
  const isStale = query !== deferredQuery;

  const results = useMemo(() => search(deferredQuery), [deferredQuery]);

  return (
    <div style={{ opacity: isStale ? 0.6 : 1 }}>
      <ResultList items={results} />
    </div>
  );
}
```

`useDeferredValue` defers a value; `useTransition` defers a state update. Use `useDeferredValue` when the query comes from props; use `useTransition` when you own the setter.

## What transitions do not fix

- **Slow components** — if `List` takes 500ms to render 5,000 items, transitions prevent blocking but the list still takes 500ms. Virtualize it.
- **Network latency** — transitions manage render priority, not fetch speed. Use Suspense for data loading.
- **State bugs** — splitting query and filteredQuery into two states requires keeping them in sync. For simple cases, `useDeferredValue` on a single state variable is cleaner.

## Suspense integration

Transitions pair naturally with Suspense for data fetching:

```tsx
function SearchPage() {
  const [query, setQuery] = useState("");
  const [isPending, startTransition] = useTransition();

  return (
    <>
      <input onChange={(e) => startTransition(() => setQuery(e.target.value))} />
      {isPending && <Spinner />}
      <Suspense fallback={<ResultsSkeleton />}>
        <Results query={query} />
      </Suspense>
    </>
  );
}
```

Suspense handles async data; transitions handle urgent vs non-urgent renders. Together they keep input responsive while expensive trees load.

## Debugging transition behavior

React DevTools Profiler shows `transition` lanes separately from `sync` updates. If input still feels laggy:

1. Verify the state update is wrapped in `startTransition` — not just the fetch
2. Check for synchronous work in render (filtering 10K items without `useMemo`)
3. Ensure expensive child components are memoized or virtualized

`useTransition` does not make renders faster — it deprioritizes them. Profiling still required.

Pair with [React memoization compiler](https://blog.michaelsam94.com/react-memoization-compiler/) when transition-deferred renders still recompute too much subtree.

## Common production mistakes

Teams get concurrent rendering transitions wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of concurrent rendering transitions fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Debugging and triage workflow

When concurrent rendering transitions misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [React useTransition documentation](https://react.dev/reference/react/useTransition)
- [React useDeferredValue documentation](https://react.dev/reference/react/useDeferredValue)
- [React 18 concurrent features explainer](https://react.dev/blog/2022/03/29/react-v18)
- [React docs — keeping components pure](https://react.dev/learn/keeping-components-pure)
- [React Window — list virtualization](https://github.com/bvaughn/react-window)
