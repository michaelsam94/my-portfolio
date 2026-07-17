---
title: "Template Literal Types"
slug: "typescript-template-literal-types"
description: "Build type-safe string patterns with TypeScript template literal types: route builders, CSS property types, event name parsing, and string manipulation at the type level."
datePublished: "2026-02-23"
dateModified: "2026-07-17"
tags: ["TypeScript", "Web", "Type Safety", "Advanced Types"]
keywords: "template literal types, TypeScript, string manipulation types, type-level strings, route types"
faq:
  - q: "What are template literal types in TypeScript?"
    a: "Template literal types apply the same string interpolation syntax used in JavaScript template literals to the type system. A type like `hello ${string}` matches any string starting with 'hello '. Combined with union types, they can generate combinatorial string patterns — for example, prefixing every member of a union with a common string — enabling type-safe APIs for CSS properties, event names, route paths, and database column names."
  - q: "How do template literal types work with unions?"
    a: "When a template literal type contains a union, TypeScript distributes over each member, producing a new union of all combinations. If Color is 'red' | 'blue' and you define type ClassName = `bg-${Color}`, the result is 'bg-red' | 'bg-blue'. This combinatorial generation is the core technique for building exhaustive string unions from smaller primitive unions without manually listing every combination."
  - q: "Can template literal types parse strings at the type level?"
    a: "Yes, using infer in conditional types combined with template literal pattern matching. TypeScript can extract substrings from a template pattern — for example, parsing '/users/:id' to extract 'id' as a parameter name. This enables type-safe route definitions where the path string determines the required parameter types. The parsing happens entirely at compile time with no runtime overhead."
faqAnswers:
  - question: "When is typescript template literal types the wrong approach?"
    answer: "When a simpler control already covers the risk, or when the operational cost exceeds the benefit for your threat and traffic model."
  - question: "What should we measure for typescript template literal types?"
    answer: "Pair a leading operational signal with a lagging user or risk outcome, reviewed on a fixed cadence with a named owner."
  - question: "How do we roll back typescript template literal types safely?"
    answer: "Keep the prior artifact or config warm, rehearse the revert once in staging, and document the one-command rollback for on-call."
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

## HTTP method + path pairs

```typescript
type Method = "GET" | "POST";
type Route = "/users" | "/orders";
type Endpoint = `${Method} ${Route}`;

const allowed: Endpoint[] = ["GET /users", "POST /orders"];
```

Pair with const object satisfies for runtime list matching compile-time union — OpenAPI codegen alternative for small internal APIs.

## Limitations

Template literal types distribute over unions but can explode combinatorially — `type Bad = `${A}-${B}-${C}`` with large A,B,C slows the compiler. Cap union size or use branded string types for open-ended identifiers like user-provided slugs.

## Event name typing in analytics

```typescript
type ProductEvent = "view_item" | "add_to_cart" | "purchase";
type AnalyticsCall = `track:${ProductEvent}`;

function track(name: ProductEvent, props: Record<string, unknown>) {
  const call = `track:${name}` satisfies AnalyticsCall;
  send(call, props);
}
```

Prevents typo event names reaching analytics pipeline — compile error on `track("add_to_car")`.

## Branded strings for open-ended IDs

When IDs are not a closed union, combine template literals with branding:

```typescript
type UserId = string & { readonly __brand: "UserId" };
function userRoute(id: UserId) {
  return `/users/${id}` as const;
}
```

Template literals handle fixed prefixes; brands stop accidental cross-typing of unrelated string IDs in route builders.

## CSS variable typing

```typescript
type Token = "color-primary" | "spacing-md";
type Var = `--${Token}`;
const cssVar = (t: Token): Var => `--${t}`;
```

Design systems map token names to CSS custom properties with compile-time validation — typo `--color-primry` fails at build.

## Design choices that matter for typescript template literal types

TypeScript techniques in typescript template literal types pay off when they encode invariants the compiler can check. Prefer types that make illegal states unrepresentable over sprawling `any` escapes.

### Migration tactics

Enable `strict` incrementally: start with new packages, then tighten `noImplicitAny`, then `strictNullChecks` on legacy modules behind a burn-down list. Track error counts per package weekly.

### Patterns that scale

Branded types for IDs, discriminated unions for results, and `satisfies` for config objects keep refactors safe. Utility types (`Pick`, `Omit`, `ReturnType`) reduce duplication without inventing a parallel type language.

### Tooling

`tsc --noEmit` in CI, ESLint type-aware rules sparingly (they are slow), and API extractors for public packages. Generate types from OpenAPI/Zod when runtime validation must match compile-time types for typescript template literal types.

## Validation scenarios for typescript template literal types

Before calling typescript template literal types done, exercise these scenarios in a staging environment that mirrors production identity, data volume, and failure injection:

1. **Happy path** with production-like payload sizes.
2. **Auth failure** — expired token, missing scope, revoked session.
3. **Dependency down** — timeout the primary collaborator; confirm degraded mode or clear error.
4. **Replay / duplicate** — submit the same event or request twice; confirm idempotency.
5. **Rollback** — disable the flag or revert the deploy; confirm state converges.

Capture traces for each scenario and store them next to the runbook for typescript template literal types.

## Ownership and interfaces

Name the producing and consuming teams for typescript template literal types. Publish the API/event contract with versioning rules. If you need a breaking change, run dual-write or dual-read long enough for consumers to migrate. Silent breakages erode trust faster than slow features.

## Resources

- [TypeScript Handbook: Template Literal Types](https://www.typescriptlang.org/docs/handbook/2/template-literal-types.html)
- [TypeScript 4.1 Release Notes](https://www.typescriptlang.org/docs/handbook/release-notes/typescript-4-1.html#template-literal-types)
- [TypeScript 4.8 Improved intersection inference](https://www.typescriptlang.org/docs/handbook/release-notes/typescript-4-8.html)
- [type-fest string utility types](https://github.com/sindresorhus/type-fest)
- [ts-pattern route typing example](https://github.com/gvergnaud/ts-pattern)
## Typed routes

Template literal types catch invalid path strings at compile time.