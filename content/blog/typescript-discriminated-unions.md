---
title: "Discriminated Unions in Practice"
slug: "typescript-discriminated-unions"
description: "Model domain state with TypeScript discriminated unions: exhaustiveness checking, narrowing patterns, API response typing, and Redux-style action design."
datePublished: "2026-02-15"
dateModified: "2026-07-17"
tags: ["TypeScript", "Web", "Type Safety", "Architecture"]
keywords: "discriminated unions, tagged unions, TypeScript narrowing, exhaustiveness, union types, algebraic data types"
faq:
  - q: "What is a discriminated union in TypeScript?"
    a: "A discriminated union is a union of object types that share a common literal property — the discriminant — which TypeScript uses to narrow the type in conditional branches. When you check if status === 'loading', TypeScript knows the object has loading-specific fields. When you check status === 'error', it knows about the error field. This gives you compile-time safety for state machines and variant data without class hierarchies."
  - q: "How does exhaustiveness checking work with discriminated unions?"
    a: "When you switch on the discriminant and handle every case, TypeScript verifies all variants are covered. If you add a new variant to the union and forget to handle it, the compiler errors on the default branch. The never type in the default case is the standard pattern: if control reaches default, the value should be never, and assigning a non-never type to never is a compile error."
  - q: "When should I use discriminated unions instead of optional properties?"
    a: "Use discriminated unions when exactly one set of properties is valid at a time — a request is either loading, succeeded, or failed, not all three simultaneously. Optional properties (status plus optional error plus optional data) allow impossible states like { status: 'success', error: '...' }. Discriminated unions make invalid states unrepresentable, which is the core principle of algebraic data type modeling."
faqAnswers:
  - question: "When is typescript discriminated unions the wrong approach?"
    answer: "When a simpler control already covers the risk, or when the operational cost exceeds the benefit for your threat and traffic model."
  - question: "What should we measure for typescript discriminated unions?"
    answer: "Pair a leading operational signal with a lagging user or risk outcome, reviewed on a fixed cadence with a named owner."
  - question: "How do we roll back typescript discriminated unions safely?"
    answer: "Keep the prior artifact or config warm, rehearse the revert once in staging, and document the one-command rollback for on-call."
---
A React component I reviewed had this state type:

```typescript
interface FetchState {
  loading: boolean;
  data?: User[];
  error?: string;
}
```

It had four possible combinations. Three were valid. One — `loading: false, error: undefined, data: undefined` — represented "idle" but wasn't distinguished from "success with empty data." Bugs followed. Replacing it with a discriminated union eliminated the ambiguous state entirely and let the compiler force every render branch to handle every case. That refactor is the single pattern I reach for most often when modeling state in TypeScript.

## The pattern

Each variant shares a literal discriminant field:

```typescript
type FetchState<T> =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "success"; data: T }
  | { status: "error"; error: string };
```

Only one variant exists at a time. `loading` and `error` never coexist. `data` only exists when `status` is `"success"`.

## Narrowing in practice

TypeScript narrows automatically on the discriminant:

```typescript
function renderUsers(state: FetchState<User[]>) {
  switch (state.status) {
    case "idle":
      return <p>Click to load users</p>;
    case "loading":
      return <Spinner />;
    case "success":
      return <UserList users={state.data} />;  // data is User[]
    case "error":
      return <Alert message={state.error} />;   // error is string
  }
}
```

No optional chaining. No `state.data?.` guards. Each branch has exactly the fields that make sense.

## Exhaustiveness checking

Add a `never` default to catch unhandled variants:

```typescript
function assertNever(value: never): never {
  throw new Error(`Unhandled case: ${JSON.stringify(value)}`);
}

function handle(state: FetchState<User>) {
  switch (state.status) {
    case "idle":    return init();
    case "loading": return wait();
    case "success": return show(state.data);
    case "error":   return retry(state.error);
    default:
      return assertNever(state);
  }
}
```

Add `{ status: "cancelled" }` to the union and the `default` branch errors because `state` is no longer `never` — it's the new variant. The compiler tells you exactly where to add handling.

## API response typing

Backend responses are naturally discriminated:

```typescript
type ApiResponse<T> =
  | { ok: true; data: T }
  | { ok: false; error: { code: string; message: string } };

async function fetchUser(id: string): Promise<ApiResponse<User>> {
  const res = await fetch(`/api/users/${id}`);
  return res.json();
}

const result = await fetchUser("123");

if (result.ok) {
  console.log(result.data.name);     // User
} else {
  console.error(result.error.code);  // string
}
```

No `if (result.data)` followed by `if (result.error)` with both possibly undefined. The `ok` field tells you which shape you have.

## Redux-style actions

The original motivating use case for discriminated unions in TypeScript:

```typescript
type Action =
  | { type: "ADD_TODO"; text: string }
  | { type: "TOGGLE_TODO"; id: string }
  | { type: "DELETE_TODO"; id: string }
  | { type: "SET_FILTER"; filter: "all" | "active" | "completed" };

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case "ADD_TODO":
      return { ...state, todos: [...state.todos, { text: action.text }] };
    case "TOGGLE_TODO":
      return { ...state, todos: toggle(state.todos, action.id) };
    case "DELETE_TODO":
      return { ...state, todos: remove(state.todos, action.id) };
    case "SET_FILTER":
      return { ...state, filter: action.filter };
    default:
      return assertNever(action);
  }
}
```

