---
title: "Fine-Grained Reactivity in SolidJS"
slug: "solidjs-fine-grained-reactivity"
description: "SolidJS updates only the DOM nodes that depend on changed signals — no virtual DOM diffing. Learn how fine-grained reactivity works and why it delivers React-like ergonomics with better runtime performance."
datePublished: "2025-09-04"
dateModified: "2025-09-04"
tags: ["SolidJS", "JavaScript", "Reactivity", "Frontend"]
keywords: "SolidJS reactivity, fine-grained updates, signals, createSignal, createMemo, no virtual DOM, reactive primitives, SolidJS performance"
faq:
  - q: "Does SolidJS use a virtual DOM?"
    a: "No. SolidJS compiles JSX into real DOM operations wired directly to reactive subscriptions. When a signal changes, only the specific text node or attribute bound to that signal updates — no tree diffing, no reconciliation pass. This is why SolidJS benchmarks often beat React and Vue on update-heavy workloads: the work scales with what changed, not with component tree size."
  - q: "How is SolidJS reactivity different from React hooks?"
    a: "React re-runs component functions on state change and diffs the resulting virtual DOM. SolidJS runs each component function once at creation time; the JSX inside sets up reactive subscriptions. State reads inside those subscriptions re-execute only the affected DOM update, not the whole component. Think of Solid components as setup functions that wire DOM nodes to signals, not render functions that produce trees."
  - q: "Can I use SolidJS with existing React knowledge?"
    a: "The JSX and component model feel familiar, but the mental model is different. You don't put reactive reads inside a render function that re-executes — you use signals and memos, and the compiler handles binding. Hooks like useState map to createSignal; useMemo maps to createMemo. The biggest shift: variables from signals are accessed by calling them as functions — count(), not count."
---

I profiled the same todo-list component in React and SolidJS on a list with 10,000 items, toggling one checkbox. React re-rendered the list component, diffed 10,000 virtual nodes, and committed one changed `<input>`. SolidJS updated that single checkbox attribute. No diff. No re-render. The component function never ran again after initial mount.

That difference is fine-grained reactivity — SolidJS's core design bet. Instead of re-executing components and diffing trees, Solid wires each DOM node directly to the signals it reads. When a signal changes, the runtime updates exactly those nodes. The model feels like React on the surface (JSX, components, props) but executes like a spreadsheet engine under the hood.

## Signals: the atomic unit of state

Everything reactive in SolidJS starts with a signal — a getter/setter pair that tracks dependencies:

```jsx
import { createSignal } from "solid-js";

function Counter() {
  const [count, setCount] = createSignal(0);

  return (
    <button onClick={() => setCount(c => c + 1)}>
      Clicked {count()} times
    </button>
  );
}
```

Notice `count()` — signals are functions. Calling `count()` inside JSX registers a subscription: when `count` changes, only the text node `"Clicked N times"` updates. The `<button>` element itself is created once. The `onClick` handler closes over `setCount` but doesn't re-bind on each update.

This is the mental model shift from React: your component body is a setup function, not a render function. It runs once. Reactive updates happen at the DOM binding level, not by re-invoking the component.

## Memos and derived state

Derived values use `createMemo`, which caches its computation and only recalculates when dependencies change:

```jsx
import { createSignal, createMemo, For } from "solid-js";

function FilteredList() {
  const [items, setItems] = createSignal(["apple", "banana", "cherry"]);
  const [filter, setFilter] = createSignal("");

  const filtered = createMemo(() =>
    items().filter(i => i.includes(filter()))
  );

  return (
    <>
      <input value={filter()} onInput={e => setFilter(e.target.value)} />
      <ul>
        <For each={filtered()}>
          {(item) => <li>{item}</li>}
        </For>
      </ul>
    </>
  );
}
```

When `filter` changes, `filtered` recalculates. The `<For>` component diffs the list by reference identity — only added or removed items touch the DOM. Typing in the filter box doesn't re-create the entire `<ul>`; Solid's list reconciliation handles insertions and removals surgically.

## Effects for side work

`createEffect` runs a function whenever its signal dependencies change — useful for logging, fetching, or syncing to external systems:

```jsx
createEffect(() => {
  console.log("Count is now:", count());
  document.title = `Count: ${count()}`;
});
```

Effects run after the DOM update for the current change, similar to React's `useEffect` but with automatic dependency tracking. You don't write dependency arrays — Solid tracks which signals were read inside the effect body.

## Why no virtual DOM is a feature

Virtual DOM frameworks pay a tax on every update: serialize the component output to a tree, diff against the previous tree, compute patches, apply patches. For small apps the tax is invisible. For dashboards with hundreds of live-updating cells, or lists with thousands of rows, the tax dominates.

SolidJS compiles JSX at build time into `_el$` template functions that create DOM nodes and register reactive bindings:

```jsx
// What you write:
<div>{name()}</div>

// What Solid compiles (simplified):
const _el$ = template(`<div></div>`);
// On creation: bind text node to name signal
// On name change: textNode.data = newValue
```

The compiler knows exactly which DOM node each expression binds to. Runtime work is O(changed bindings), not O(tree size).

## Stores for nested state

Flat signals work for simple state. Nested objects use `createStore`, which applies fine-grained reactivity to property access:

```jsx
import { createStore } from "solid-js/store";

const [state, setState] = createStore({ user: { name: "Ada", age: 36 } });

// Only components reading state.user.name update:
setState("user", "name", "Grace");

// Deep partial update:
setState("user", { age: 37 });
```

Store property reads create granular subscriptions. A component that only reads `state.user.name` won't re-run when `state.user.age` changes — even though they're the same object tree.

## Practical patterns and pitfalls

**Don't destructure signals.** `const { count } = ...` breaks reactivity because you capture the value once. Always call signal getters in reactive contexts.

**Use `<Show>` and `<For>` for control flow.** Solid provides reactive control-flow components that handle conditional rendering and list diffing without destroying and recreating DOM subtrees unnecessarily.

**Batch updates.** Multiple `setSignal` calls in the same synchronous block batch into one DOM flush, avoiding intermediate repaints.

**Server-side rendering.** Solid supports SSR with streaming hydration. The server renders HTML; the client hydrates by attaching reactive bindings to existing DOM nodes rather than replacing them.

## Common production mistakes

Teams get solidjs fine grained reactivity wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of solidjs fine grained reactivity fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Debugging and triage workflow

When solidjs fine grained reactivity misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [SolidJS documentation — reactivity guide](https://www.solidjs.com/docs/latest/guide/introduction)
- [SolidJS signals API reference](https://www.solidjs.com/docs/latest/api/basic-reactivity)
- [Fine-grained reactivity — Ryan Carniato (Solid creator)](https://dev.to/this-is-learning/solidjs-reactivity-101-1k9a)
- [SolidJS vs React benchmarks](https://krausest.github.io/js-framework-benchmark/current.html)
- [SolidJS Playground for live experimentation](https://playground.solidjs.com/)
