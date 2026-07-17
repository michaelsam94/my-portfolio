---
title: "Signals: The Reactivity Primitive"
slug: "web-signals-fine-grained-reactivity"
description: "Understand signals as a fine-grained reactivity primitive: how they work, framework implementations in Solid, Angular, and Preact, and when signals beat virtual DOM diffing."
datePublished: "2026-05-16"
dateModified: "2026-07-17"
tags: ["Web", "JavaScript", "Reactivity", "Frontend"]
keywords: "signals, fine-grained reactivity, SolidJS, Angular signals, Preact signals, reactive primitives"
faq:
  - q: "What is a signal in web development?"
    a: "A signal is a reactive primitive that holds a value and automatically notifies dependents when the value changes. Unlike React state which triggers a full component re-render, a signal update propagates only to the specific DOM nodes or computations that read it. This fine-grained reactivity avoids the overhead of virtual DOM diffing for every state change, resulting in faster updates especially in components with large DOM trees or frequent state changes."
  - q: "How are signals different from React useState?"
    a: "useState triggers a re-render of the entire component function when state changes, and React diffs the virtual DOM to find what changed in the real DOM. Signals track which DOM nodes depend on which values at a granular level, and only those nodes update when a signal changes — no re-render, no diff. In practice, updating a counter signal in a component with 1000 DOM nodes updates one text node, while useState re-runs the component and diffs all 1000 nodes."
  - q: "Which frameworks support signals?"
    a: "SolidJS is built entirely on signals from the ground up. Angular added signals in version 16 as a core reactivity primitive alongside RxJS. Preact offers @preact/signals as an optional package. Vue's ref and computed are conceptually similar to signals. React does not have native signals, though proposals like the React Forget compiler aim to achieve similar fine-grained updates through automatic memoization. The TC39 Signals proposal aims to standardize a signal API across JavaScript."
---
Updating a counter in React re-rendered a component with 2,000 DOM nodes, diffed the virtual DOM, and patched one text node. In Solid, the same counter update changed one text node. No re-render. No diff. The framework knew exactly which DOM node displayed the counter because a signal tracked the dependency at creation time. Signals aren't a framework feature — they're a reactivity primitive that makes the framework's job trivial: update only what changed. The concept is spreading from Solid to Angular to Preact, and understanding it clarifies how reactive UI can work without virtual DOM overhead.

## How signals work

A signal is a getter/setter pair with a subscriber list:

```javascript
function createSignal(initialValue) {
  let value = initialValue;
  const subscribers = new Set();

  function read() {
    if (currentEffect) subscribers.add(currentEffect);
    return value;
  }

  function write(newValue) {
    value = newValue;
    subscribers.forEach(effect => effect());
  }

  return [read, write];
}
```

When an effect reads a signal, it registers as a subscriber. When the signal is written, only its subscribers re-run. No global re-render.

## SolidJS: signals-native framework

```jsx
import { createSignal, createEffect } from 'solid-js';

function Counter() {
  const [count, setCount] = createSignal(0);

  createEffect(() => {
    console.log('Count changed to:', count());
  });

  return (
    <div>
      <span>{count()}</span>       {/* only this text node updates */}
      <button onClick={() => setCount(c => c + 1)}>+</button>
    </div>
  );
}
```

`count()` is a function call — Solid tracks that this DOM text node depends on `count`. When `setCount` is called, only that text node updates.

### Derived values with memos

```jsx
import { createSignal, createMemo } from 'solid-js';

function ShoppingCart() {
  const [items, setItems] = createSignal([]);
  const total = createMemo(() =>
    items().reduce((sum, item) => sum + item.price * item.qty, 0)
  );

  return (
    <div>
      <ul>{/* render items */}</ul>
      <p>Total: ${total().toFixed(2)}</p>
    </div>
  );
}
```

`createMemo` is a cached derived signal — it recalculates only when `items` changes, and only DOM nodes reading `total()` update.

## Angular signals

Angular 16+ adopted signals as a core primitive:

```typescript
import { Component, signal, computed, effect } from '@angular/core';

@Component({
  selector: 'app-counter',
  template: `
    <p>Count: {{ count() }}</p>
    <p>Doubled: {{ doubled() }}</p>
    <button (click)="increment()">+</button>
  `,
})
export class CounterComponent {
  count = signal(0);
  doubled = computed(() => this.count() * 2);

  increment() {
    this.count.update(c => c + 1);
  }
}
```

