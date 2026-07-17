---
title: "Migrating to TypeScript Strict Mode"
slug: "typescript-strict-mode-migration"
description: "A practical guide to enabling TypeScript strict mode incrementally: strictNullChecks, noImplicitAny, strictFunctionTypes, and fixing a legacy codebase without stopping development."
datePublished: "2026-02-21"
dateModified: "2026-07-17"
tags: ["TypeScript", "Web", "Migration", "Type Safety"]
keywords: "TypeScript strict mode, strictNullChecks, noImplicitAny, migration, tsconfig, type safety"
faq:
  - q: "What does TypeScript strict mode actually enable?"
    a: "Strict mode is not a single flag — it is a bundle of compiler options activated by strict: true in tsconfig.json. The most impactful individual flags are strictNullChecks (null and undefined are distinct from other types), noImplicitAny (error on untyped parameters and variables), strictFunctionTypes (stricter function parameter checking), and strictPropertyInitialization (class properties must be initialized). Together they eliminate the majority of runtime type errors TypeScript otherwise allows."
  - q: "Can I enable strict mode incrementally on an existing project?"
    a: "Yes, and you should. Do not flip strict: true on a large codebase in one PR. Enable individual flags one at a time, starting with noImplicitAny and strictNullChecks as the highest-value pair. Use @ts-expect-error with a ticket reference for errors you cannot fix immediately, and track the count to ensure it decreases over time. Many teams run a strict tsconfig for new files while legacy files remain on the loose config until migrated."
  - q: "How long does a strict mode migration typically take?"
    a: "It depends on codebase size and age, but a rough guide: a 50k-line project takes two to four weeks of dedicated effort, while a 200k-line project takes one to three months spread across normal development. The work is mostly mechanical — adding null checks, typing function parameters, fixing any escapes — but it touches many files. The key is incremental progress: enable one flag, fix the errors, merge, repeat. Trying to fix everything at once leads to a long-lived branch that never merges."
faqAnswers:
  - question: "When is typescript strict mode migration the wrong approach?"
    answer: "When a simpler control already covers the risk, or when the operational cost exceeds the benefit for your threat and traffic model."
  - question: "What should we measure for typescript strict mode migration?"
    answer: "Pair a leading operational signal with a lagging user or risk outcome, reviewed on a fixed cadence with a named owner."
  - question: "How do we roll back typescript strict mode migration safely?"
    answer: "Keep the prior artifact or config warm, rehearse the revert once in staging, and document the one-command rollback for on-call."
---
"We'll enable strict mode after the launch." That was six launches ago. The tsconfig still had `strict: false`, `noImplicitAny: false`, and `skipLibCheck: true` covering a multitude of sins. When we finally flipped `strictNullChecks` alone, the compiler reported 1,400 errors — and half of them were real bugs: unguarded `response.data` accesses, functions that returned `undefined` on error paths without typing it, and event handlers assuming `event.target` was never null. Strict mode isn't a style preference. It's a bug-finding tool, and migrating to it is one of the best returns on investment in a TypeScript codebase.

## What strict: true enables

```json
{
  "compilerOptions": {
    "strict": true
  }
}
```

This activates:

| Flag | What it catches |
|---|---|
| `strictNullChecks` | `null`/`undefined` not handled |
| `noImplicitAny` | Untyped parameters and variables |
| `strictFunctionTypes` | Unsafe function parameter variance |
| `strictBindCallApply` | Incorrect `bind`/`call`/`apply` usage |
| `strictPropertyInitialization` | Uninitialized class properties |
| `noImplicitThis` | `this` with implicit `any` type |
| `alwaysStrict` | Emit `"use strict"` in output |

`strictNullChecks` and `noImplicitAny` account for 90% of the errors and 90% of the bugs found.

## Incremental migration strategy

### Step 1: Baseline the error count

```bash
npx tsc --noEmit --strict 2>&1 | tail -1
# Found 1847 errors in 412 files.
```

Record this number. It's your score to beat.

### Step 2: Enable one flag at a time

Start with `noImplicitAny` — it's the most mechanical to fix:

```json
{
  "compilerOptions": {
    "noImplicitAny": true
  }
}
```

Common fixes:
- Add parameter types to untyped functions
- Type catch clause variables: `catch (e: unknown)`
- Replace implicit `any` returns with explicit types

