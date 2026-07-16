---
title: "Error Boundary Patterns"
slug: "react-error-boundaries-patterns"
description: "Implement React error boundary patterns: granular fallbacks, reset strategies, logging integration, and boundaries for async and server component errors."
datePublished: "2025-02-13"
dateModified: "2025-02-13"
tags: ["React", "Web", "Error Handling", "Error Boundaries"]
keywords: "React error boundaries, error boundary patterns, componentDidCatch, fallback UI, error recovery, React error handling"
faq:
  - q: "What errors do React error boundaries catch?"
    a: "Error boundaries catch rendering errors, lifecycle errors, and errors in constructors of child components during rendering. They do not catch errors in event handlers, async code (setTimeout, promises), server-side rendering throws, or errors in the error boundary itself. You need try/catch for event handlers and .catch() for async work in addition to boundaries."
  - q: "Where should I place error boundaries in my component tree?"
    a: "Place boundaries at every level where you want independent failure isolation — per route, per widget, per data-dependent section. A single app-level boundary means one chart throwing takes down the entire page. Granular boundaries let the rest of the UI function while the failed section shows a fallback with a retry option."
  - q: "How do I recover from an error boundary without reloading the page?"
    a: "Give each boundary a reset key or reset function that clears error state and re-renders children. Incrementing a key prop on the boundary forces React to remount the failed subtree. For transient errors like failed fetches, a retry button that calls the reset function is enough. For persistent code bugs, the boundary re-catches on remount until the code is fixed."
---

A dashboard widget throwing on null data used to white-screen the entire analytics page — twenty working charts gone because one API response was malformed. Error boundaries isolate failures to the subtree that broke, render a fallback where the crash happened, and let the rest of the application keep running. They are try/catch for the render phase, and most React apps do not have enough of them.

## Basic error boundary

Error boundaries are class components (no hook equivalent yet) implementing `getDerivedStateFromError` and `componentDidCatch`:

```tsx
import { Component, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, info: React.ErrorInfo) => void;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    this.props.onError?.(error, info);
    // Send to error tracking: Sentry, Datadog, etc.
  }

  reset = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      return this.props.fallback ?? (
        <div role="alert">
          <p>Something went wrong.</p>
          <button onClick={this.reset}>Try again</button>
        </div>
      );
    }
    return this.props.children;
  }
}
```

`getDerivedStateFromError` updates state to show the fallback. `componentDidCatch` runs side effects — logging, analytics — after the error is caught.

## Granular boundary placement

```tsx
function DashboardPage() {
  return (
    <div>
      <ErrorBoundary fallback={<HeaderError />}>
        <Header />
      </ErrorBoundary>

      <div className="grid">
        <ErrorBoundary fallback={<WidgetError name="Revenue" />}>
          <RevenueChart />
        </ErrorBoundary>

        <ErrorBoundary fallback={<WidgetError name="Users" />}>
          <UserGrowthChart />
        </ErrorBoundary>

        <ErrorBoundary fallback={<WidgetError name="Activity" />}>
          <ActivityFeed />
        </ErrorBoundary>
      </div>
    </div>
  );
}
```

Each widget fails independently. One bad API response does not cascade.

## Reset strategies

**Key-based reset** — force remount by changing a key:

```tsx
function ResettableBoundary({ children }: { children: ReactNode }) {
  const [key, setKey] = useState(0);

  return (
    <ErrorBoundary
      key={key}
      fallback={<RetryPrompt onRetry={() => setKey(k => k + 1)} />}
    >
      {children}
    </ErrorBoundary>
  );
}
```

**State-based reset** — the boundary's internal `reset()` clears error state and re-attempts rendering children. Works for transient data errors; persistent code bugs re-trigger immediately.

**Navigation reset** — route changes naturally unmount and remount subtrees. Navigating away and back clears error state without explicit reset logic.

## What boundaries do not catch

Handle these separately:

```tsx
// Event handlers — use try/catch
function handleClick() {
  try {
    riskyOperation();
  } catch (error) {
    showToast("Operation failed");
    logError(error);
  }
}

// Async code — use .catch() or try/catch in async functions
async function loadData() {
  try {
    const data = await fetch("/api/data").then(r => r.json());
    setData(data);
  } catch (error) {
    setError(error);
  }
}

// Server Components — use error.tsx in Next.js App Router
// export default function Error({ error, reset }) { ... }
```

Document which error handling strategy applies where. Teams that rely only on boundaries miss event handler and async errors entirely.

## Integrating with error tracking

```tsx
componentDidCatch(error: Error, info: React.ErrorInfo) {
  Sentry.captureException(error, {
    contexts: {
      react: { componentStack: info.componentStack },
    },
  });
}
```

Include `componentStack` in every report — it shows exactly which component tree path led to the crash. Tag with route, user ID, and feature flag state for faster triage.

## react-error-boundary library

For function-component ergonomics, `react-error-boundary` wraps the class pattern:

```tsx
import { ErrorBoundary } from "react-error-boundary";

function WidgetError({ error, resetErrorBoundary }) {
  return (
    <div role="alert">
      <p>{error.message}</p>
      <button onClick={resetErrorBoundary}>Retry</button>
    </div>
  );
}

<ErrorBoundary FallbackComponent={WidgetError} onReset={() => queryClient.invalidateQueries()}>
  <DataWidget />
</ErrorBoundary>
```

`onReset` runs before the boundary remounts children — useful for invalidating stale cache entries that caused the error.

## Next.js App Router error.tsx

Server Components and route segments use file-based error boundaries:

```tsx
// app/dashboard/error.tsx
"use client";

export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div>
      <h2>Dashboard failed to load</h2>
      <button onClick={reset}>Retry</button>
    </div>
  );
}
```

`error.tsx` catches errors in its route segment and below. Pair with `loading.tsx` for Suspense fallbacks and `not-found.tsx` for 404s.

## Design principles

- **Fail visibly, not silently** — show a clear fallback, not an empty div.
- **Always offer recovery** — retry button, link to home, or automatic reset on navigation.
- **Log everything** — boundaries are your last line of defense; every catch should report.
- **Bound at the right granularity** — too few boundaries mean wide outages; too many mean noisy logs for expected failures.

Treat production rollout as a measured change: ship with observability, validate rollback, and review metrics 24 hours after deploy — patterns that look obvious in docs fail when skipped under release pressure.

## Common production mistakes

Teams get error boundaries patterns wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of error boundaries patterns fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Debugging and triage workflow

When error boundaries patterns misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [React error boundaries documentation](https://react.dev/reference/react/Component#catching-rendering-errors-with-an-error-boundary)
- [react-error-boundary library](https://github.com/bvaughn/react-error-boundary)
- [Next.js error handling](https://nextjs.org/docs/app/building-your-application/routing/error-handling)
- [Sentry React error boundary integration](https://docs.sentry.io/platforms/javascript/guides/react/features/error-boundary/)
- [React 19 — improved error reporting](https://react.dev/blog/2024/12/05/react-19)
