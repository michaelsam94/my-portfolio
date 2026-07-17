---
title: "Svelte 5 Runes and Reactivity"
slug: "svelte-5-runes-reactivity"
description: "Svelte 5 replaces implicit reactivity with explicit runes — $state, $derived, $effect. Learn the new model and how it changes component design, performance, and cross-component state sharing."
datePublished: "2025-10-05"
dateModified: "2026-07-17"
tags: ["Svelte", "JavaScript", "Frontend", "Reactivity"]
keywords: "Svelte 5 runes, $state, $derived, $effect, Svelte reactivity, Svelte 5 migration, runes vs stores, SvelteKit 2"
faq:
  - q: "Do I need to rewrite my Svelte 4 app to use runes?"
    a: "No — Svelte 5 runs Svelte 4 components in compatibility mode. You can adopt runes incrementally, file by file. New components should use runes; existing components continue working with let declarations and $: reactive statements. The Svelte team provides a migration tool (npx sv migrate svelte-5) for automated conversion of common patterns."
  - q: "How do runes compare to Svelte 4 stores?"
    a: "Runes replace most store use cases with simpler syntax. $state replaces writable stores for local and shared state. $derived replaces derived stores. For truly global cross-app state, Svelte 5 still supports stores, but runes in .svelte.js modules (universal reactivity) cover most scenarios without the subscribe/set boilerplate."
  - q: "Are runes only for .svelte files?"
    a: "No — runes work in .svelte.js and .svelte.ts files too, enabling reactive logic outside components. A cart module can export $state and $derived values that any component imports. This replaces the pattern of creating writable/derived stores in separate .ts files with cleaner, more explicit reactive modules."
faqAnswers:
  - question: "When is svelte 5 runes reactivity the wrong approach?"
    answer: "When a simpler control already covers the risk, or when the operational cost exceeds the benefit for your threat and traffic model."
  - question: "What should we measure for svelte 5 runes reactivity?"
    answer: "Pair a leading operational signal with a lagging user or risk outcome, reviewed on a fixed cadence with a named owner."
  - question: "How do we roll back svelte 5 runes reactivity safely?"
    answer: "Keep the prior artifact or config warm, rehearse the revert once in staging, and document the one-command rollback for on-call."
---
Svelte 4's reactivity was magic — assign to a `let` variable, and the DOM updates. It worked until it didn't: reactivity didn't cross function boundaries, `$:` statements confused newcomers, and sharing reactive state between files required the store ceremony (writable, subscribe, set, update). Svelte 5 replaces the magic with runes — explicit reactive primitives that work consistently everywhere.

I've migrated three components so far. The `$state` rune for a counter is clearer than `let count` with implicit reactivity. `$derived` replaces `$: doubled = count * 2` with something that reads like a computed property. `$effect` replaces `$: { document.title = count }` with an explicit side-effect block. The code is slightly more verbose and significantly more predictable.

## $state: explicit reactive variables

```svelte
<script>
  let count = $state(0);

  function increment() {
    count++;
  }
</script>

<button onclick={increment}>
  Clicked {count} times
</button>
```

`$state` wraps a value in a reactive proxy. Mutations trigger updates. For objects and arrays, deep reactivity is automatic:

```svelte
<script>
  let user = $state({ name: "Ada", scores: [95, 87, 92] });

  function addScore(score) {
    user.scores.push(score);  // reactive — no reassignment needed
  }
</script>
```

In Svelte 4, mutating object properties without reassignment didn't trigger updates unless you used `$:` or spread into a new object. `$state` tracks deep mutations natively.

## $derived: computed values

```svelte
<script>
  let count = $state(0);
  let doubled = $derived(count * 2);
  let label = $derived(`Count: ${count}, Doubled: ${doubled}`);
</script>

<p>{label}</p>
```

`$derived` recalculates when dependencies change, like Svelte 4's `$:` but with clearer semantics. For complex derivations, use `$derived.by` with a function body:

```svelte
<script>
  let items = $state([/* ... */]);
  let filter = $state("");

  let filtered = $derived.by(() => {
    const q = filter.toLowerCase();
    return items.filter(i => i.name.toLowerCase().includes(q));
  });
</script>
```

Derived values are read-only. Attempting to assign to a `$derived` value is a compile error — use `$state` for writable values.

## $effect: side effects

```svelte
<script>
  let count = $state(0);

  $effect(() => {
    document.title = `Count: ${count}`;
    console.log("Count changed to", count);
  });
</script>
```

