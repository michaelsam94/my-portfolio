---
title: "Signals: The Reactivity Primitive"
slug: "web-signals-fine-grained-reactivity"
description: "Understand signals as a fine-grained reactivity primitive: how they work, framework implementations in Solid, Angular, and Preact, and when signals beat virtual DOM diffing."
datePublished: "2026-05-16"
dateModified: "2026-05-16"
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

## Measuring success in production

Deploy changes behind feature flags when possible so you can compare metrics between control and treatment groups. Use Real User Monitoring to capture performance data from actual devices and network conditions — lab tools alone miss the long tail of user experiences. Set up alerts for regressions: a 10% LCP increase week-over-week warrants investigation before it hits CrUX.

Document your baseline metrics before making changes. Performance work without measurement is guesswork. Share results with the team — concrete numbers ("LCP improved 800ms on mobile") build support for continued investment in web performance and reliability.

Review changes quarterly. Browser updates, new API support, and traffic pattern shifts can obsolete previous optimizations or create new opportunities. What worked in 2024 may not be the best approach in 2026.

## Resources

- [SolidJS signals documentation](https://www.solidjs.com/docs/latest/api#createsignal)
- [Angular signals guide](https://angular.dev/guide/signals)
- [Preact signals](https://preactjs.com/guide/v10/signals/)
- [TC39 Signals proposal](https://github.com/tc39/proposal-signals)
- [Fine-grained reactivity (Ryan Carniato)](https://www.solidjs.com/guides/reactivity)
