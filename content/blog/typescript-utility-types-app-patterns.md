---
title: "Utility Types for Application Patterns"
slug: "typescript-utility-types-app-patterns"
description: "Pick, Omit, Partial, and Record patterns for API layers — avoiding duplicate type definitions."
datePublished: "2026-11-24"
dateModified: "2026-07-17"
tags:
  - "Engineering"
keywords: "TypeScript utility types, Pick Omit Partial, app type patterns"
faq:
  - q: "When use Pick versus Omit?"
    a: "Pick when projecting a small read subset; Omit when most fields pass through minus server-generated or secret fields. Pick lists what you keep; Omit lists what you drop."
  - q: "Why not Partial<User> for updates?"
    a: "Partial<User> allows patching id, role, or createdAt — fields your API must never accept from clients. Use Partial<Pick<User, mutable fields>> instead."
  - q: "How do utility types work with Zod?"
    a: "Infer domain type from Zod schema with z.infer, then Pick/Omit for public DTO projections — runtime validation and compile-time shapes stay aligned."
---
Duplicate User, UserDTO, UserResponse, and CreateUserPayload drifted apart until a timezone field shipped — API accepted null while database rejected it. TypeScript utility types derive every layer shape from one domain interface so the compiler catches stale DTOs before deploy.

## Single source of truth for DTOs

Define domain models once; derive API shapes with **Pick**, **Omit**, and **Partial**:

```typescript
interface User {
  id: string;
  email: string;
  name: string;
  role: "member" | "admin";
  timezone: string;
  createdAt: Date;
  passwordHash: string;
}

type UserPublic = Pick<User, "id" | "name" | "role">;
type CreateUserInput = Omit<User, "id" | "createdAt" | "passwordHash">;
type UpdateUserInput = Partial<Pick<User, "name" | "email" | "timezone">>;
```

When `timezone` became required, only `User` changed — compiler errors surfaced every stale DTO in handlers, serializers, and tests.

## Pick and Omit in API layers

**Pick** for read projections exposing safe columns to clients. **Omit** for writes that exclude server-generated or secret fields. Never hand-copy field lists into parallel interfaces — copy-paste is where drift begins.

```typescript
type OrderSummary = Pick<Order, "id" | "total" | "status">;
type CreateOrderInput = Omit<Order, "id" | "createdAt" | "updatedAt">;
type AdminOrderView = Pick<Order, "id" | "total" | "status" | "internalNotes">;
```

GraphQL resolvers map Pick types to field selection sets — when schema adds field, update Pick alias once.

## Partial for PATCH semantics

Use **Partial<Pick<User, mutable fields>>** — not **Partial<User>**, which allows patching `id`, `role`, or `createdAt` from client payloads.

```typescript
type UpdatableUserFields = Pick<User, "name" | "email" | "timezone">;
type UpdateUserInput = Partial<UpdatableUserFields>;
```

Name intermediate aliases instead of nesting utilities — `UpdateUserInput` reads clearer in handler signatures than inline Partial<Pick<...>>.

## Record, Required, Readonly

```typescript
type RolePermissions = Record<User["role"], Permission[]>;
type ResolvedConfig = Required<ConfigInput>;
type ImmutableConfig = Readonly<Config>;
```

Record keys from union types stay exhaustive — adding new role without updating RolePermissions fails compile. Required after merging partial env config ensures apiUrl and jwtSecret present before server listens.

## ReturnType and Awaited

Derive from functions when implementation is source of truth:

```typescript
type FetchUserResult = Awaited<ReturnType<typeof userService.fetchById>>;
type HandlerReturn = Awaited<ReturnType<typeof createOrderHandler>>;
```

When service return type changes, consumers update automatically — no manual DTO sync.

## Exclude and Extract for unions

```typescript
type Success = { ok: true; data: User };
type Failure = { ok: false; error: string };
type ApiResult = Success | Failure;

type ErrorPayload = Extract<ApiResult, { ok: false }>;
type UserData = Extract<ApiResult, { ok: true }>["data"];
```

Extract narrows union members by shape — cleaner than manual conditional types for API result handling in route handlers.

## Parameters and ConstructorParameters

Wrap third-party functions without re-declaring argument types:

```typescript
type FetchArgs = Parameters<typeof fetch>;
type DateParts = ConstructorParameters<typeof Date>;
```

Library signature updates propagate to wrappers — fewer silent mismatches after dependency bumps.

## NonNullable and Required for config merging

Defaults merge with partial environment overrides:

```typescript
type ConfigInput = { apiUrl?: string; logLevel?: "info" | "debug" };
type LiveConfig = Required<Pick<ConfigInput, "apiUrl">> & ConfigInput;
```

Fail at boot when Required keys missing — not on first request in production.

## Zod alignment

Infer external input from schema; use Pick for public projections:

