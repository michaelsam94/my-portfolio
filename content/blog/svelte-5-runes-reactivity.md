---
title: "Svelte 5 Runes and Reactivity"
slug: "svelte-5-runes-reactivity"
description: "Svelte 5 replaces implicit reactivity with explicit runes — $state, $derived, $effect. Learn the new model and how it changes component design, performance, and cross-component state sharing."
datePublished: "2025-10-05"
dateModified: "2025-10-05"
tags: ["Svelte", "JavaScript", "Frontend", "Reactivity"]
keywords: "Svelte 5 runes, $state, $derived, $effect, Svelte reactivity, Svelte 5 migration, runes vs stores, SvelteKit 2"
faq:
  - q: "Do I need to rewrite my Svelte 4 app to use runes?"
    a: "No — Svelte 5 runs Svelte 4 components in compatibility mode. You can adopt runes incrementally, file by file. New components should use runes; existing components continue working with let declarations and $: reactive statements. The Svelte team provides a migration tool (npx sv migrate svelte-5) for automated conversion of common patterns."
  - q: "How do runes compare to Svelte 4 stores?"
    a: "Runes replace most store use cases with simpler syntax. $state replaces writable stores for local and shared state. $derived replaces derived stores. For truly global cross-app state, Svelte 5 still supports stores, but runes in .svelte.js modules (universal reactivity) cover most scenarios without the subscribe/set boilerplate."
  - q: "Are runes only for .svelte files?"
    a: "No — runes work in .svelte.js and .svelte.ts files too, enabling reactive logic outside components. A cart module can export $state and $derived values that any component imports. This replaces the pattern of creating writable/derived stores in separate .ts files with cleaner, more explicit reactive modules."
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

## Common production mistakes

Teams get 5 runes reactivity wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of 5 runes reactivity fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Resources

- [Svelte 5 announcement and runes docs](https://svelte.dev/docs/svelte/what-are-runes)
- [$state rune reference](https://svelte.dev/docs/svelte/$state)
- [$derived rune reference](https://svelte.dev/docs/svelte/$derived)
- [Svelte 5 migration guide](https://svelte.dev/docs/svelte/v5-migration-guide)
- [Universal reactivity in .svelte.js files](https://svelte.dev/docs/svelte/svelte-js-files)
