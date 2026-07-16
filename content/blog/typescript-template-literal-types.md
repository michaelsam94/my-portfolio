---
title: "Template Literal Types"
slug: "typescript-template-literal-types"
description: "Build type-safe string patterns with TypeScript template literal types: route builders, CSS property types, event name parsing, and string manipulation at the type level."
datePublished: "2026-02-23"
dateModified: "2026-02-23"
tags: ["TypeScript", "Web", "Type Safety", "Advanced Types"]
keywords: "template literal types, TypeScript, string manipulation types, type-level strings, route types"
faq:
  - q: "What are template literal types in TypeScript?"
    a: "Template literal types apply the same string interpolation syntax used in JavaScript template literals to the type system. A type like `hello ${string}` matches any string starting with 'hello '. Combined with union types, they can generate combinatorial string patterns — for example, prefixing every member of a union with a common string — enabling type-safe APIs for CSS properties, event names, route paths, and database column names."
  - q: "How do template literal types work with unions?"
    a: "When a template literal type contains a union, TypeScript distributes over each member, producing a new union of all combinations. If Color is 'red' | 'blue' and you define type ClassName = `bg-${Color}`, the result is 'bg-red' | 'bg-blue'. This combinatorial generation is the core technique for building exhaustive string unions from smaller primitive unions without manually listing every combination."
  - q: "Can template literal types parse strings at the type level?"
    a: "Yes, using infer in conditional types combined with template literal pattern matching. TypeScript can extract substrings from a template pattern — for example, parsing '/users/:id' to extract 'id' as a parameter name. This enables type-safe route definitions where the path string determines the required parameter types. The parsing happens entirely at compile time with no runtime overhead."
---

I wanted a function `on(eventName, handler)` where the event name `"user:created"` automatically typed the handler as `(payload: { id: string }) => void`. Without template literal types, I'd have maintained a manual map and hoped it stayed in sync. With them, I defined the event pattern `` `${string}:created` `` and let the compiler derive the rest. Template literal types bring string manipulation into the type system — and they're the foundation for some of the most ergonomic APIs in modern TypeScript libraries.

## Basic syntax

```typescript
type Greeting = `Hello, ${string}`;

const a: Greeting = "Hello, world";  // OK
const b: Greeting = "Goodbye";         // Error
```

The `${string}` is a type-level wildcard matching any string.

## Combinatorial generation from unions

The killer feature — generate all combinations:

```typescript
type Color = "red" | "green" | "blue";
type Size = "sm" | "lg";

type ColorClass = `text-${Color}`;
// "text-red" | "text-green" | "text-blue"

type Variant = `${Size}-${Color}`;
// "sm-red" | "sm-green" | "sm-blue" | "lg-red" | "lg-green" | "lg-blue"
```

Six variants from two unions of three and two members. Add a color and the class union grows automatically.

## CSS and design system types

```typescript
type Spacing = 0 | 1 | 2 | 4 | 8 | 16;
type Side = "t" | "r" | "b" | "l";

type MarginClass = `m${Side}-${Spacing}`;
// "mt-0" | "mt-1" | ... | "ml-16"

type CssValue = `${number}px` | `${number}%` | `${number}rem`;

function style(property: string, value: CssValue): string {
  return `${property}: ${value}`;
}

style("width", "100%");    // OK
style("width", "100");     // Error: not a valid CssValue
```

## Parsing routes with infer

Extract parameter names from path strings:

```typescript
type ExtractParams<T extends string> =
  T extends `${infer _Start}:${infer Param}/${infer Rest}`
    ? Param | ExtractParams<`/${Rest}`>
    : T extends `${infer _Start}:${infer Param}`
    ? Param
    : never;

type Params1 = ExtractParams<"/users/:id">;
// "id"

type Params2 = ExtractParams<"/users/:userId/orders/:orderId">;
// "userId" | "orderId"
```

Build a type-safe router:

