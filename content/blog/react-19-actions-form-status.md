---
title: "React 19 Actions and Form Status"
slug: "react-19-actions-form-status"
description: "Use React 19 Actions and useFormStatus for form submissions: server actions, pending states, optimistic updates, and progressive enhancement."
datePublished: "2025-02-05"
dateModified: "2025-02-05"
tags: ["React", "Web", "Forms", "React 19"]
keywords: "React 19 actions, useFormStatus, useActionState, server actions, form pending state, React forms"
faq:
  - q: "What are React 19 Actions?"
    a: "Actions are async functions passed to form action props or called from useTransition that React tracks as transitions. When an action runs, React manages pending state, error handling, and optimistic updates automatically. Server Actions are Actions that execute on the server, letting forms submit without manual fetch boilerplate."
  - q: "How does useFormStatus differ from managing loading state manually?"
    a: "useFormStatus reads pending state from the nearest parent form's pending Action — no prop drilling or context setup. It only works inside components rendered as children of a form using an Action. The hook returns pending, data, method, and action fields, giving child components like submit buttons access to submission state without coupling to parent state management."
  - q: "Do React 19 form Actions work without JavaScript?"
    a: "Server Actions submitted via form action attributes work as standard HTML form POST requests when JavaScript is unavailable — the browser submits the form natively. React enhances the experience with client-side pending states and optimistic updates when JS is present. This is progressive enhancement: the form works either way."
---

Every form you have ever built in React followed the same ceremony: `useState` for loading, `e.preventDefault()`, a `fetch` call, error parsing, and a spinner wired to `isSubmitting`. React 19 Actions collapse that boilerplate — pass an async function to `<form action={...}>`, read pending state from `useFormStatus`, and let React manage the transition. Server Actions push it further by running the function on the server.

## Actions and form submission

An Action is an async function React treats as a transition:

```tsx
async function createTodo(formData: FormData) {
  "use server"; // Server Action (Next.js / React Server Components)
  const title = formData.get("title") as string;
  await db.todos.create({ title });
  revalidatePath("/todos");
}

export function TodoForm() {
  return (
    <form action={createTodo}>
      <input name="title" required />
      <SubmitButton />
    </form>
  );
}
```

No `onSubmit` handler. No `preventDefault`. The form's `action` prop accepts the async function directly. React calls it with `FormData` built from the form's named inputs.

## useFormStatus for child components

Submit buttons and status indicators usually live inside the form but need pending state from the parent. `useFormStatus` solves this without prop drilling:

```tsx
import { useFormStatus } from "react-dom";

function SubmitButton() {
  const { pending } = useFormStatus();

  return (
    <button type="submit" disabled={pending}>
      {pending ? "Saving..." : "Save"}
    </button>
  );
}
```

`useFormStatus` only works in components that are **descendants of a `<form>` using an Action**. It reads the nearest form's submission state. Calling it outside that tree throws.

Available fields:

- `pending` — boolean, true while the Action runs.
- `data` — FormData from the in-flight submission.
- `method` — GET or POST.
- `action` — the function or URL being invoked.

## useActionState for result handling

When the Action returns data or errors the UI needs to display, `useActionState` (formerly `useFormState`) manages action state:

```tsx
import { useActionState } from "react";

async function updateProfile(prevState: State, formData: FormData): Promise<State> {
  const name = formData.get("name") as string;
  if (!name) return { error: "Name is required" };
  await api.updateProfile({ name });
  return { success: true };
}

function ProfileForm() {
  const [state, formAction, pending] = useActionState(updateProfile, {});

  return (
    <form action={formAction}>
      <input name="name" />
      {state.error && <p className="error">{state.error}</p>}
      {state.success && <p>Profile updated!</p>}
      <button disabled={pending}>Update</button>
    </form>
  );
}
```

The Action receives the previous state as its first argument, enabling error accumulation and multi-step flows. `pending` is returned directly — no need for `useFormStatus` in the same component (though child components can still use it).

## Client-side Actions without Server Actions

Actions work on the client too — no `"use server"` directive:

```tsx
async function saveSettings(formData: FormData) {
  const theme = formData.get("theme") as string;
  await fetch("/api/settings", {
    method: "POST",
    body: JSON.stringify({ theme }),
    headers: { "Content-Type": "application/json" },
  });
}

function SettingsForm() {
  return (
    <form action={saveSettings}>
      <select name="theme">
        <option value="light">Light</option>
        <option value="dark">Dark</option>
      </select>
      <SubmitButton />
    </form>
  );
}
```

React still tracks this as a transition — `useFormStatus` works, concurrent rendering does not block the UI during the fetch.

## Optimistic updates with useOptimistic

Combine Actions with `useOptimistic` for instant UI feedback:

```tsx
import { useOptimistic } from "react";

function TodoList({ todos }: { todos: Todo[] }) {
  const [optimisticTodos, addOptimistic] = useOptimistic(
    todos,
    (current, newTodo: Todo) => [...current, newTodo]
  );

  async function addTodo(formData: FormData) {
    const title = formData.get("title") as string;
    addOptimistic({ id: "temp", title, done: false });
    await api.createTodo({ title });
  }

  return (
    <>
      <ul>{optimisticTodos.map(t => <li key={t.id}>{t.title}</li>)}</ul>
      <form action={addTodo}>
        <input name="title" />
        <SubmitButton />
      </form>
    </>
  );
}
```

The optimistic item appears immediately. When the Action completes, real data replaces it. If the Action fails, React reverts the optimistic state.

## Error handling

Actions propagate errors through React's error boundary system. Wrap forms in error boundaries for unexpected failures:

```tsx
async function riskyAction(formData: FormData) {
  const result = await api.submit(formData);
  if (!result.ok) {
    return { error: result.message }; // handled via useActionState
  }
  return { success: true };
}
```

Return errors as state for expected failures (validation, business rules). Throw for unexpected failures (network down, 500 responses) so error boundaries catch them.

## Progressive enhancement

Server Actions with `<form action={serverFn}>` degrade gracefully:

- **JS enabled:** React intercepts submission, shows pending state, handles the response client-side.
- **JS disabled:** Browser POSTs the form to the server action endpoint natively. Page reloads with the result.

Build the server-side path first; client enhancements layer on top.

## Common production mistakes

Teams get 19 actions form status wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of 19 actions form status fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Debugging and triage workflow

When 19 actions form status misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [React 19 release notes — Actions](https://react.dev/blog/2024/12/05/react-19)
- [React useFormStatus documentation](https://react.dev/reference/react-dom/hooks/useFormStatus)
- [React useActionState documentation](https://react.dev/reference/react/useActionState)
- [React useOptimistic documentation](https://react.dev/reference/react/useOptimistic)
- [Next.js Server Actions guide](https://nextjs.org/docs/app/building-your-application/data-fetching/server-actions-and-mutations)
