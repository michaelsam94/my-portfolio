# Part 4: TypeScript (4)

POSTS = {}

POSTS["typescript-generics-constraints"] = (
    {
        "title": "Generics and Constraints, Explained",
        "description": "Use TypeScript generics and constraints effectively: bounded type parameters, keyof patterns, generic inference, and building reusable type-safe utilities.",
        "datePublished": "2026-02-17",
        "tags": ["TypeScript", "Web", "Type Safety", "Fundamentals"],
        "keywords": "TypeScript generics, generic constraints, extends, keyof, type inference, bounded type parameters",
        "faq": [
            {
                "q": "What is a generic constraint in TypeScript?",
                "a": "A generic constraint limits what types can be passed as a type argument by requiring the type to extend a specific shape. The syntax T extends SomeType means T must be assignable to SomeType. This lets you access properties on T inside the function body — for example, T extends { id: string } lets you read item.id — while still preserving the specific type the caller passes in.",
            },
            {
                "q": "What is the difference between generics and the any type?",
                "a": "any disables type checking entirely — you lose safety and IDE support. Generics preserve the relationship between input and output types while remaining flexible. A function identity<T>(value: T): T with any becomes identity(value: any): any, which tells the compiler nothing. With generics, passing a string returns a string, passing a number returns a number, and misuse is caught at compile time.",
            },
            {
                "q": "When should I add a constraint versus leaving the generic unbounded?",
                "a": "Leave generics unbounded when the function truly works with any type — identity, array wrapping, Promise creation. Add a constraint when the function accesses specific properties or methods on T — sorting requires T extends Comparable, grouping requires T extends Record<string, unknown>. If you find yourself casting inside a generic function, you probably need a constraint.",
            },
        ],
    },
    r"""The utility function `getProperty(obj, key)` compiled with `any` for months until someone passed a key that did not exist and production logged `undefined` through twelve downstream calls. Adding `<T, K extends keyof T>` fixed it in one line — and autocomplete started listing legal keys. Generics without constraints are flexible; generics **with** constraints are flexible **and** safe inside the function body. That distinction is most of advanced TypeScript application code.

## Unbounded generics

```typescript
function identity<T>(value: T): T {
  return value;
}

const n = identity(42);      // number
const s = identity("hello"); // string
```

Compiler tracks relationship between input and output. No access to properties on `T` without constraint:

```typescript
function broken<T>(item: T) {
  return item.id; // Error: Property 'id' does not exist on type 'T'
}
```

## Basic constraints

```typescript
function withId<T extends { id: string }>(item: T): string {
  return item.id;
}
```

`T` might be `User`, `Order`, anything with `id: string` — caller keeps specific type:

```typescript
const user: User = { id: "u1", name: "Ada" };
const id = withId(user); // T inferred as User
```

## keyof constraints

Safe property access:

```typescript
function getProperty<T, K extends keyof T>(obj: T, key: K): T[K] {
  return obj[key];
}

const user = { id: "1", name: "Ada", age: 30 };
getProperty(user, "name"); // ok, string
getProperty(user, "email"); // compile error
```

Return type **`T[K]`** preserves property type — not `any`.

## Multiple constraints with intersection

```typescript
function merge<T extends object, U extends object>(a: T, b: U): T & U {
  return { ...a, ...b };
}
```

Requires object — excludes primitives.

## Constructor constraints

```typescript
function create<T extends new (...args: any[]) => InstanceType<T>>(
  Ctor: T,
  ...args: ConstructorParameters<T>
): InstanceType<T> {
  return new Ctor(...args);
}

class User {
  constructor(public name: string) {}
}

create(User, "Ada"); // User
```

## Generic inference pitfalls

Explicit type args when inference fails:

```typescript
const arr = [1, 2, 3];
const first = pick(arr, 0); // infer T as number

function pick<T>(list: T[], index: number): T {
  return list[index];
}
```

Widening with `as const` when literals needed:

```typescript
const config = { mode: "strict" } as const;
```

## Building utilities

```typescript
function groupBy<T, K extends string | number | symbol>(
  items: T[],
  keyFn: (item: T) => K
): Record<K, T[]> {
  return items.reduce((acc, item) => {
    const key = keyFn(item);
    (acc[key] ??= []).push(item);
    return acc;
  }, {} as Record<K, T[]>);
}
```

Constraint on **`K`** matches Record key requirements.

## When casts signal missing constraints

```typescript
// smell
function sortBy<T>(items: T[], key: keyof T) {
  return items.sort((a, b) => (a[key] as any) - (b[key] as any));
}

// better
function sortBy<T extends Record<K, number | string>, K extends keyof T>(
  items: T[],
  key: K
) {
  return [...items].sort((a, b) => {
    if (a[key] < b[key]) return -1;
    if (a[key] > b[key]) return 1;
    return 0;
  });
}
```

## Default type parameters

```typescript
interface ApiResponse<T = unknown> {
  data: T;
  error?: string;
}
```

Defaults reduce noise when callers omit type arg.

Generics constraints encode **what you need to know about T** to implement the function. Start unbounded; add `extends` when the compiler asks for properties. The goal is zero `as any` inside reusable utilities.""",
)