```typescript
type Routes = {
  "/users": void;
  "/users/:id": { id: string };
  "/users/:id/posts": { id: string };
};

type ParamsFor<Route extends keyof Routes> =
  ExtractParams<Route & string> extends never
    ? Record<string, never>
    : { [K in ExtractParams<Route & string>]: string };

function navigate<Route extends keyof Routes>(
  path: Route,
  ...args: ParamsFor<Route> extends Record<string, never>
    ? []
    : [params: ParamsFor<Route>]
): void {
  // implementation
}

navigate("/users");                          // OK, no params
navigate("/users/:id", { id: "123" });       // OK
navigate("/users/:id");                      // Error: missing params
navigate("/users/:id", { id: 123 });        // Error: id must be string
```

## Event name patterns

```typescript
type EventFamily = "user" | "order" | "payment";
type EventAction = "created" | "updated" | "deleted";

type EventName = `${EventFamily}:${EventAction}`;
// "user:created" | "user:updated" | ... (9 combinations)

type EventPayload<E extends EventName> =
  E extends `${infer Family}:created`
    ? Family extends "user" ? { id: string; name: string }
    : Family extends "order" ? { orderId: string; total: number }
    : { ref: string }
    : { id: string };

function on<E extends EventName>(
  event: E,
  handler: (payload: EventPayload<E>) => void
): void { /* ... */ }

on("user:created", (p) => console.log(p.name));    // p has name
on("order:created", (p) => console.log(p.total));    // p has total
```

## String manipulation utilities

TypeScript provides built-in intrinsic string manipulation types:

```typescript
type Upper = Uppercase<"hello">;       // "HELLO"
type Lower = Lowercase<"HELLO">;       // "hello"
type Cap = Capitalize<"hello">;        // "Hello"
type Uncap = Uncapitalize<"Hello">;    // "hello"
```

Combine with template literals:

```typescript
type GetterNames<T extends string> = `get${Capitalize<T>}`;

type Props = "name" | "age" | "email";
type Getters = GetterNames<Props>;
// "getName" | "getAge" | "getEmail"
```

## Database column naming

```typescript
type Table = "users" | "orders" | "products";
type Column<T extends Table> =
  T extends "users" ? "id" | "name" | "email"
  : T extends "orders" ? "id" | "total" | "status"
  : "id" | "title" | "price";

type ColumnRef<T extends Table, C extends Column<T>> = `${T}.${C}`;

type Ref1 = ColumnRef<"users", "name">;     // "users.name"
type Ref2 = ColumnRef<"orders", "total">;   // "orders.total"
type Ref3 = ColumnRef<"users", "total">;    // Error
```

## Practical limits

Template literal types are powerful but can slow compilation when unions explode combinatorially. A union of 10 colors × 10 sizes × 10 variants = 1,000 members — fine. 50 × 50 × 50 = 125,000 — the compiler will struggle. Keep generating unions to a few hundred members. For larger sets, use `string` with runtime validation instead.

## Route type safety example

```typescript
type Route = `/users/${string}` | `/orders/${number}`;
type ApiPath = `/api/v1${Route}`;

function fetchApi(path: ApiPath): Promise<Response> {
  return fetch(path);
}
fetchApi("/api/v1/users/alice");  // OK
fetchApi("/api/v1/unknown");       // Type error
```

Combine with `as const` object maps for event names and Redis channel patterns.

## Common production mistakes

Teams get template literal types wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

TypeScript patterns for template literal types erode when `any` escapes during deadlines, generic constraints are loosened instead of modeling domain invariants, and strict mode is disabled file-by-file without a migration plan.

## Debugging and triage workflow

When template literal types misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [TypeScript Handbook: Template Literal Types](https://www.typescriptlang.org/docs/handbook/2/template-literal-types.html)
- [TypeScript 4.1 Release Notes](https://www.typescriptlang.org/docs/handbook/release-notes/typescript-4-1.html#template-literal-types)
- [TypeScript 4.8 Improved intersection inference](https://www.typescriptlang.org/docs/handbook/release-notes/typescript-4-8.html)
- [type-fest string utility types](https://github.com/sindresorhus/type-fest)
- [ts-pattern route typing example](https://github.com/gvergnaud/ts-pattern)