Each action carries exactly the payload it needs. `action.text` is only available in the `ADD_TODO` branch. Modern state libraries (Zustand, Jotai) benefit from the same pattern even without a formal reducer.

## Combining with generics

Discriminated unions work well with generic result types:

```typescript
type Result<T, E = Error> =
  | { success: true; value: T }
  | { success: false; reason: E };

function parseJSON<T>(raw: string): Result<T, "SYNTAX_ERROR" | "SCHEMA_MISMATCH"> {
  try {
    const parsed = JSON.parse(raw);
    return { success: true, value: parsed };
  } catch {
    return { success: false, reason: "SYNTAX_ERROR" };
  }
}
```

Callers must check `success` before accessing `value` or `reason`. The compiler enforces it.

## Modeling complex UI state

A multi-step form with discriminated steps:

```typescript
type FormStep =
  | { step: "contact"; email: string; phone: string }
  | { step: "address"; street: string; city: string; zip: string }
  | { step: "review"; confirmed: boolean }
  | { step: "submitted"; orderId: string };

function FormWizard({ state }: { state: FormStep }) {
  switch (state.step) {
    case "contact":
      return <ContactForm email={state.email} phone={state.phone} />;
    case "address":
      return <AddressForm street={state.street} city={state.city} zip={state.zip} />;
    case "review":
      return <ReviewPanel confirmed={state.confirmed} />;
    case "submitted":
      return <Confirmation orderId={state.orderId} />;
  }
}
```

Each step component receives exactly the data for its step. No prop drilling of the entire form state.

## Migration from optional properties

To refactor an existing interface:

1. Identify the discriminant (usually `status`, `type`, or `kind`)
2. List all valid combinations of properties
3. Create one variant per combination
4. Replace `if (state.data)` chains with `switch (state.status)`
5. Add `assertNever` default

The upfront cost is small. The ongoing benefit is that new states can't be added without the compiler pointing at every place that needs updating.

## React rendering with exhaustive switches

Map async state to UI with a single switch — TypeScript verifies every variant:

```tsx
function OrderPanel({ state }: { state: AsyncState<Order> }) {
  switch (state.status) {
    case "idle": return null;
    case "loading": return <Spinner />;
    case "success": return <Receipt order={state.data} />;
    case "error": return <Alert message={state.error} />;
    default: return assertNever(state);
  }
}
```

Adding `"pending_payment"` to the union without a case errors at compile time — before QA finds a blank screen.

## JSON deserialization caveat

Runtime JSON will not automatically match discriminated unions — validate at boundaries with Zod or similar and construct typed objects. TypeScript narrowing applies after you have proven the discriminant field matches a known literal; trust parsed data, not raw `JSON.parse` casts.

## Serialization round-trip

When persisting discriminated unions to JSON, validate discriminant on read:

```typescript
function parseEvent(raw: unknown): Event {
  const o = EventSchema.parse(raw);
  switch (o.type) {
    case "click": return o;
    case "submit": return o;
    default: return assertNever(o);
  }
}
```

Zod `.discriminatedUnion("type", [...])` generates parser and TypeScript type together — single source of truth.

## Edge cases in typescript discriminated unions

TypeScript techniques in typescript discriminated unions pay off when they encode invariants the compiler can check. Prefer types that make illegal states unrepresentable over sprawling `any` escapes.

### Migration tactics

Enable `strict` incrementally: start with new packages, then tighten `noImplicitAny`, then `strictNullChecks` on legacy modules behind a burn-down list. Track error counts per package weekly.

### Patterns that scale

Branded types for IDs, discriminated unions for results, and `satisfies` for config objects keep refactors safe. Utility types (`Pick`, `Omit`, `ReturnType`) reduce duplication without inventing a parallel type language.

### Tooling

`tsc --noEmit` in CI, ESLint type-aware rules sparingly (they are slow), and API extractors for public packages. Generate types from OpenAPI/Zod when runtime validation must match compile-time types for typescript discriminated unions.

## Validation scenarios for typescript discriminated unions

Before calling typescript discriminated unions done, exercise these scenarios in a staging environment that mirrors production identity, data volume, and failure injection:

1. **Happy path** with production-like payload sizes.
2. **Auth failure** — expired token, missing scope, revoked session.
3. **Dependency down** — timeout the primary collaborator; confirm degraded mode or clear error.
4. **Replay / duplicate** — submit the same event or request twice; confirm idempotency.
5. **Rollback** — disable the flag or revert the deploy; confirm state converges.

Capture traces for each scenario and store them next to the runbook for typescript discriminated unions.

## Ownership and interfaces

Name the producing and consuming teams for typescript discriminated unions. Publish the API/event contract with versioning rules. If you need a breaking change, run dual-write or dual-read long enough for consumers to migrate. Silent breakages erode trust faster than slow features.

## Resources

- [TypeScript Handbook: Narrowing](https://www.typescriptlang.org/docs/handbook/2/narrowing.html)
- [TypeScript Handbook: Discriminated Unions](https://www.typescriptlang.org/docs/handbook/2/narrowing.html#discriminated-unions)
- [Exhaustiveness checking (TypeScript docs)](https://www.typescriptlang.org/docs/handbook/2/narrowing.html#exhaustiveness-checking)
- [Making illegal states unrepresentable](https://blog.janestreet.com/effective-ml-video/)
- [Redux TypeScript usage guide](https://redux.js.org/usage/usage-with-typescript)
## Exhaustive never

`default: const _x: never = x` forces new union members handled.