### Step 3: Enable strictNullChecks

This is the big one. Every `null` and `undefined` must be handled:

```typescript
// Before (compiles with strictNullChecks: false)
function getName(user: User | null) {
  return user.name;  // runtime crash if null
}

// After
function getName(user: User | null): string {
  if (!user) return "Anonymous";
  return user.name;
}
```

Patterns that fix most errors:

```typescript
// Optional chaining
const city = user?.address?.city;

// Nullish coalescing
const name = user.name ?? "Unknown";

// Type guards
if (result !== null) {
  process(result);  // result is narrowed
}

// Non-null assertion (last resort)
const el = document.getElementById("app")!;
```

Use non-null assertions (`!`) sparingly and only where you have external guarantees (e.g., a DOM element you just created).

### Step 4: Use @ts-expect-error as a bridge

For errors you can't fix immediately:

```typescript
// @ts-expect-error TODO(TS-142): user can be null from legacy API
const name = legacyGetUser().name;
```

`@ts-expect-error` is better than `@ts-ignore` because it errors if the line below stops being an error — meaning someone fixed it and the suppression is now stale.

Track suppressions:

```bash
rg "@ts-expect-error" --count-matches | awk -F: '{sum+=$2} END {print sum}'
```

Set a CI threshold that only decreases.

## Fixing patterns at scale

### Untyped function parameters

```typescript
// Before
function formatDate(d) { return d.toISOString(); }

// After
function formatDate(d: Date): string { return d.toISOString(); }
```

### API response handling

```typescript
// Before
const data = await response.json();
console.log(data.user.name);

// After
interface ApiResponse { user: { name: string } | null }
const data: ApiResponse = await response.json();
console.log(data.user?.name ?? "Unknown");
```

### Array access

```typescript
// Before
const first = items[0].name;  // items[0] might be undefined

// After
const first = items[0]?.name;
// or
const [first] = items;
if (first) { /* ... */ }
```

### Event handlers

```typescript
// Before
function handleClick(e) {
  e.target.value = "";
}

// After
function handleClick(e: Event) {
  const target = e.target as HTMLInputElement;
  target.value = "";
}
```

## Dual tsconfig for new vs. legacy

For large codebases, run two configs:

```json
// tsconfig.strict.json
{
  "extends": "./tsconfig.json",
  "compilerOptions": { "strict": true },
  "include": ["src/new-feature/**/*"]
}
```

New code is strict from day one. Legacy code migrates file by file. Move directories from the loose config to the strict config as they're cleaned up.

## CI enforcement

Add a ratchet to prevent regression:

```bash
# In CI
ERRORS=$(npx tsc --noEmit --strict 2>&1 | grep "Found" | awk '{print $2}')
THRESHOLD=1200  # decrease this number over time
if [ "$ERRORS" -gt "$THRESHOLD" ]; then
  echo "TypeScript strict errors ($ERRORS) exceed threshold ($THRESHOLD)"
  exit 1
fi
```

Lower the threshold each sprint. New code that adds errors breaks CI. The count only goes down.

## What not to do

- **Don't `@ts-ignore` everything.** It hides errors without tracking them.
- **Don't cast to `any` to silence errors.** `as any` defeats the purpose.
- **Don't enable all flags in a mega-PR.** It won't merge and will rot.
- **Don't skip `strictFunctionTypes`.** It's low-error-count but catches real callback mismatches.

## The payoff

After migration, you'll notice:
- Fewer `Cannot read property of undefined` production errors
- Better IDE autocomplete (types are real, not `any`)
- Safer refactoring (the compiler catches breakage)
- New team members get accurate type information

The migration is tedious but mechanical. The bugs it surfaces are not theoretical — they're in your production error logs, waiting to be found.

## Incremental strictness rollout

Enable `strict` flags one at a time across codebase: `strictNullChecks` first (highest bug catch), then `noImplicitAny`, then `strictFunctionTypes`. Use `@ts-expect-error` with ticket references for legacy files during migration — not `@ts-ignore` without expiry. CI rule: no new `@ts-expect-error` without approval. Track error count weekly; celebrate downward trend even if not zero yet.

## noImplicitReturns in async functions

Async functions implicitly return `Promise<void>` — missing return in branch still violates noImplicitReturns when other branches return value. Explicit `return undefined` or restructure guards. Enable in CI per-directory once src/legacy is excluded via tsconfig references.