`$effect` runs after the DOM updates when its dependencies change. It replaces Svelte 4's reactive statements used for side effects. Return a cleanup function for teardown:

```svelte
<script>
  let interval = $state(1000);

  $effect(() => {
    const id = setInterval(() => console.log("tick"), interval);
    return () => clearInterval(id);
  });
</script>
```

Effects don't run during SSR — they're client-only, like Svelte 4's `onMount` combined with reactive side effects.

## $props and $bindable: component interfaces

Svelte 5 replaces `export let` with `$props()`:

```svelte
<script>
  let { name, age = 0 } = $props();
</script>

<p>{name} is {age} years old</p>
```

Two-way binding uses `$bindable`:

```svelte
<!-- Child.svelte -->
<script>
  let { value = $bindable("") } = $props();
</script>
<input bind:value />

<!-- Parent.svelte -->
<Child bind:value={searchQuery} />
```

This replaces `export let value` with `bind:value` in Svelte 4. The `$bindable` annotation marks which props support two-way binding.

## Shared state with .svelte.js modules

Runes work outside components in universal reactive modules:

```javascript
// cart.svelte.js
let items = $state([]);
let total = $derived(items.reduce((sum, i) => sum + i.price, 0));

export function addItem(item) {
  items.push(item);
}

export function getItems() { return items; }
export function getTotal() { return total; }
```

```svelte
<script>
  import { addItem, getItems, getTotal } from "./cart.svelte.js";
</script>

<p>Total: ${getTotal()}</p>
```

Any component importing from this module shares the same reactive state — no stores, no context providers. This is the Svelte 5 answer to global state management.

## Migration from Svelte 4

Common conversions:

| Svelte 4 | Svelte 5 |
|----------|----------|
| `let count = 0` | `let count = $state(0)` |
| `$: doubled = count * 2` | `let doubled = $derived(count * 2)` |
| `$: { sideEffect() }` | `$effect(() => { sideEffect() })` |
| `export let name` | `let { name } = $props()` |
| `createEventDispatcher()` | callback props |
| `writable(0)` store | `$state(0)` in .svelte.js |

Run the migration tool: `npx sv migrate svelte-5`. Review generated changes — automated migration handles syntax but not architectural decisions about where to use universal modules vs component-local state.

Migrate `$:` reactive statements incrementally — mixing runes and legacy reactivity in one component produces silent stale UI bugs.

## $effect pitfalls

```javascript
let count = $state(0);

// BAD: infinite loop — effect writes to state it reads
$effect(() => {
  count = count + 1;
});

// GOOD: explicit dependencies, no self-write
$effect(() => {
  console.log(`count is ${count}`);
});
```

Use `$effect.pre` when you need to run before DOM updates. Use `$effect.root` for effects outside component lifecycle (advanced — prefer keeping effects in components).

## Performance with large derived state

```javascript
let items = $state([]);

// Recalculates when items OR filter changes
let filtered = $derived(items.filter(i => i.active));

// Expensive computation — still reactive, but profile it
let sorted = $derived(filtered.toSorted((a, b) => a.name.localeCompare(b.name)));
```

`$derived.by(() => ...)` for multi-line derived logic. Avoid side effects in `$derived` — use `$effect` instead.

## SSR and runes

Svelte 5 runes work with SvelteKit SSR — `$state` serializes for hydration. Pitfall: initializing `$state` from browser-only APIs in module scope breaks SSR:

```javascript
// BAD at module level
let width = $state(window.innerWidth);

// GOOD — init in $effect or onMount
let width = $state(0);
$effect(() => { width = window.innerWidth; });
```

