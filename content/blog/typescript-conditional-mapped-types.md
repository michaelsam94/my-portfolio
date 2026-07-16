---
title: "Conditional and Mapped Types"
slug: "typescript-conditional-mapped-types"
description: "Master TypeScript conditional and mapped types: infer, distributive conditionals, key remapping, utility type patterns, and building type-safe APIs."
datePublished: "2026-02-13"
dateModified: "2026-02-13"
tags: ["TypeScript", "Web", "Type Safety", "Advanced Types"]
keywords: "conditional types, mapped types, TypeScript infer, utility types, type transformation, key remapping"
faq:
  - q: "What is a conditional type in TypeScript?"
    a: "A conditional type selects one of two types based on a condition, using the syntax T extends U ? X : Y. It works like a ternary operator at the type level. Conditional types can inspect whether a type extends another, extract inner types with infer, and distribute over union members. They are the foundation of most advanced TypeScript utility types like Exclude, Extract, and ReturnType."
  - q: "What is a mapped type and when do I use one?"
    a: "A mapped type iterates over the keys of an existing type and transforms each property, using the syntax { [K in keyof T]: ... }. Built-in examples are Partial, Readonly, and Record. You use mapped types when you need to systematically transform every property of a type — making them optional, readonly, nullable, or renaming keys — without manually duplicating the shape."
  - q: "What does the infer keyword do in conditional types?"
    a: "The infer keyword declares a type variable inside a conditional type that TypeScript infers from the matched pattern. For example, ReturnType<T> uses infer to extract the return type from a function signature: T extends (...args: any[]) => infer R ? R : never. Without infer, you would need to manually specify types you want to extract, which defeats the purpose of type-level introspection."
---

I was building a type-safe event emitter and needed `on('click', handler)` to infer the handler's event payload type from the event name string. Without conditional types, I'd have maintained a parallel lookup table by hand — a map of event names to payload types that drifted from reality every time someone added an event. Conditional types with `infer` let the compiler derive the relationship directly from the type definition. That pattern — inspect a type, extract a piece, transform it — is the backbone of advanced TypeScript, and once it clicks, you stop writing runtime validation that duplicates what the type system already knows.

## Conditional types: type-level if/else

```typescript
type IsString<T> = T extends string ? true : false;

type A = IsString<"hello">;  // true
type B = IsString<42>;       // false
```

The power comes from combining `extends` with `infer`:

```typescript
// Extract return type of any function
type MyReturnType<T> = T extends (...args: any[]) => infer R ? R : never;

type R1 = MyReturnType<() => string>;        // string
type R2 = MyReturnType<(x: number) => boolean>; // boolean
```

This is exactly how TypeScript's built-in `ReturnType<T>` works.

### Distributive conditionals

When the checked type is a naked type parameter, conditional types distribute over unions:

```typescript
type ToArray<T> = T extends any ? T[] : never;

type StrOrNumArray = ToArray<string | number>;
// string[] | number[]  (not (string | number)[])
```

Each union member is evaluated independently. To prevent distribution, wrap in a tuple:

```typescript
type ToArrayNonDist<T> = [T] extends [any] ? T[] : never;

type Combined = ToArrayNonDist<string | number>;
// (string | number)[]
```

### Practical infer patterns

Extract promise inner type:

```typescript
type Awaited<T> = T extends Promise<infer U> ? U : T;

type Inner = Awaited<Promise<string>>; // string
```

Extract the first argument of a function:

```typescript
type FirstArg<T> = T extends (first: infer F, ...rest: any[]) => any ? F : never;

type Arg = FirstArg<(name: string, age: number) => void>; // string
```

Extract array element type:

```typescript
type ElementOf<T> = T extends (infer E)[] ? E : never;

type Item = ElementOf<string[]>; // string
```

## Mapped types: transform every key

```typescript
type Optional<T> = {
  [K in keyof T]?: T[K];
};

type ReadonlyFields<T> = {
  readonly [K in keyof T]: T[K];
};
```

These are the implementations behind `Partial<T>` and `Readonly<T>`.

