---
title: "Fine-Grained Reactivity in SolidJS"
slug: "solidjs-fine-grained-reactivity"
description: "SolidJS updates only the DOM nodes that depend on changed signals — no virtual DOM diffing. Learn how fine-grained reactivity works and why it delivers React-like ergonomics with better runtime performance."
datePublished: "2025-09-04"
dateModified: "2026-07-17"
tags: ["SolidJS", "JavaScript", "Reactivity", "Frontend"]
keywords: "SolidJS reactivity, fine-grained updates, signals, createSignal, createMemo, no virtual DOM, reactive primitives, SolidJS performance"
faq:
  - q: "Does SolidJS use a virtual DOM?"
    a: "No. SolidJS compiles JSX into real DOM operations wired directly to reactive subscriptions. When a signal changes, only the specific text node or attribute bound to that signal updates — no tree diffing, no reconciliation pass. This is why SolidJS benchmarks often beat React and Vue on update-heavy workloads: the work scales with what changed, not with component tree size."
  - q: "How is SolidJS reactivity different from React hooks?"
    a: "React re-runs component functions on state change and diffs the resulting virtual DOM. SolidJS runs each component function once at creation time; the JSX inside sets up reactive subscriptions. State reads inside those subscriptions re-execute only the affected DOM update, not the whole component. Think of Solid components as setup functions that wire DOM nodes to signals, not render functions that produce trees."
  - q: "Can I use SolidJS with existing React knowledge?"
    a: "The JSX and component model feel familiar, but the mental model is different. You don't put reactive reads inside a render function that re-executes — you use signals and memos, and the compiler handles binding. Hooks like useState map to createSignal; useMemo maps to createMemo. The biggest shift: variables from signals are accessed by calling them as functions — count(), not count."
faqAnswers:
  - question: "When is solidjs fine grained reactivity the wrong approach?"
    answer: "When a simpler control already covers the risk, or when the operational cost exceeds the benefit for your threat and traffic model."
  - question: "What should we measure for solidjs fine grained reactivity?"
    answer: "Pair a leading operational signal with a lagging user or risk outcome, reviewed on a fixed cadence with a named owner."
  - question: "How do we roll back solidjs fine grained reactivity safely?"
    answer: "Keep the prior artifact or config warm, rehearse the revert once in staging, and document the one-command rollback for on-call."
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

## React-to-Solid migration pitfalls

Destructuring props breaks reactivity: `const { count } = props` captures a snapshot — use `props.count` in JSX or split with `<Child count={props.count} />`. `createEffect` that writes to a signal it reads needs a guard or `untrack()` — otherwise checkout preview looped until tab crash.

Store derived values in `createMemo`, not duplicated signals updated from multiple effects. Solid DevTools (when enabled) shows graph dependencies — use during first week of migration to catch non-reactive patterns code review misses.

## React-to-Solid migration pitfalls

Destructuring props breaks reactivity: `const { count } = props` captures a snapshot — use `props.count` in JSX or split with `<Child count={props.count} />`. `createEffect` that writes to a signal it reads needs a guard or `untrack()` — otherwise checkout preview looped until tab crash.

Store derived values in `createMemo`, not duplicated signals updated from multiple effects. Solid DevTools (when enabled) shows graph dependencies — use during first week of migration to catch non-reactive patterns code review misses.

## Resources

- [SolidJS documentation — reactivity guide](https://www.solidjs.com/docs/latest/guide/introduction)
- [SolidJS signals API reference](https://www.solidjs.com/docs/latest/api/basic-reactivity)
- [Fine-grained reactivity — Ryan Carniato (Solid creator)](https://dev.to/this-is-learning/solidjs-reactivity-101-1k9a)
- [SolidJS vs React benchmarks](https://krausest.github.io/js-framework-benchmark/current.html)
- [SolidJS Playground for live experimentation](https://playground.solidjs.com/)

## Failure modes specific to solidjs fine grained reactivity

Operating solidjs fine grained reactivity well means tying design choices to measurable outcomes and explicit owners. Ambiguous ownership is how pages rot.

For solidjs fine grained reactivity:
- Write the SLO and the user journey it protects
- Automate the boring verification; reserve humans for judgment calls
- Prefer progressive delivery with fast rollback over big-bang cuts
- Keep runbooks next to the code that can break

Revisit the design when the metric that justified solidjs fine grained reactivity stops moving — sunsetting is a feature.

| Signal | Target | Alarm |
|--------|--------|-------|
| Cold start p95 | Team-defined SLO | Page on burn rate |
| Throttle count | Baseline − noise | Ticket if sustained |
| Downstream timeouts | Budget cap | Weekly review |

## What reviewers should challenge in solidjs fine grained reactivity PRs

Reviewers should challenge assumptions encoded in solidjs fine grained reactivity: defaults copied from tutorials, timeouts that exceed upstream SLAs, and authz checks applied only on the primary UI path. Require a short threat or failure note in the PR when the change touches a trust boundary.

Concrete probes:
1. Scenario A for solidjs fine grained reactivity: partial dependency outage — prove clients degrade gracefully and retries do not amplify load.
2. Scenario B for solidjs fine grained reactivity: bad config shipped — prove rollback within the declared RTO without data corruption.
3. Scenario C for solidjs fine grained reactivity: traffic 3× baseline — prove autoscaling or shedding keeps the golden journey healthy.

## Rollout sequence that worked for solidjs fine grained reactivity

Roll out solidjs fine grained reactivity behind a flag or weighted route when possible. Start with internal users or a low-risk geography. Watch the signals in the table for at least one full business cycle before calling the migration done. Keep the previous path warm until error budgets stabilize.

Document the owner, the dashboard, and the single command that reverts the change. If that sentence is hard to write, the design is not ready for production traffic.

## Compliance evidence for solidjs fine grained reactivity

Detail 1 (750): for solidjs fine grained reactivity, define the contract between producers and consumers explicitly — payload shape, timeout, and idempotency key. When compliance evidence for solidjs fine grained reactivity becomes painful, it is usually because that contract was implicit.

I keep a short matrix: who can break solidjs fine grained reactivity, how we detect it within five minutes, and who is paged. Update the matrix when ownership moves. Add one synthetic check that exercises the failure path, not only the happy path. Prefer checks that run continuously over quarterly manual reviews that everyone skips under deadline pressure.

If you only remember one thing about solidjs fine grained reactivity: optimize for reversible decisions. Reversibility beats cleverness when the incident channel is busy and the blast radius is unclear.

## Developer experience when changing solidjs fine grained reactivity

Detail 2 (398): for solidjs fine grained reactivity, define the contract between producers and consumers explicitly — payload shape, timeout, and idempotency key. When developer experience when changing solidjs fine grained reactivity becomes painful, it is usually because that contract was implicit.

I keep a short matrix: who can break solidjs fine grained reactivity, how we detect it within five minutes, and who is paged. Update the matrix when ownership moves. Add one synthetic check that exercises the failure path, not only the happy path. Prefer checks that run continuously over quarterly manual reviews that everyone skips under deadline pressure.

If you only remember one thing about solidjs fine grained reactivity: optimize for reversible decisions. Reversibility beats cleverness when the incident channel is busy and the blast radius is unclear.