Pair with [CSS container queries](https://blog.michaelsam94.com/css-container-queries/) for responsive layouts that complement reactive state.

## props vs export let migration

Replace export let foo with let { foo } = $props() — run migration script but manually fix components using rest props. Runes mode disables implicit props reactivity; grep codebase for dollar-dollar leftovers before enabling runes globally.

## SSR runes hydration mismatch

Ensure server and client state initial values match — hydration mismatch warnings often trace to Date.now() in initializer. Pass timestamp from loader data instead.

## Integration testing notes

Exercise the happy path plus three failure modes specific to svelte 5 runes reactivity: dependency timeout, duplicate delivery, and partial deploy during rolling update. Automated tests should assert idempotent behavior and user-visible error messages—not only HTTP 200 from mocks.

## Documentation and on-call

Link runbook steps from the service catalog entry for svelte 5 runes reactivity. On-call engineers should find rollback command, dashboard URL, and known false-positive alerts without searching Slack history. Update the entry when behavior or metrics change.

## Rollout checklist

Ship behind a feature flag when behavior is user-visible. Compare error rate and p95 latency for seven days against baseline captured before merge. Document rollback in the pull request so on-call can revert without author contact.

## Quick reference

Prefer $derived for computed state; avoid mirroring props into $state without reason. Keep a dashboard per critical user journey and review weekly during the first month after launch.

Review metrics quarterly; traffic mix shifts can invert prior wins without code changes.

Capture baseline p75 latency and error rate one week before merge; compare seven days post-deploy by mobile and region.

## Resources

- [Svelte 5 announcement and runes docs](https://svelte.dev/docs/svelte/what-are-runes)
- [$state rune reference](https://svelte.dev/docs/svelte/$state)
- [$derived rune reference](https://svelte.dev/docs/svelte/$derived)
- [Svelte 5 migration guide](https://svelte.dev/docs/svelte/v5-migration-guide)
- [Universal reactivity in .svelte.js files](https://svelte.dev/docs/svelte/svelte-js-files)

## Field notes on svelte 5 runes reactivity

Operating svelte 5 runes reactivity well means tying design choices to measurable outcomes and explicit owners. Ambiguous ownership is how pages rot.

For svelte 5 runes reactivity:
- Write the SLO and the user journey it protects
- Automate the boring verification; reserve humans for judgment calls
- Prefer progressive delivery with fast rollback over big-bang cuts
- Keep runbooks next to the code that can break

Revisit the design when the metric that justified svelte 5 runes reactivity stops moving — sunsetting is a feature.

| Signal | Target | Alarm |
|--------|--------|-------|
| Latency p99 | Team-defined SLO | Page on burn rate |
| Error rate | Baseline − noise | Ticket if sustained |
| Cost per 1k ops | Budget cap | Weekly review |

## Ownership and on-call for svelte 5 runes reactivity

Reviewers should challenge assumptions encoded in svelte 5 runes reactivity: defaults copied from tutorials, timeouts that exceed upstream SLAs, and authz checks applied only on the primary UI path. Require a short threat or failure note in the PR when the change touches a trust boundary.

Concrete probes:
1. Scenario A for svelte 5 runes reactivity: partial dependency outage — prove clients degrade gracefully and retries do not amplify load.
2. Scenario B for svelte 5 runes reactivity: bad config shipped — prove rollback within the declared RTO without data corruption.
3. Scenario C for svelte 5 runes reactivity: traffic 3× baseline — prove autoscaling or shedding keeps the golden journey healthy.

## Anti-patterns unique to svelte 5 runes reactivity

Roll out svelte 5 runes reactivity behind a flag or weighted route when possible. Start with internal users or a low-risk geography. Watch the signals in the table for at least one full business cycle before calling the migration done. Keep the previous path warm until error budgets stabilize.

Document the owner, the dashboard, and the single command that reverts the change. If that sentence is hard to write, the design is not ready for production traffic.

## Caching interactions with svelte 5 runes reactivity

Detail 1 (800): for svelte 5 runes reactivity, define the contract between producers and consumers explicitly — payload shape, timeout, and idempotency key. When caching interactions with svelte 5 runes reactivity becomes painful, it is usually because that contract was implicit.

I keep a short matrix: who can break svelte 5 runes reactivity, how we detect it within five minutes, and who is paged. Update the matrix when ownership moves. Add one synthetic check that exercises the failure path, not only the happy path. Prefer checks that run continuously over quarterly manual reviews that everyone skips under deadline pressure.

If you only remember one thing about svelte 5 runes reactivity: optimize for reversible decisions. Reversibility beats cleverness when the incident channel is busy and the blast radius is unclear.

## Multi-tenant concerns in svelte 5 runes reactivity

Detail 2 (721): for svelte 5 runes reactivity, define the contract between producers and consumers explicitly — payload shape, timeout, and idempotency key. When multi-tenant concerns in svelte 5 runes reactivity becomes painful, it is usually because that contract was implicit.

I keep a short matrix: who can break svelte 5 runes reactivity, how we detect it within five minutes, and who is paged. Update the matrix when ownership moves. Add one synthetic check that exercises the failure path, not only the happy path. Prefer checks that run continuously over quarterly manual reviews that everyone skips under deadline pressure.

If you only remember one thing about svelte 5 runes reactivity: optimize for reversible decisions. Reversibility beats cleverness when the incident channel is busy and the blast radius is unclear.