Angular's `computed` is equivalent to Solid's `createMemo`. `effect` runs side effects when signals change. Angular is migrating from RxJS observables to signals for component state.

## Preact signals

```jsx
import { signal, computed } from '@preact/signals';
import { useSignals } from '@preact/signals-react/runtime';

function Counter() {
  useSignals();
  const count = signal(0);
  const doubled = computed(() => count.value * 2);

  return (
    <div>
      <p>{count}</p>       {/* auto-tracks, auto-updates */}
      <p>{doubled}</p>
      <button onClick={() => count.value++}>+</button>
    </div>
  );
}
```

Preact signals can be used in React via `@preact/signals-react`, bringing fine-grained updates to React components.

## Signals vs virtual DOM

| Aspect | Signals | Virtual DOM (React) |
|---|---|---|
| Update scope | Specific DOM nodes | Entire component subtree |
| Dependency tracking | Automatic at read time | Manual (useMemo, useCallback) |
| Re-render | None | Full component re-run |
| Diffing | None needed | O(n) tree comparison |
| Memory | Subscriber lists | Virtual DOM tree copies |
| Learning curve | New primitive | Familiar hooks |

## When signals matter most

Signals provide the biggest advantage when:
- Components have large DOM trees with small state changes
- State updates are frequent (real-time data, animations, typing)
- Derived values depend on multiple sources
- Performance profiling shows unnecessary re-renders

Signals provide less advantage when:
- Components are small (few DOM nodes)
- State changes are infrequent (form submission, page navigation)
- The team is deeply invested in React patterns

## The TC39 proposal

A standard signal API is being proposed for JavaScript:

```javascript
// Proposed standard API (not yet finalized)
import { Signal } from '#signals';

const count = new Signal(0);
count.value;          // read
count.value = 5;      // write

const doubled = count.derived(v => v * 2);
doubled.value;        // 10
```

Standardization would let signals work across frameworks without adapter libraries.

## Building your own signals

Understanding the implementation helps regardless of framework:

```javascript
let currentEffect = null;

function createSignal(initial) {
  let value = initial;
  const subs = new Set();

  const read = () => {
    if (currentEffect) subs.add(currentEffect);
    return value;
  };

  const write = (v) => {
    value = typeof v === 'function' ? v(value) : v;
    subs.forEach(fn => fn());
  };

  return [read, write];
}

function createEffect(fn) {
  const effect = () => {
    currentEffect = effect;
    fn();
    currentEffect = null;
  };
  effect();
}

// Usage
const [count, setCount] = createSignal(0);

createEffect(() => {
  console.log('Count is:', count()); // runs on every setCount
});

setCount(1); // logs: "Count is: 1"
setCount(2); // logs: "Count is: 2"
```

This is the entire reactivity system that powers Solid, in 30 lines.

## Signal graph debugging

Preact DevTools and Solid DevTools expose the signal dependency graph. When an effect re-runs unexpectedly, trace which signal change triggered it. Common bug: reading a signal inside a conditional that doesn't run every time, causing stale dependencies.

## Interop with non-reactive code

Bridge signals to imperative APIs with effects:

```javascript
effect(() => {
  document.title = `${pageTitle.value} — My App`;
});
```

Clean up side effects by returning a dispose function from effects where the framework supports it.

## Resources

