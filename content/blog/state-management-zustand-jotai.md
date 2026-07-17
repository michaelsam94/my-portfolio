---
title: "State Management with Zustand and Jotai"
slug: "state-management-zustand-jotai"
description: "Zustand offers simple global stores with minimal boilerplate; Jotai provides atomic bottom-up state composition. Compare both libraries and learn when to pick each for React apps."
datePublished: "2025-09-20"
dateModified: "2026-07-17"
tags:
  - "Engineering"
keywords: "Zustand vs Jotai, React state management, atomic state, Zustand store, Jotai atoms, lightweight React state, global state 2026"
faq:
  - q: "Should I use Zustand or Jotai for a new React project?"
    a: "Use Zustand when you need a few global stores with straightforward read/write semantics — auth state, cart, UI preferences. Use Jotai when state is highly derived, shared across distant component trees in granular pieces, or when you want colocated atoms that compose bottom-up. Many teams use both: Zustand for app-wide stores, Jotai for feature-local reactive state."
  - q: "Do Zustand and Jotai replace React Context?"
    a: "For performance-sensitive global state, yes. Context re-renders every consumer when any value changes, which becomes a bottleneck with frequent updates. Both libraries use subscription models that re-render only components reading changed slices. Keep Context for dependency injection, theme providers, and infrequently changing configuration — not for live counters or form state."
  - q: "How do Zustand and Jotai compare to Redux Toolkit?"
    a: "Redux Toolkit adds structure — actions, reducers, middleware, DevTools — at the cost of boilerplate. Zustand is a single create() call with a set function. Jotai is atoms with no actions or reducers at all. Choose Redux when you need time-travel debugging, strict action logging, or a large team that benefits from enforced patterns. Choose Zustand or Jotai when you want less ceremony and faster iteration."
faqAnswers:
  - question: "When is state management zustand jotai the wrong approach?"
    answer: "When a simpler control already covers the risk, or when the operational cost exceeds the benefit for your threat and traffic model."
  - question: "What should we measure for state management zustand jotai?"
    answer: "Pair a leading operational signal with a lagging user or risk outcome, reviewed on a fixed cadence with a named owner."
  - question: "How do we roll back state management zustand jotai safely?"
    answer: "Keep the prior artifact or config warm, rehearse the revert once in staging, and document the one-command rollback for on-call."
---
Redux powered our dashboard for three years. By year two, adding a boolean flag required an action type, action creator, reducer case, selector, and a PR comment thread about naming conventions. When we rewrote the notification panel with Zustand, the entire store — state, actions, selectors — fit in forty lines. The Jotai rewrite of our filter system went further: each filter became an independent atom, and components subscribed only to the atoms they read.

Zustand and Jotai are the two lightweight alternatives that won the post-Redux era for React. Both avoid Context's re-render problem. Both work with React 19 and Server Components (with boundaries). They differ in mental model: Zustand is top-down stores; Jotai is bottom-up atoms.

## Zustand: global stores without ceremony

Zustand creates a store with `create()`, returns a hook, and lets you read/write state directly:

```tsx
import { create } from "zustand";

interface CartStore {
  items: CartItem[];
  addItem: (item: CartItem) => void;
  removeItem: (id: string) => void;
  total: () => number;
}

const useCart = create<CartStore>((set, get) => ({
  items: [],
  addItem: (item) => set((s) => ({ items: [...s.items, item] })),
  removeItem: (id) => set((s) => ({ items: s.items.filter(i => i.id !== id) })),
  total: () => get().items.reduce((sum, i) => sum + i.price * i.qty, 0),
}));

// In a component — only re-renders when items change:
function CartBadge() {
  const count = useCart((s) => s.items.length);
  return <span>{count}</span>;
}
```

The selector `(s) => s.items.length` is critical. Without it, every state change re-renders every subscriber. With it, only length changes trigger updates.

Zustand supports middleware for persistence, DevTools, and immer-based immutable updates:

```tsx
import { persist } from "zustand/middleware";

const useSettings = create(
  persist<SettingsStore>(
    (set) => ({
      theme: "dark",
      setTheme: (theme) => set({ theme }),
    }),
    { name: "app-settings" }
  )
);
```

For most apps, two to four Zustand stores cover auth, cart, UI chrome, and feature flags. Resist creating a store per component — that's what local `useState` is for.

## Jotai: atomic state composition

Jotai models state as atoms — independent reactive units that compose:

```tsx
import { atom, useAtom, useAtomValue } from "jotai";

const countAtom = atom(0);
const doubleAtom = atom((get) => get(countAtom) * 2);

function Counter() {
  const [count, setCount] = useAtom(countAtom);
  const doubled = useAtomValue(doubleAtom);
  return (
    <div>
      <p>{count} × 2 = {doubled}</p>
      <button onClick={() => setCount(c => c + 1)}>+1</button>
    </div>
  );
}
```

Derived atoms recalculate only when their dependencies change. A component reading `doubleAtom` doesn't re-render when unrelated atoms update — finer granularity than Zustand selectors in complex dependency graphs.

Async atoms handle data fetching without useEffect boilerplate:

```tsx
const userIdAtom = atom<string | null>(null);
const userAtom = atom(async (get) => {
  const id = get(userIdAtom);
  if (!id) return null;
  const res = await fetch(`/api/users/${id}`);
  return res.json();
});

function UserProfile() {
  const user = useAtomValue(userAtom);
  // Suspense boundary handles loading state
  return <h1>{user.name}</h1>;
}
```

Jotai integrates with React Suspense natively — async atoms suspend while loading, and error boundaries catch failures.

## When to pick which

**Choose Zustand when:**
- State is naturally grouped (auth session, shopping cart, app settings).
- You want a familiar store pattern with actions and getters.
- The team prefers explicit, centralized state over scattered atoms.
- You need middleware (persist, devtools, immer) with minimal setup.

**Choose Jotai when:**
- State has complex derivation chains (filters → sorted results → pagination).
- Different parts of the tree need different slices of the same data.
- You want colocated state next to the components that define it.
- Async data dependencies form a graph (atom A feeds atom B feeds atom C).

## Combining both libraries

They're not mutually exclusive. A common pattern:

```tsx
// Zustand for app-wide auth
const useAuth = create(...);

// Jotai atoms derived from auth for feature-specific state
const permissionsAtom = atom((get) => {
  const user = useAuth.getState().user;
  return computePermissions(user);
});
```

Use Zustand for write-heavy global stores. Use Jotai for read-heavy derived state that many components consume in different combinations.

## Performance and React 19 considerations

Both libraries use `useSyncExternalStore` under the hood, making them compatible with React 18 concurrent features and React 19. Neither causes the tearing issues that plagued early external store implementations.

For Server Components, neither library runs on the server — wrap client components that consume stores in `"use client"` boundaries. Pass server-fetched data as props to seed initial store state on hydration:

```tsx
"use client";
function CartProvider({ initialItems, children }) {
  useEffect(() => {
    useCart.setState({ items: initialItems });
  }, []);
  return children;
}
```

## Implementation depth (1)

Engineering teams shipping state management zustand jotai benefit from treating boundaries as contracts: document inputs, outputs, failure modes, and rollback before wide rollout. Measure p75 latency on mid-tier mobile over throttled 4G — desktop lab metrics hide real user pain. Pair client changes with server and cache alignment; fast UI on slow APIs still feels broken. Exercise refresh, back navigation, double submit, offline recovery, and keyboard-only paths in QA before promoting to production traffic.

## Implementation depth (2)

Engineering teams shipping state management zustand jotai benefit from treating boundaries as contracts: document inputs, outputs, failure modes, and rollback before wide rollout. Measure p75 latency on mid-tier mobile over throttled 4G — desktop lab metrics hide real user pain. Pair client changes with server and cache alignment; fast UI on slow APIs still feels broken. Exercise refresh, back navigation, double submit, offline recovery, and keyboard-only paths in QA before promoting to production traffic.

## Implementation depth (3)

Engineering teams shipping state management zustand jotai benefit from treating boundaries as contracts: document inputs, outputs, failure modes, and rollback before wide rollout. Measure p75 latency on mid-tier mobile over throttled 4G — desktop lab metrics hide real user pain. Pair client changes with server and cache alignment; fast UI on slow APIs still feels broken. Exercise refresh, back navigation, double submit, offline recovery, and keyboard-only paths in QA before promoting to production traffic.

## A concrete playbook for state management zustand jotai

Treat state management zustand jotai as a product capability with an owner, a dashboard, and a rollback plan. Define the user-visible success metric before debating tools.

### Delivery

Ship behind a flag when blast radius is high. Prefer managed services for undifferentiated heavy lifting. Document the escape hatch for teams that cannot adopt state management zustand jotai yet — and review escape hatches quarterly.

### Operability

Alerts should page on symptoms users feel, not on every internal retry. Link runbooks from alerts. After incidents involving state management zustand jotai, add one test or one alert that would have shortened detection.

### Knowledge

Keep a short FAQ in frontmatter synchronized with reality. Outdated answers are worse than none. Point to primary sources (RFCs, vendor docs) in Resources rather than secondary blog summaries when behavior is subtle.

## Validation scenarios for state management zustand jotai

Before calling state management zustand jotai done, exercise these scenarios in a staging environment that mirrors production identity, data volume, and failure injection:

1. **Happy path** with production-like payload sizes.
2. **Auth failure** — expired token, missing scope, revoked session.
3. **Dependency down** — timeout the primary collaborator; confirm degraded mode or clear error.
4. **Replay / duplicate** — submit the same event or request twice; confirm idempotency.
5. **Rollback** — disable the flag or revert the deploy; confirm state converges.

Capture traces for each scenario and store them next to the runbook for state management zustand jotai.

## Ownership and interfaces

Name the producing and consuming teams for state management zustand jotai. Publish the API/event contract with versioning rules. If you need a breaking change, run dual-write or dual-read long enough for consumers to migrate. Silent breakages erode trust faster than slow features.

## Resources

- [Zustand documentation](https://docs.pmnd.rs/zustand/getting-started/introduction)
- [Jotai documentation](https://jotai.org/docs/introduction)
- [Zustand vs Jotai comparison — Poimandres](https://docs.pmnd.rs/)
- [React useSyncExternalStore docs](https://react.dev/reference/react/useSyncExternalStore)
- [Jotai async atoms and Suspense](https://jotai.org/docs/guides/async)