POSTS["typescript-satisfies-operator"] = (
    {
        "title": "The TypeScript satisfies Operator",
        "description": "Use the TypeScript satisfies operator to validate types without widening: preserve literal inference, catch typos, and type-check config objects cleanly.",
        "datePublished": "2026-02-19",
        "tags": ["TypeScript", "Web", "Type Safety", "TypeScript 4.9"],
        "keywords": "TypeScript satisfies, type narrowing, literal types, config validation, type widening",
        "faq": [
            {
                "q": "What does the satisfies operator do in TypeScript?",
                "a": "The satisfies operator checks that an expression conforms to a type without changing the expression's inferred type. Unlike a type annotation, which widens literal types to their base type, satisfies preserves narrow literal types while still validating the shape. You get both compile-time checking and precise autocomplete for literal values like color names, route paths, or configuration keys.",
            },
            {
                "q": "How is satisfies different from a type annotation?",
                "a": "A type annotation like const config: Config = { ... } validates the shape but widens inferred types — a literal 'red' becomes string. The satisfies operator const config = { ... } satisfies Config validates the same shape but keeps 'red' as the literal type 'red'. This matters when you want exhaustiveness checking plus precise downstream inference for individual property values.",
            },
            {
                "q": "When should I use satisfies instead of as const?",
                "a": "Use as const when you want everything deeply readonly and literal with no target type to validate against. Use satisfies when you need to check against a specific type — like a Record of route handlers or a theme config interface — while preserving literal types. satisfies gives you validation that as const cannot provide, because as const doesn't check whether your object actually matches an expected shape.",
            },
        ],
    },
    r"""Theme config used `"rebeccapurple"` in production because TypeScript accepted `{ primary: "rebeccapurple" }` with a `Theme` annotation — valid string, wrong union member. **`satisfies Theme`** would have failed compile: typo caught before merge. The `satisfies` operator (TypeScript 4.9+) validates shape without widening literals — the rare feature that adds safety **and** better inference instead of trading one for the other.

## Widening problem with annotations

```typescript
type Color = "red" | "green" | "blue";

type Theme = {
  primary: Color;
  secondary: Color;
};

const bad: Theme = {
  primary: "red",
  secondary: "reed", // typo — error caught
};

const widened: Theme = {
  primary: "red",
  secondary: "blue",
};

// typeof widened.primary is Color, not "red"
```

Annotation checks assignability but widens property inference to declared type.

## satisfies preserves literals

```typescript
const theme = {
  primary: "red",
  secondary: "blue",
} satisfies Theme;

// theme.primary is "red" (literal)
// theme.secondary is "blue" (literal)
```

Excess property checking still applies; typos in union members fail:

```typescript
const broken = {
  primary: "red",
  secondary: "reed",
} satisfies Theme; // Error
```

## Route maps and exhaustiveness

```typescript
type Route = "/home" | "/settings" | "/profile";

type Handlers = Record<Route, () => void>;

const routes = {
  "/home": () => console.log("home"),
  "/settings": () => console.log("settings"),
  "/profile": () => console.log("profile"),
} satisfies Handlers;
```

Missing or mistyped key — compile error. Keys stay literal types for switch exhaustiveness elsewhere.

## satisfies vs as const

```typescript
const palette = {
  red: "#f00",
  green: "#0f0",
} as const;
// readonly, literals, but no validation against external schema

const palette2 = {
  red: "#f00",
  green: "#0f0",
} satisfies Record<string, `#${string}`>;
// validates hex pattern + preserves literal keys
```

Use **`as const satisfies T`** together when you need readonly + validation:

```typescript
const config = {
  mode: "strict",
  retries: 3,
} as const satisfies Config;
```

## Nested configs

```typescript
type EnvConfig = {
  apiUrl: string;
  features: Record<"darkMode" | "beta", boolean>;
};

const env = {
  development: {
    apiUrl: "http://localhost:3000",
    features: { darkMode: true, beta: true },
  },
  production: {
    apiUrl: "https://api.example.com",
    features: { darkMode: false, beta: false },
  },
} satisfies Record<"development" | "production", EnvConfig>;
```

## When annotations remain correct

Public API exports where consumers should see wide type:

```typescript
export const DEFAULT_THEME: Theme = {
  primary: "red",
  secondary: "blue",
};
```

Export boundary intentionally widens; internal config uses `satisfies`.

## ESLint and review

Enable `@typescript-eslint/prefer-satisfies` where appropriate. In review, flag new `: LargeConfig` annotations on constant objects — ask if literals matter.

`satisfies` is the right default for in-file config objects, theme tokens, route tables, and discriminated maps — anywhere a typo should fail compile but autocomplete should know exact keys. Save type annotations for when you intentionally want widening at the boundary.""",
)

