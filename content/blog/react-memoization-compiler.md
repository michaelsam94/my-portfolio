---
title: "The React Compiler and Memoization"
slug: "react-memoization-compiler"
description: "Understand the React Compiler (React Forget): automatic memoization, how it replaces manual useMemo and useCallback, and what it means for your codebase."
datePublished: "2025-02-17"
dateModified: "2025-02-17"
tags: ["React", "Web", "Compiler", "Performance"]
keywords: "React Compiler, React Forget, automatic memoization, useMemo useCallback, React 19 compiler, fine-grained reactivity"
faq:
  - q: "What does the React Compiler do?"
    a: "The React Compiler (formerly React Forget) analyzes component code at build time and automatically inserts memoization where it is safe and beneficial. It tracks which values and functions are stable across renders and which JSX outputs can be skipped when inputs have not changed. The goal is eliminating manual useMemo, useCallback, and React.memo without changing runtime behavior."
  - q: "Do I still need useMemo and useCallback with the React Compiler?"
    a: "In compiler-enabled projects, manual memoization becomes unnecessary for most cases the compiler handles. You may still use them for expensive computations the compiler cannot analyze — heavy data transformations, WebAssembly calls — or when integrating with libraries that require stable references. The compiler docs list escape hatches for cases it cannot optimize."
  - q: "Is the React Compiler stable for production?"
    a: "Meta uses the React Compiler in production across Instagram and other products. It is available as a Babel plugin and integrates with Next.js and Vite. Adoption requires enabling the compiler in your build config and running the ESLint plugin to flag patterns the compiler cannot handle. Start with a single route or feature flag before enabling globally."
---

You added `useCallback` to every handler, wrapped every derived value in `useMemo`, and sprinkled `React.memo` on components that still re-rendered because a parent passed a new object literal. Manual memoization in React is a whack-a-mole game where fixing one re-render often creates stale closure bugs somewhere else. The React Compiler aims to make all of that unnecessary by analyzing your components at build time and inserting precise memoization automatically.

## The problem with manual memoization

React re-renders a component when state or props change. Child components re-render too unless prevented. The manual toolkit:

- `React.memo` — skip child render if props are shallow-equal.
- `useMemo` — cache computed values between renders.
- `useCallback` — cache function references between renders.

This works but creates maintenance burden:

```tsx
// Before: manual memoization everywhere
const filtered = useMemo(
  () => items.filter(i => i.active),
  [items]
);

const handleClick = useCallback(
  (id: string) => setSelected(id),
  []
);

const MemoizedList = React.memo(ItemList);
```

Every dependency array is a future bug. Every `useCallback` with missing deps is a stale closure. Every `React.memo` on a component receiving inline objects is useless. Teams spend review time on memoization correctness instead of features.

## How the React Compiler works

The compiler runs as a Babel plugin at build time. It:

1. **Analyzes** each component's data flow — which values depend on which props and state.
2. **Determines** which computations and JSX outputs are safe to cache across renders.
3. **Inserts** automatic memoization — equivalent to optimally placed `useMemo`, `useCallback`, and `React.memo`.

```tsx
// You write this — no manual memoization
function TodoList({ items, onToggle }) {
  const active = items.filter(i => !i.done);

  return (
    <ul>
      {active.map(item => (
        <TodoItem key={item.id} item={item} onToggle={onToggle} />
      ))}
    </ul>
  );
}

// The compiler produces optimized output equivalent to:
// - memoized `active` computation (only re-filters when items change)
// - stable onToggle reference passed to TodoItem (if stable in parent)
// - TodoItem skipped when its specific item hasn't changed
```

The compiled output uses React's internal memoization cache, not `useMemo` calls in your source.

## Enabling the compiler

**Babel plugin:**

```js
// babel.config.js
module.exports = {
  plugins: [
    ["babel-plugin-react-compiler", {
      // configuration options
    }],
  ],
};
```

**Next.js:**

```js
// next.config.js
module.exports = {
  experimental: {
    reactCompiler: true,
  },
};
```

**ESLint plugin** — flags code patterns the compiler cannot optimize:

```js
// .eslintrc
{
  "plugins": ["react-compiler"],
  "rules": {
    "react-compiler/react-compiler": "error"
  }
}
```

The ESLint plugin is essential during adoption. It tells you which components need refactoring before the compiler can handle them.

## Rules of React the compiler enforces

The compiler requires components to follow the Rules of React more strictly:

- **Pure rendering** — no side effects during render (no mutations, no network calls).
- **Stable hook usage** — hooks called in the same order every render.
- **No mutating props or state** — immutable data patterns.