- [SolidJS signals documentation](https://www.solidjs.com/docs/latest/api#createsignal)
- [Angular signals guide](https://angular.dev/guide/signals)
- [Preact signals](https://preactjs.com/guide/v10/signals/)
- [TC39 Signals proposal](https://github.com/tc39/proposal-signals)
- [Fine-grained reactivity (Ryan Carniato)](https://www.solidjs.com/guides/reactivity)

## Operational checklist (1)

Before promoting Web Signals Fine Grained Reactivity changes, confirm observability dashboards cover error rate and p75 latency for affected routes, rollback is documented in the pull request, and a staging drill reproduced the last known failure mode.

## Field validation (2)

Re-baseline Web Signals Fine Grained Reactivity after browser upgrades or CDN configuration changes. Mobile share above seventy percent shifts median device class — optimizations tuned on desktop lab profiles may not transfer.

## Coordination (3)

Align with platform and backend owners on cache TTL, deploy windows, and API contracts when Web Signals Fine Grained Reactivity touches shared infrastructure — single-layer wins often disappear when another tier invalidates caches.

## Operational checklist (4)

Before promoting Web Signals Fine Grained Reactivity changes, confirm observability dashboards cover error rate and p75 latency for affected routes, rollback is documented in the pull request, and a staging drill reproduced the last known failure mode.

## Field validation (5)

Re-baseline Web Signals Fine Grained Reactivity after browser upgrades or CDN configuration changes. Mobile share above seventy percent shifts median device class — optimizations tuned on desktop lab profiles may not transfer.

## Coordination (6)

Align with platform and backend owners on cache TTL, deploy windows, and API contracts when Web Signals Fine Grained Reactivity touches shared infrastructure — single-layer wins often disappear when another tier invalidates caches.

## Operational checklist (7)

Before promoting Web Signals Fine Grained Reactivity changes, confirm observability dashboards cover error rate and p75 latency for affected routes, rollback is documented in the pull request, and a staging drill reproduced the last known failure mode.

## Capacity and cost notes for web signals fine grained reactivity

Estimate QPS, payload size, cardinality, and downstream saturation. Functionally correct web signals fine grained reactivity changes still cause outages through pool exhaustion, crawl waste, or CPU amplification.

| Check | Expected for web signals fine grained reactivity |
|--------|----------------------|
| Happy path | Pass |
| Injected fault | Controlled degradation |
| After rollback | Prior stable behavior |

Concrete probe 1: inject the failure mode you fear for web signals fine grained reactivity in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Reviewer checklist for web signals fine grained reactivity

Ask what happens when the dependency is slow, when authz is skipped on batch jobs, and when clients retry. Those three questions catch most web signals fine grained reactivity regressions before production.

Concrete probe 2: inject the failure mode you fear for web signals fine grained reactivity in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Incident patterns around web signals fine grained reactivity

Most incidents involving web signals fine grained reactivity start as a silent drift: a secondary path skips the control, a retry amplifies load, or a config default from a tutorial ships to production. Write the failure story before the happy path.

| Check | Expected for web signals fine grained reactivity |
|--------|----------------------|
| Happy path | Pass |
| Injected fault | Controlled degradation |
| After rollback | Prior stable behavior |

Concrete probe 3: inject the failure mode you fear for web signals fine grained reactivity in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Invariants to enforce for web signals fine grained reactivity

Name three invariants that must hold after every deploy of web signals fine grained reactivity. Encode at least one in an automated test that fails when the invariant is disabled. Reviewers should reject PRs that only cover the primary UI path.

Concrete probe 4: inject the failure mode you fear for web signals fine grained reactivity in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Telemetry and ownership for web signals fine grained reactivity

Pair a leading operational signal with a lagging user or risk outcome. Page on burn related to web signals fine grained reactivity, not vanity counters. Keep a named owner and a dashboard link in the service catalog entry.

| Check | Expected for web signals fine grained reactivity |
|--------|----------------------|
| Happy path | Pass |
| Injected fault | Controlled degradation |
| After rollback | Prior stable behavior |

Concrete probe 5: inject the failure mode you fear for web signals fine grained reactivity in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Rollout sequence for web signals fine grained reactivity

Prefer flags, weighted routes, or dual-running configs. Rehearse rollback once in staging. The on-call note for web signals fine grained reactivity should include the revert command and the expected user-visible effect within five minutes.

Concrete probe 6: inject the failure mode you fear for web signals fine grained reactivity in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Cross-team contracts for web signals fine grained reactivity

Document producers, consumers, timeouts, and idempotency keys. Silent schema or policy changes are how web signals fine grained reactivity breaks without a clear owner in the incident channel.

| Check | Expected for web signals fine grained reactivity |
|--------|----------------------|
| Happy path | Pass |
| Injected fault | Controlled degradation |
| After rollback | Prior stable behavior |

Concrete probe 7: inject the failure mode you fear for web signals fine grained reactivity in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.
