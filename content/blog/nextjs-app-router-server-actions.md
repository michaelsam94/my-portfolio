---
title: "Server Actions in the App Router"
slug: "nextjs-app-router-server-actions"
description: "Use Next.js Server Actions for form mutations and data updates: progressive enhancement, validation, revalidation, and security patterns."
datePublished: "2025-08-22"
dateModified: "2026-07-17"
tags:
keywords: "Next.js Server Actions, App Router mutations, useFormState, server-side form handling, revalidatePath, progressive enhancement"
faq:
  - q: "When should I use Server Actions instead of API routes?"
    a: "Use Server Actions for form submissions and mutations triggered from React components in the same Next.js app. Use API routes when external clients, webhooks, or non-React consumers need the endpoint, or when you need fine-grained HTTP method and header control."
  - q: "Do Server Actions work without JavaScript?"
    a: "Yes. Server Actions are HTML form actions under the hood. With the form action attribute pointing to a server function, the form submits via POST even when JS fails to load. useFormStatus and client-side optimistic updates require JS."
  - q: "How do I prevent CSRF attacks on Server Actions?"
    a: "Next.js validates the Origin header and sets encrypted action IDs automatically in production. Do not disable these checks. For additional protection, include a CSRF token in forms handling sensitive operations."
---
You added a "Save profile" form and reached for `fetch('/api/profile', { method: 'PATCH' })` out of habit. In the App Router, Server Actions let you call an async function on the server directly from a form or event handler—no API route boilerplate, no client-side fetch wrapper, and the form works before hydration completes. The mental model shift is treating server mutations like regular functions with `"use server"` at the top of the file.

## Defining a Server Action

```typescript
// app/actions/profile.ts
"use server";

import { revalidatePath } from "next/cache";
import { z } from "zod";
import { db } from "@/lib/db";
import { auth } from "@/lib/auth";

const ProfileSchema = z.object({
  name: z.string().min(1).max(100),
  bio: z.string().max(500).optional(),
});

export async function updateProfile(formData: FormData) {
  const session = await auth();
  if (!session?.user?.id) throw new Error("Unauthorized");

  const parsed = ProfileSchema.safeParse({
    name: formData.get("name"),
    bio: formData.get("bio"),
  });
  if (!parsed.success) {
    return { error: parsed.error.flatten().fieldErrors };
  }

  await db.user.update({
    where: { id: session.user.id },
    data: parsed.data,
  });

  revalidatePath("/settings");
  return { success: true };
}
```

The `"use server"` directive marks exported functions as callable from the client via a secure POST channel.

## Form integration

```tsx
// app/settings/page.tsx
import { updateProfile } from "@/app/actions/profile";

export default function SettingsPage() {
  return (
    <form action={updateProfile}>
      <input name="name" required />
      <textarea name="bio" />
      <button type="submit">Save</button>
    </form>
  );
}
```

No `onSubmit`, no `preventDefault`. The browser POSTs to Next.js, which invokes your function.

## Client-side pending states

```tsx
"use client";

import { useFormStatus, useFormState } from "react-dom";
import { updateProfile } from "@/app/actions/profile";

function SubmitButton() {
  const { pending } = useFormStatus();
  return (
    <button type="submit" disabled={pending}>
      {pending ? "Saving…" : "Save"}
    </button>
  );
}

export function ProfileForm() {
  const [state, action] = useFormState(updateProfile, null);

  return (
    <form action={action}>
      <input name="name" />
      {state?.error?.name && <p>{state.error.name}</p>}
      <SubmitButton />
    </form>
  );
}
```

`useFormStatus` must be called from a child of the form—wrapping the button in its own component is required.

## Revalidation after mutations

```typescript
import { revalidatePath, revalidateTag } from "next/cache";

// Invalidate a specific page
revalidatePath("/posts");

// Invalidate all pages using a fetch cache tag
revalidateTag("posts");

// Invalidate dynamic segment
revalidatePath("/posts/[slug]", "page");
```

Call revalidation inside the Server Action after the database write succeeds. Stale cache is worse than a slow response.

## Calling actions from event handlers

```tsx
"use client";

import { deletePost } from "@/app/actions/posts";

export function DeleteButton({ postId }: { postId: string }) {
  return (
    <button
      onClick={async () => {
        await deletePost(postId);
      }}
    >
      Delete
    </button>
  );
}
```

Server Actions accept serializable arguments—strings, numbers, plain objects, FormData, and arrays thereof. Not functions, class instances, or DOM nodes.