## Resources

- [TypeScript tsconfig strict](https://www.typescriptlang.org/tsconfig#strict)
- [TypeScript 3.0 strictNullChecks](https://www.typescriptlang.org/docs/handbook/release-notes/typescript-3-0.html#new-unknown-top-type)
- [Gradual strict mode migration (Matt Pocock)](https://www.totaltypescript.com/how-to-enable-strict-mode)
- [typescript-strict-plugin](https://github.com/allegro/typescript-strict-plugin)
- [TypeScript Handbook: Narrowing](https://www.typescriptlang.org/docs/handbook/2/narrowing.html)

## typescript strict mode migration rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## typescript strict mode migration rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## typescript strict mode migration rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## typescript strict mode migration rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## typescript strict mode migration rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## typescript strict mode migration rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## typescript strict mode migration rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## typescript strict mode migration rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## typescript strict mode migration rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## typescript strict mode migration rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## typescript strict mode migration rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## typescript strict mode migration rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## Architecture decisions around typescript strict mode migration

TypeScript leverage for typescript strict mode migration comes from encoding invariants the compiler can enforce at change sites. `any` escapes and loose `as` casts are where production bugs hide.

For typescript strict mode migration:
- Prefer `unknown` + narrowing over `any`
- Branded types for IDs that must not mix (UserId vs OrderId)
- Zod (or equivalent) at IO boundaries; infer types from schemas
- `satisfies` for config objects that need both literal inference and type checks

Enable strictness incrementally with lint gates so new code cannot regress the baseline.

| Signal | Target | Alarm |
|--------|--------|-------|
| Plan apply time | Team-defined SLO | Page on burn rate |
| Drift open count | Baseline − noise | Ticket if sustained |
| Failed policy checks | Budget cap | Weekly review |

## Load and chaos experiments for typescript strict mode migration

Reviewers should challenge assumptions encoded in typescript strict mode migration: defaults copied from tutorials, timeouts that exceed upstream SLAs, and authz checks applied only on the primary UI path. Require a short threat or failure note in the PR when the change touches a trust boundary.

Concrete probes:
1. Scenario B for typescript strict mode migration: bad config shipped — prove rollback within the declared RTO without data corruption.
2. Scenario C for typescript strict mode migration: traffic 3× baseline — prove autoscaling or shedding keeps the golden journey healthy.
3. Scenario A for typescript strict mode migration: partial dependency outage — prove clients degrade gracefully and retries do not amplify load.

## Capacity planning with typescript strict mode migration in mind

Roll out typescript strict mode migration behind a flag or weighted route when possible. Start with internal users or a low-risk geography. Watch the signals in the table for at least one full business cycle before calling the migration done. Keep the previous path warm until error budgets stabilize.

Document the owner, the dashboard, and the single command that reverts the change. If that sentence is hard to write, the design is not ready for production traffic.

## Observability cardinality around typescript strict mode migration

Detail 1 (386): for typescript strict mode migration, define the contract between producers and consumers explicitly — payload shape, timeout, and idempotency key. When observability cardinality around typescript strict mode migration becomes painful, it is usually because that contract was implicit.

I keep a short matrix: who can break typescript strict mode migration, how we detect it within five minutes, and who is paged. Update the matrix when ownership moves. Add one synthetic check that exercises the failure path, not only the happy path. Prefer checks that run continuously over quarterly manual reviews that everyone skips under deadline pressure.

If you only remember one thing about typescript strict mode migration: optimize for reversible decisions. Reversibility beats cleverness when the incident channel is busy and the blast radius is unclear.

## Caching interactions with typescript strict mode migration

Detail 2 (150): for typescript strict mode migration, define the contract between producers and consumers explicitly — payload shape, timeout, and idempotency key. When caching interactions with typescript strict mode migration becomes painful, it is usually because that contract was implicit.

I keep a short matrix: who can break typescript strict mode migration, how we detect it within five minutes, and who is paged. Update the matrix when ownership moves. Add one synthetic check that exercises the failure path, not only the happy path. Prefer checks that run continuously over quarterly manual reviews that everyone skips under deadline pressure.

If you only remember one thing about typescript strict mode migration: optimize for reversible decisions. Reversibility beats cleverness when the incident channel is busy and the blast radius is unclear.