### Key remapping with `as`

TypeScript 4.1 added key remapping in mapped types:

```typescript
type Getters<T> = {
  [K in keyof T as `get${Capitalize<string & K>}`]: () => T[K];
};

interface Person { name: string; age: number; }

type PersonGetters = Getters<Person>;
// { getName: () => string; getAge: () => number; }
```

The `as` clause can also filter keys:

```typescript
type OnlyStrings<T> = {
  [K in keyof T as T[K] extends string ? K : never]: T[K];
};

interface Mixed { name: string; age: number; active: boolean; }

type StringFields = OnlyStrings<Mixed>;
// { name: string }
```

### Combining mapped and conditional

A pattern I use constantly — make specific keys required:

```typescript
type RequireKeys<T, K extends keyof T> = T & {
  [P in K]-?: T[P];
};

interface Config {
  host?: string;
  port?: number;
  timeout?: number;
}

type RequiredConfig = RequireKeys<Config, "host" | "port">;
// host and port are required; timeout stays optional
```

The `-?` modifier removes optionality from specific keys.

## Building a type-safe API client

Combining both features for an API where route determines response type:

```typescript
interface Routes {
  "/users": { users: User[] };
  "/users/:id": { user: User };
  "/health": { status: "ok" };
}

type RouteParams<T extends string> =
  T extends `${infer _Start}:${infer Param}/${infer Rest}`
    ? { [K in Param | keyof RouteParams<`/${Rest}`>]: string }
    : T extends `${infer _Start}:${infer Param}`
    ? { [K in Param]: string }
    : {};

type ResponseFor<TRoute extends keyof Routes> = Routes[TRoute];

async function api<TRoute extends keyof Routes>(
  route: TRoute,
  ...args: keyof RouteParams<TRoute & string> extends never
    ? []
    : [params: RouteParams<TRoute & string>]
): Promise<ResponseFor<TRoute>> {
  // implementation
  return {} as ResponseFor<TRoute>;
}

const users = await api("/users");
//    ^? { users: User[] }

const user = await api("/users/:id", { id: "123" });
//    ^? { user: User }
```

The return type is inferred from the route string. Params are required only for routes that have them. No manual type assertions at call sites.

## Utility types worth knowing

| Built-in | What it does |
|---|---|
| `Partial<T>` | All properties optional |
| `Required<T>` | All properties required |
| `Pick<T, K>` | Select specific keys |
| `Omit<T, K>` | Remove specific keys |
| `Record<K, V>` | Object type with keys K and values V |
| `Exclude<T, U>` | Remove U from union T |
| `Extract<T, U>` | Keep only T members assignable to U |
| `NonNullable<T>` | Remove null and undefined |
| `Parameters<T>` | Tuple of function parameter types |
| `ReturnType<T>` | Function return type |

Most of these are implemented with conditional and mapped types internally. Reading their source in `lib.es5.d.ts` is one of the best ways to learn the patterns.

## When to stop

Not every type needs to be derived. If a mapped conditional type takes 10 lines to read and you use it once, a plain interface is better. These tools earn their complexity when they eliminate entire categories of runtime bugs across many call sites — API clients, event systems, form validators, and ORM query builders are the sweet spots.

## Common production mistakes

Teams get conditional mapped types wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

TypeScript patterns for conditional mapped types erode when `any` escapes during deadlines, generic constraints are loosened instead of modeling domain invariants, and strict mode is disabled file-by-file without a migration plan.

## Resources

- [TypeScript Handbook: Conditional Types](https://www.typescriptlang.org/docs/handbook/2/conditional-types.html)
- [TypeScript Handbook: Mapped Types](https://www.typescriptlang.org/docs/handbook/2/mapped-types.html)
- [TypeScript 4.1 Key Remapping](https://www.typescriptlang.org/docs/handbook/release-notes/typescript-4-1.html#key-remapping-in-mapped-types)
- [type-fest utility collection](https://github.com/sindresorhus/type-fest)
- [Type Challenges (practice problems)](https://github.com/type-challenges/type-challenges)