## Security checklist

- **Authenticate inside every action.** Middleware may protect routes, but actions are separate entry points.
- **Validate all inputs** with Zod or similar—never trust FormData.
- **Authorize resource ownership** before update/delete.
- **Rate limit** sensitive actions (password change, account deletion) at the action level or via middleware.
- **Never expose secrets** in action return values—they serialize to the client.

## Server Actions vs Route Handlers

| Concern | Server Action | Route Handler |
|---------|--------------|---------------|
| Form POST | Native | Manual parsing |
| External API consumers | No | Yes |
| Custom HTTP status codes | Limited | Full control |
| File uploads | FormData works | Raw body access |
| Caching headers | Not applicable | Full control |

Use both: Server Actions for in-app mutations, Route Handlers for webhooks and public APIs.

## Error handling

```typescript
export async function createPost(formData: FormData) {
  try {
    // ... validation and insert
    return { success: true, id: post.id };
  } catch (e) {
    console.error("createPost failed", e);
    return { error: "Failed to create post. Try again." };
  }
}
```

Uncaught exceptions return a generic error to the client. Return structured errors for expected failures (validation, conflicts).

## Optimistic updates with useOptimistic

React 19's `useOptimistic` pairs with Server Actions for instant UI feedback:

```tsx
"use client";
import { useOptimistic } from "react";
import { toggleTodo } from "./actions";

export function TodoList({ todos }) {
  const [optimistic, addOptimistic] = useOptimistic(todos, (state, id) =>
    state.map(t => t.id === id ? { ...t, done: !t.done } : t)
  );

  return optimistic.map(todo => (
    <form key={todo.id} action={async () => {
      addOptimistic(todo.id);
      await toggleTodo(todo.id);
    }}>
      <button>{todo.done ? "✓" : "○"} {todo.text}</button>
    </form>
  ));
}
```

Optimistic state reverts automatically if the action throws — handle errors in the action return value for user-visible rollback messages.

## revalidatePath vs revalidateTag

Cache invalidation after mutations:

```typescript
"use server";
import { revalidatePath, revalidateTag } from "next/cache";

export async function updateProduct(id: string, data: FormData) {
  await db.product.update({ where: { id }, data: ... });
  revalidateTag(`product-${id}`);      // granular
  revalidatePath("/products");          // page-level
}
```

Tag-based revalidation scales better — one product update doesn't invalidate the entire site. Fetch with `{ next: { tags: [`product-${id}`] } }`.

Pair with [Next.js metadata SEO API](https://blog.michaelsam94.com/nextjs-metadata-seo-api/) when server actions update content that affects page metadata.

## Resources

- [Next.js Server Actions docs](https://nextjs.org/docs/app/building-your-application/data-fetching/server-actions-and-mutations) — official guide
- [React useFormStatus](https://react.dev/reference/react-dom/hooks/useFormStatus) — pending state hook
- [React useFormState](https://react.dev/reference/react-dom/hooks/useFormState) — action result state
- [Next.js revalidatePath](https://nextjs.org/docs/app/api-reference/functions/revalidatePath) — cache invalidation
- [Zod validation library](https://zod.dev/) — input schema validation

## Production notes for LLM stacks

When `nextjs-app-router-server-actions` sits on an inference or RAG path, treat user prompts and retrieved chunks as untrusted input. Log correlation IDs and policy decisions—not raw prompts—in production telemetry. Gate risky operations behind explicit authorization at the gateway, not inside ad-hoc tool handlers.

Roll out changes with shadow mode first: record what **would** have happened under the new rule without blocking traffic. Compare deny rates, latency impact, and false positives for at least one business week before enforcing. Pair enforcement with a runbook entry: symptom, dashboard, rollback (feature flag or config), and owner.

Load-test with production-shaped concurrency. LLM workloads burst differently from CRUD APIs—tail latency and token throttling dominate. If `server actions in the app router` protects an invariant (security, billing, data residency), prove the invariant with an automated test that fails CI when someone removes the check.

## What teams get wrong

Teams copy a reference architecture without matching their compliance tier, then discover in audit that logs, backups, or support exports reintroduced the data they thought they had eliminated. Another pattern: shipping the demo integration without idempotency, then fighting duplicate side effects when clients retry on model timeouts.

Document the tradeoff you chose—strictness vs recall, cost vs quality, sync vs async—and the metric that tells you if the choice still holds six months later.