POSTS["typescript-strict-mode-migration"] = (
    {
        "title": "Migrating to TypeScript Strict Mode",
        "description": "A practical guide to enabling TypeScript strict mode incrementally: strictNullChecks, noImplicitAny, strictFunctionTypes, and fixing a legacy codebase without stopping development.",
        "datePublished": "2026-02-21",
        "tags": ["TypeScript", "Web", "Migration", "Type Safety"],
        "keywords": "TypeScript strict mode, strictNullChecks, noImplicitAny, migration, tsconfig, type safety",
        "faq": [
            {
                "q": "What does TypeScript strict mode actually enable?",
                "a": "Strict mode is not a single flag — it is a bundle of compiler options activated by strict: true in tsconfig.json. The most impactful individual flags are strictNullChecks (null and undefined are distinct from other types), noImplicitAny (error on untyped parameters and variables), strictFunctionTypes (stricter function parameter checking), and strictPropertyInitialization (class properties must be initialized). Together they eliminate the majority of runtime type errors TypeScript otherwise allows.",
            },
            {
                "q": "Can I enable strict mode incrementally on an existing project?",
                "a": "Yes, and you should. Do not flip strict: true on a large codebase in one PR. Enable individual flags one at a time, starting with noImplicitAny and strictNullChecks as the highest-value pair. Use @ts-expect-error with a ticket reference for errors you cannot fix immediately, and track the count to ensure it decreases over time. Many teams run a strict tsconfig for new files while legacy files remain on the loose config until migrated.",
            },
            {
                "q": "How long does a strict mode migration typically take?",
                "a": "It depends on codebase size and age, but a rough guide: a 50k-line project takes two to four weeks of dedicated effort, while a 200k-line project takes one to three months spread across normal development. The work is mostly mechanical — adding null checks, typing function parameters, fixing any escapes — but it touches many files. The key is incremental progress: enable one flag, fix the errors, merge, repeat. Trying to fix everything at once leads to a long-lived branch that never merges.",
            },
        ],
    },
    r"""`strict: true` in a single PR touched 1,400 files and never merged. Six months later, a null reference in checkout cost a day of revenue. The second attempt enabled **`noImplicitAny`** only — three hundred files, one sprint, shipped. Then **`strictNullChecks`** — six hundred files over two sprints. Strict mode migration is a marathon of small merges, not a rewrite branch. The compiler flags are binary; your rollout should not be.

## What strict: true enables

```json
{
  "compilerOptions": {
    "strict": true
  }
}
```

Equivalent to enabling:

| Flag | Effect |
|------|--------|
| strictNullChecks | null/undefined explicit |
| noImplicitAny | ban inferred any |
| strictFunctionTypes | contravariant params |
| strictBindCallApply | typed bind/call |
| strictPropertyInitialization | class fields init |
| noImplicitThis | this typing |
| alwaysStrict | emit use strict |

**strictNullChecks** and **noImplicitAny** catch most production bugs; prioritize those first.

## Incremental rollout strategy

**Step 1 — noImplicitAny**

```json
{ "compilerOptions": { "noImplicitAny": true } }
```

Fix implicit any on parameters, destructuring, catch bindings:

```typescript
// before
function parse(json) {
  return JSON.parse(json);
}

// after
function parse(json: string): unknown {
  return JSON.parse(json);
}
```

**Step 2 — strictNullChecks**

```typescript
// before
function len(s: string | null) {
  return s.length; // error under strictNullChecks
}

// after
function len(s: string | null) {
  if (s === null) return 0;
  return s.length;
}
```

Use optional chaining and nullish coalescing — but not as substitute for logic errors.

**Step 3 — remaining strict flags**

Enable **`strictFunctionTypes`** before heavy callback refactors. **`strictPropertyInitialization`** last on class-heavy codebases — consider `declare` fields or definite assignment assertion sparingly:

```typescript
class Service {
  private client!: HttpClient; // initialized in constructor — use carefully
  constructor() {
    this.client = createClient();
  }
}
```

## ts-expect-error budget

```typescript
// @ts-expect-error TICKET-1234 legacy API returns untyped payload
const data = legacyFetch();
```

Track count in CI:

```bash
grep -r "@ts-expect-error" src | wc -l
```

Fail CI if count increases. Decrease weekly.

## Dual tsconfig pattern

```json
// tsconfig.strict.json
{
  "extends": "./tsconfig.json",
  "compilerOptions": { "strict": true },
  "include": ["src/new-module/**/*"]
}
```

New modules strict from day one; old modules migrate file-by-file.

## Codemods and tools

- **`typescript-eslint` strict rules** — align lint with compiler
- **`ts-migrate`** (Airbnb) — bulk any injection then tighten (controversial but bootstraps)
- **`eslint --fix`** for explicit return types on exported functions

## Team process

1. Document flag order and rationale in ADR.
2. Allocate 10–20% sprint capacity during migration quarter.
3. No new `@ts-ignore` — only `@ts-expect-error` with ticket.
4. Celebrate flag enable merges like features.

## Common fixes catalog

| Error | Fix pattern |
|-------|-------------|
| Object possibly undefined | Guard or optional chain |
| Parameter implicitly any | Add type or generic |
| Type null not assignable | Extend union or default |
| Function not assignable | Fix callback arity/types |

## Avoid

- **`as any`** to silence — defeats migration
- Long-lived strict branch rebased weekly
- Disabling strict for entire `src/` via `@ts-nocheck`

Strict mode makes TypeScript earn the name. Incremental enablement keeps shipping while error count trends to zero — boring, mergeable PRs beat heroic rewrites.""",
)