Code that violates these rules may not compile or may produce incorrect optimizations. The ESLint plugin catches violations at development time.

## What the compiler cannot optimize

Escape hatches remain for:

- **External mutable refs** — `useRef` values mutated without triggering re-renders.
- **Side effects in render** — code the compiler cannot reason about.
- **Third-party libraries** requiring specific reference stability contracts.
- **Extremely expensive computations** — you may still want explicit `useMemo` with custom comparison.

```tsx
// Compiler may not optimize this — explicit memoization still valid
const result = useMemo(
  () => expensiveWASMComputation(data),
  [data]
);
```

## Migration strategy

1. **Enable the ESLint plugin** — fix violations it reports.
2. **Enable the compiler on one route or feature** — compare render counts and performance.
3. **Remove manual memoization gradually** — delete `useMemo`/`useCallback`/`React.memo` where the compiler takes over.
4. **Monitor** — use React DevTools Profiler to verify re-render reduction.

Do not delete all manual memoization on day one. Verify the compiler handles each component before removing its manual caches.

## Impact on code style

The compiler enables writing natural React code without performance anxiety:

```tsx
// Clean, readable — compiler handles optimization
function ProductPage({ productId }) {
  const [quantity, setQuantity] = useState(1);
  const product = useProduct(productId);
  const total = product.price * quantity;

  return (
    <div>
      <ProductDetails product={product} />
      <QuantitySelector value={quantity} onChange={setQuantity} />
      <PriceDisplay total={total} />
    </div>
  );
}
```

No `useMemo` for `total`. No `useCallback` for `setQuantity`. No `React.memo` on child components. The compiler inserts equivalent optimizations at build time.

## Compiler opt-in and configuration

Enable incrementally — not all at once:

```javascript
// babel.config.js
module.exports = {
  plugins: [
    ['babel-plugin-react-compiler', {
      compilationMode: 'annotation',  // start with 'use memo' annotations
      // compilationMode: 'all',      // enable globally after validation
    }]
  ]
};
```

```tsx
// Opt-in per component during migration
'use memo';  // compiler optimizes this component
function ExpensiveList({ items }) { ... }

// Opt-out for problematic components
'use no memo';
function ComponentWithExternalDeps() { ... }
```

Start with `annotation` mode on hot-path components. Switch to `all` after ESLint plugin reports zero rule violations.

## ESLint plugin catches manual memo mistakes

```javascript
// eslint.config.js
import reactCompiler from 'eslint-plugin-react-compiler';

export default [
  reactCompiler.configs.recommended,
  // Flags: unnecessary useMemo, useCallback, React.memo
  // Flags: Rules of React violations that break compiler assumptions
];
```

Remove manual `useMemo`/`useCallback`/`React.memo` as compiler coverage expands — they become redundant and can conflict with compiler optimizations.

## Migration from manual memoization

```tsx
// Before: manual memoization
const MemoizedChild = React.memo(Child);
const handleClick = useCallback(() => setCount(c => c + 1), []);
const expensiveValue = useMemo(() => compute(data), [data]);

// After: compiler handles it
function Parent() {
  const handleClick = () => setCount(c => c + 1);
  const expensiveValue = compute(data);
  return <Child onClick={handleClick} value={expensiveValue} />;
}
// Compiler automatically memoizes Child, handleClick, expensiveValue
// when their dependencies haven't changed
```

Remove manual memoization incrementally. Keep `React.memo` on components with external store subscriptions until compiler coverage verified.

## Failure modes

- **Enabling globally before testing** — compiler assumptions violated; silent incorrect renders
- **Manual memo + compiler together** — conflicting optimizations; remove manual memo
- **Rules of React violations** — mutating props/state breaks compiler; ESLint plugin catches these
- **External mutable refs in render** — compiler can't track; use `use no memo` opt-out
- **Class components** — compiler only works on function components

## Production checklist

- Start with `compilationMode: 'annotation'` on hot-path components
- ESLint plugin enabled to catch Rules of React violations
- Manual useMemo/useCallback/React.memo removed as compiler coverage expands
- `use no memo` on components with external mutable dependencies
- Performance profiled before/after on identified slow components
- Switch to `compilationMode: 'all'` after zero ESLint violations

## Resources

- [React Compiler documentation](https://react.dev/learn/react-compiler)
- [React Compiler playground](https://playground.react.dev/)
- [babel-plugin-react-compiler](https://www.npmjs.com/package/babel-plugin-react-compiler)
- [eslint-plugin-react-compiler](https://www.npmjs.com/package/eslint-plugin-react-compiler)
- [React 19 release — compiler availability](https://react.dev/blog/2024/12/05/react-19)