```typescript
const UserSchema = z.object({ id: z.string(), email: z.string(), secret: z.string() });
type User = z.infer<typeof UserSchema>;
type PublicUser = Pick<User, "id" | "email">;
```

Runtime validation and compile-time types share schema — utility types slice validated shape for responses.

## satisfies with utility-derived constraints

```typescript
const routes = {
  home: "/",
  settings: "/settings",
} as const satisfies Record<string, `/${string}`>;
```

Literal inference plus utility constraints — routes stay typed path strings without widening to generic Record.

## Anti-patterns in code review

- Duplicate entity and DTO with copy-paste field lists
- Partial<Entity> for updates allowing forbidden fields
- Utility soup without named aliases — Partial<Omit<Pick<...>>>
- Custom Optional<T> alias duplicating Partial
- Using utilities instead of discriminated unions for polymorphic API responses

## Migration from duplicate interfaces

Search codebase for interfaces mirroring entity fields — replace with Pick/Omit from domain model one module per PR. Compiler errors enumerate remaining drift. Add ESLint rule banning duplicate property sets where domain type exists.

## Testing derived types

Type-level tests with `@ts-expect-error` on forbidden assignments:

```typescript
// @ts-expect-error role is not updatable
const bad: UpdateUserInput = { role: "admin" };
```

Compile-time tests cheaper than runtime tests for shape enforcement.

Utility types are glue between layers — derive shapes, name them for readers, let the compiler propagate model changes. The timezone incident would have been a type error, not a production outage.

## Layering DTOs in hexagonal architecture

Domain entity stays pure — application layer defines Pick/Omit views for inbound commands and outbound queries. Infrastructure maps entity to persistence model separately. Utility types express application boundary, not ORM row shape.

## OpenAPI codegen integration

When OpenAPI generates types, wrap generated interfaces with Pick for public responses instead of editing generated files — regeneration overwrites manual edits. Utility types sit in hand-written adapter layer between codegen output and handlers.

## Monorepo sharing

Publish `@acme/types` with domain entity and derived DTO aliases — frontend imports UserPublic, backend imports CreateUserInput from same package. Changes propagate via semver on types package, not silent cross-repo drift.

## Performance considerations

Utility types erase at compile time — zero runtime cost. Prefer types over runtime pick/omit helpers unless validating dynamic keys from untrusted JSON at boundary (use Zod there instead).

## Conditional types versus utilities

Reach for conditional types when mapping over union members — utilities when slicing object properties. Mixing both: `type Mutable<T> = { -readonly [K in keyof T]: T[K] }` for readonly stripping at config boundaries.

## StrictNullChecks interaction

Pick and Omit preserve optional modifiers from source — undefined still flows through Pick of optional field. Required<> after Pick when business rules demand presence post-validation.

## Generic factory functions

```typescript
function pick<T, K extends keyof T>(obj: T, ...keys: K[]): Pick<T, K> {
  const result = {} as Pick<T, K>;
  for (const k of keys) result[k] = obj[k];
  return result;
}
```

Prefer type-level Pick at compile time; runtime pick only for dynamic keys with validation.

## Editor and DX tooling

Enable `@typescript-eslint/consistent-type-definitions` and ban duplicate property interfaces via custom ESLint rule comparing AST shape to domain type import.

## Additional context (1)

Partial for PATCH and Required for create DTOs — utility types beat hand-rolling optional variants per endpoint. Document which routes or tenants you changed first, and keep rollback paths in the PR description before promoting beyond canary traffic.

## Additional context (2)

Partial for PATCH and Required for create DTOs — utility types beat hand-rolling optional variants per endpoint. Document which routes or tenants you changed first, and keep rollback paths in the PR description before promoting beyond canary traffic.

## Utility types as shared vocabulary

`Pick`, `Omit`, `Partial`, and mapped types should name API boundaries — `CreateOrderInput` versus `OrderRecord` — not decorate every object. Deep `Partial<Entity>` hides required invariants and trains callers to omit fields finance still needs.

Publish which utilities are encouraged versus banned in domain cores. Prefer explicit result unions over optional fields that mean missing, not loaded, and not applicable at once. Extract cross-package helpers to a versioned types package.

Compile-fail tests document illegal states better than wiki pages. When a utility spreads across five apps, treat changes like API breaks with dual-read windows.

## Operations note 1 for typescript utility types app patterns

Name the owner, dashboard, and rollback for typescript utility types app patterns. Add one automated check for the failure path. Prefer progressive delivery. Require a compatibility note when typescript utility types app patterns changes cross team boundaries. Rehearse rollback once in staging.

## Operations note 2 for typescript utility types app patterns

Name the owner, dashboard, and rollback for typescript utility types app patterns. Add one automated check for the failure path. Prefer progressive delivery. Require a compatibility note when typescript utility types app patterns changes cross team boundaries. Rehearse rollback once in staging.