POSTS["typescript-utility-types-app-patterns"] = (
    {
        "title": "Utility Types for Application Patterns",
        "description": "Pick, Omit, Partial, and Record patterns for API layers — avoiding duplicate type definitions.",
        "datePublished": "2026-11-24",
        "tags": ["TypeScript", "Types", "Patterns"],
        "keywords": "TypeScript utility types, Pick Omit Partial, app type patterns",
        "faq": [
            {
                "q": "When should I use Pick versus duplicating a type?",
                "a": "Use Pick when a type is a subset of an existing model — UserSummary = Pick<User, 'id' | 'name'>. Duplicating fields drifts when User adds required fields; Pick keeps a single source of truth. If the subset diverges semantically from the base type, a distinct interface may be clearer than Pick.",
            },
            {
                "q": "How do Omit and Partial help API layers?",
                "a": "Omit removes fields generated server-side — CreateUserInput = Omit<User, 'id' | 'createdAt'>. Partial makes update payloads where every field is optional — UpdateUserInput = Partial<Pick<User, 'name' | 'email'>>. Together they avoid maintaining parallel DTO types that mirror entities.",
            },
            {
                "q": "What are common mistakes with utility types?",
                "a": "Over-nesting Pick<Omit<Partial<T>>> becomes unreadable — extract named type aliases. Applying Partial to entire entities for updates allows clearing required fields unintentionally — prefer Pick of mutable fields. Record<string, unknown> as escape hatch everywhere defeats strict checking — use specific keys or branded types.",
            },
        ],
    },
    r"""The API layer defined `User`, `UserCreate`, `UserUpdate`, `UserResponse`, and `UserPublic` — five interfaces with eighty percent overlapping fields. When `timezone` became required on `User`, three DTOs drifted until mobile sent null and the server rejected valid sessions. TypeScript utility types **`Pick`**, **`Omit`**, **`Partial`**, and **`Record`** derive DTOs from domain models — one change propagates, reviewers see intent in the type expression.

## Single source of truth

```typescript
interface User {
  id: string;
  email: string;
  name: string;
  role: "member" | "admin";
  timezone: string;
  createdAt: Date;
  passwordHash: string; // server only
}

type UserPublic = Pick<User, "id" | "name" | "role">;

type CreateUserInput = Omit<User, "id" | "createdAt" | "passwordHash">;

type UpdateUserInput = Partial<Pick<User, "name" | "email" | "timezone">>;
```

Public API never exposes `passwordHash` — compiler enforces at assignment:

```typescript
function toPublic(user: User): UserPublic {
  return { id: user.id, name: user.name, role: user.role };
}
```

## Pick for projections

```typescript
type OrderSummary = Pick<Order, "id" | "total" | "status">;
```

List endpoints return summaries without duplicating field list in comment docs.

## Omit for server-generated fields

```typescript
type CreateOrderInput = Omit<Order, "id" | "createdAt" | "updatedAt">;
```

Pair with Zod runtime validation at boundary:

```typescript
const CreateOrderSchema = z.object({
  customerId: z.string(),
  lineItems: z.array(LineItemSchema),
});
type CreateOrderInput = z.infer<typeof CreateOrderSchema>;
```

Schema-first often replaces Omit for external input — utilities still help internal types.

## Partial for PATCH semantics

```typescript
async function updateUser(id: string, patch: UpdateUserInput) {
  const existing = await repo.findById(id);
  return repo.save({ ...existing, ...patch });
}
```

Do not **`Partial<User>`** for updates — allows patching `id` or `role` unintentionally. **`Pick` mutable fields, then `Partial`**.

## Required and Readonly

```typescript
type PublishedPost = Required<Pick<Post, "title" | "body" | "publishedAt">>;

type ImmutableConfig = Readonly<Config>;
```

**`Required`** fills optional keys; **`Readonly`** shallow freezes props.

## Record for maps

```typescript
type RolePermissions = Record<User["role"], Permission[]>;

const permissions: RolePermissions = {
  member: ["read"],
  admin: ["read", "write", "delete"],
};
```

Keys exhaust union — missing `admin` errors.

```typescript
type RouteParams = Record<string, string>; // escape hatch — narrow when possible
```

Prefer **`Record<RouteId, Handler>`** over string keys when routes are finite.

## Extract and Exclude

```typescript
type AdminRole = Extract<User["role"], "admin">;
type NonAdminRole = Exclude<User["role"], "admin">;
```

Filter union members for conditional logic types.

## Composition readability

Bad:

```typescript
type X = Partial<Omit<Pick<User, "a" | "b" | "c">, "a">>;
```

Good:

```typescript
type UpdatableUserFields = Pick<User, "name" | "email" | "timezone">;
type UpdateUserInput = Partial<UpdatableUserFields>;
```

Name intermediate aliases — diff reviews stay human-readable.

## ReturnType and Parameters

```typescript
type FetchUser = typeof userService.fetchById;
type FetchUserResult = Awaited<ReturnType<FetchUser>>;
```

Derive types from functions when implementation is source of truth.

## Anti-patterns

- Duplicate entity and DTO with copy-paste
- `Partial<Entity>` for API updates
- Utility soup without named aliases
- Using utilities instead of discriminated unions for polymorphic API responses

Utility types are glue between layers — not cleverness for its own sake. Derive shapes, name them for readers, and let the compiler propagate model changes into every DTO that should move together.""",
)
