---
title: "The use() Hook and Promises in React"
slug: "react-use-hook-promises"
description: "React's use() hook reads promises and context during render. How it works, how it differs from useEffect fetching, and patterns for Suspense-friendly data loading."
datePublished: "2026-01-04"
dateModified: "2026-01-04"
tags: ["React", "Web", "JavaScript", "Suspense"]
keywords: "React use hook, use() promise, React 19, Suspense data fetching, context reading, render phase"
faq:
  - q: "What does the React use() hook do?"
    a: "The use() hook reads the value of a resource during render. It accepts a Promise (suspending until resolved) or a Context (returning the current value). Unlike hooks such as useState, use() can be called conditionally and inside loops, which makes it flexible for reading context in branches and for integrating promise-based data sources with Suspense."
  - q: "How is use() different from useEffect for data fetching?"
    a: "useEffect runs after render and triggers a state update when data arrives, causing a second render with a loading flash. use() suspends during render when given an unresolved promise, letting a parent Suspense boundary show a fallback instead. use() is render-phase and pairs with Suspense; useEffect is commit-phase and pairs with local loading state."
  - q: "Can I call use() conditionally?"
    a: "Yes. Unlike most React hooks, use() is intentionally callable inside if statements and loops because it reads a resource passed as an argument rather than registering persistent state on the fiber. You still must not call it inside try/catch blocks around the suspend point in ways that violate React's rules — consult the React docs for the exact constraints on error handling with use()."
---

React 19 introduced `use()` as a hook that blurs the line between "reading data" and "rendering UI." You pass it a Promise, it suspends until the Promise resolves, and your component continues with the value — no `useState`, no `useEffect`, no intermediate loading flag. The first time I replaced a ten-line fetch effect with three lines of `use()`, the component read like synchronous code even though the network was still async underneath.

That simplicity comes with constraints. `use()` is not a drop-in replacement for TanStack Query or SWR. It is a low-level primitive for Suspense-integrated data loading and context reading. Understanding when to reach for it saves you from either over-engineering or fighting the renderer.

## Reading promises with use()

```tsx
import { use, Suspense } from "react";

function UserProfile({ userPromise }: { userPromise: Promise<User> }) {
  const user = use(userPromise);
  return <h1>{user.name}</h1>;
}

// Parent creates the promise once and passes it down
function Page() {
  const userPromise = fetchUser(id); // starts immediately
  return (
    <Suspense fallback={<ProfileSkeleton />}>
      <UserProfile userPromise={userPromise} />
    </Suspense>
  );
}
```

The Promise must be created outside the component that calls `use()`, or recreated in a way that preserves referential stability across suspends. If you create a fresh Promise on every render inside `UserProfile`, you will suspend forever — each render starts a new unresolved Promise.

The pattern that works: start the fetch in the parent (or in a cache layer), pass the stable Promise reference to the child, and let `use()` unwrap it.

## use() for Context — including conditional reads

Before `use()`, reading Context conditionally violated the Rules of Hooks. `useContext` had to be called unconditionally at the top level. `use()` removes that restriction:

```tsx
function ThemeLabel({ showTheme }: { showTheme: boolean }) {
  if (showTheme) {
    const theme = use(ThemeContext);
    return <span>{theme.name}</span>;
  }
  return <span>Default</span>;
}
```

This matters for component libraries and polymorphic components where context is only relevant on certain code paths. The trade-off: `use()` throws if the context value is missing (there is no default), so provide defaults at the Provider or handle absence explicitly.

## Integration with caching libraries

Raw `use(promise)` does not deduplicate requests, cache results, or handle revalidation. In production you wrap it:

```tsx
// Conceptual pattern with a simple cache
const cache = new Map<string, Promise<User>>();

function getUser(id: string): Promise<User> {
  if (!cache.has(id)) {
    cache.set(id, fetch(`/api/users/${id}`).then(r => r.json()));
  }
  return cache.get(id)!;
}

function UserCard({ id }: { id: string }) {
  const user = use(getUser(id));
  return <Card name={user.name} />;
}
```

Libraries like React Query and SWR are building Suspense-compatible APIs that handle staleness, background refetch, and deduplication. Unless your needs are trivial, prefer those over a hand-rolled Map. `use()` is the hook; the cache is the hard part.

## Error handling and retry

When a Promise passed to `use()` rejects, the nearest error boundary catches it — same as a Server Component throw. Plan for this explicitly:

```tsx
<ErrorBoundary fallback={<UserLoadError onRetry={refetch} />}>
  <Suspense fallback={<Skeleton />}>
    <UserProfile userPromise={userPromise} />
  </Suspense>
</ErrorBoundary>
```

Retry requires creating a new Promise reference. Mutating the rejected Promise does not re-trigger Suspense. Increment a `key` on the boundary or call a parent function that replaces the Promise in state (which forces a new render with a fresh fetch).

## use() vs useEffect — decision guide

| Concern | use() + Suspense | useEffect + useState |
| --- | --- | --- |
| Initial page load | Streams with SSR | Client-only fetch after paint |
| Loading UI | Parent fallback | Local isLoading flag |
| Conditional fetch | Awkward — promise starts before branch | Natural |
| Polling / subscriptions | Poor fit | Natural |
| DevTools familiarity | Newer pattern | Universal |

Use `use()` when the data is part of the render tree's critical path and you already have Suspense boundaries. Use `useEffect` (or a data library) for post-mount updates, user-triggered refetches, and anything that should not block render.

## Pitfalls from the field

**Waterfalls from sequential use() calls.** Two `use()` calls on dependent promises serialize. Parallelize independent fetches before render and pass resolved structures down, or use `Promise.all` in the parent.

**Missing Suspense boundary.** `use()` on an unresolved promise without a Suspense ancestor throws in development and breaks in production. Every `use(promise)` subtree needs a boundary.

**Server vs client boundaries.** In RSC architectures, fetching often belongs in Server Components, with Client Components receiving serializable props. Do not pass non-serializable Promises across the server/client boundary unless your framework explicitly supports it.

## Common production mistakes

Teams get use hook promises wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of use hook promises fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Debugging and triage workflow

When use hook promises misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [React use() reference](https://react.dev/reference/react/use)
- [React 19 release — use() API](https://react.dev/blog/2024/12/05/react-19)
- [Suspense for data fetching](https://react.dev/reference/react/Suspense)
- [TanStack Query Suspense guide](https://tanstack.com/query/latest/docs/framework/react/guides/suspense)
- [Error boundaries in React](https://react.dev/reference/react/Component#catching-rendering-errors-with-an-error-boundary)
