---
title: "Form Validation with Zod"
slug: "forms-validation-zod-react-hook-form"
description: "Zod schemas validate forms with TypeScript inference. Pair with react-hook-form for performant registration, error messages, and server error mapping."
datePublished: "2025-04-07"
dateModified: "2025-04-07"
tags: ["Web", "Frontend", "React", "TypeScript"]
keywords: "Zod validation, react-hook-form zodResolver, TypeScript form validation, schema validation React, z.infer"
faq:
  - q: "Zod vs Yup vs Joi for React forms?"
    a: "Zod leads in TypeScript projects because schemas infer static types with z.infer. Yup is mature and similar API; Joi targets Node more often. Zod plus @hookform/resolvers is the common 2025 stack for client forms."
  - q: "How do I validate on blur vs submit?"
    a: "react-hook-form mode option: onSubmit (default), onBlur, onChange, or all. Zod runs when resolver triggers validation—combine mode with reValidateMode for UX after first submit."
  - q: "Can one Zod schema validate client and server?"
    a: "Yes—share schema package between Next.js API routes and React client. Parse req.body with schema.safeParse on server; same schema in zodResolver on client. Single source of truth reduces drift."
---

We duplicated email regex in three files—component, API route, and OpenAPI comment that nobody updated. Zod collapsed validation into one schema; TypeScript knew the shape of valid form data before we reached for autocomplete. Hooking it to react-hook-form removed the re-render storm from controlled inputs on every keystroke.

## Schema definition

```typescript
import { z } from 'zod';

export const signupSchema = z.object({
  email: z.string().email('Enter a valid email'),
  password: z
    .string()
    .min(8, 'At least 8 characters')
    .regex(/[A-Z]/, 'Include an uppercase letter'),
  age: z.coerce.number().int().min(18, 'Must be 18 or older'),
});

export type SignupInput = z.infer<typeof signupSchema>;
```

`z.infer` exports TypeScript type from schema—no duplicate interfaces.

## react-hook-form integration

```bash
npm install react-hook-form @hookform/resolvers zod
```

```tsx
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';

export function SignupForm() {
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    setError,
  } = useForm<SignupInput>({
    resolver: zodResolver(signupSchema),
    mode: 'onBlur',
  });

  const onSubmit = async (data: SignupInput) => {
    const res = await fetch('/api/signup', {
      method: 'POST',
      body: JSON.stringify(data),
    });
    if (res.status === 409) {
      setError('email', { message: 'Email already registered' });
      return;
    }
    // success path
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)}>
      <input {...register('email')} aria-invalid={!!errors.email} />
      {errors.email && <p role="alert">{errors.email.message}</p>}

      <input type="password" {...register('password')} />
      {errors.password && <p role="alert">{errors.password.message}</p>}

      <button type="submit" disabled={isSubmitting}>Sign up</button>
    </form>
  );
}
```

`register` keeps inputs uncontrolled for performance—validation runs on configured mode.

## Refinements and cross-field rules

```typescript
const passwordSchema = z
  .object({
    password: z.string().min(8),
    confirm: z.string(),
  })
  .refine((data) => data.password === data.confirm, {
    message: 'Passwords must match',
    path: ['confirm'],
  });
```

`path` attaches error to confirm field.

## Optional and discriminated unions

```typescript
const paymentSchema = z.discriminatedUnion('method', [
  z.object({ method: z.literal('card'), last4: z.string().length(4) }),
  z.object({ method: z.literal('paypal'), email: z.string().email() }),
]);
```

Exhaustive handling in UI with switch on `method`.

## Server-side reuse

```typescript
// api/signup.ts
const parsed = signupSchema.safeParse(await req.json());
if (!parsed.success) {
  return Response.json(
    { errors: parsed.error.flatten().fieldErrors },
    { status: 400 },
  );
}
const { email, password } = parsed.data;
```

Map `flatten().fieldErrors` to `setError` on client for consistent messages.

## Custom error maps

```typescript
z.setErrorMap((issue, ctx) => {
  if (issue.code === z.ZodIssueCode.invalid_type) {
    return { message: 'Required field' };
  }
  return { message: ctx.defaultError };
});
```

Global friendly copy for generic Zod errors.

## Testing schemas

```typescript
expect(signupSchema.safeParse({ email: 'bad', password: 'x', age: 17 }).success)
  .toBe(false);
```

Unit test schemas without rendering React—fast feedback on rule changes.

## Server field errors mapping

```typescript
const { fieldErrors } = parsed.error.flatten();
(Object.entries(fieldErrors) as [keyof SignupInput, string[]][]).forEach(
  ([field, messages]) => {
    if (messages?.[0]) setError(field, { message: messages[0] });
  },
);
```

Keeps client and server validation messages aligned.

## i18n with Zod

Custom error map reading `t()` from i18next for localized messages—define schemas per locale or map issue codes to translation keys.

## Async validation

```typescript
z.string().refine(async (email) => !(await emailTaken(email)), {
  message: 'Email already registered',
});
```

Use sparingly—debounce in UI; async refine on every keystroke hammers API.

## Schema composition

```typescript
const baseUser = z.object({ email: z.string().email() });
const signupSchema = baseUser.extend({ password: passwordSchema });
const updateSchema = baseUser.partial();
```

DRY across create/update forms.


## Default values and Zod coercion

`z.coerce.number()` on empty string yields 0—pair with `.min(1)` or preprocess empty to undefined:

```typescript
z.preprocess(
  (v) => (v === '' ? undefined : v),
  z.coerce.number().optional(),
);
```

## Form reset after submit

```typescript
reset(defaultValues);
```

Reset validation state—`reset` clears errors; call after successful submit before showing confirmation.

## Accessibility

Associate errors with inputs via `aria-describedby` pointing to error element id—react-hook-form `formState.errors` ids should match for screen readers.

## Performance on large forms

Split into steps with separate schemas composed—validate step schema on Next, full schema on Submit—reduces re-validation cost on 40-field admin forms.

## Field arrays

react-hook-form useFieldArray with Zod array schema—validate min/max items for dynamic tag inputs; error paths include index `tags.2` mapped with setError.

## Rollout guidance

Schema major version bump coordinated with mobile app minimum version force upgrade if API rejects old clients—backend returns structured validation error code mobile maps to store update prompt when schema mismatch detected.

## Team practices

Shipping Forms Validation Zod React Hook Form in production taught our team that documentation beats hero demos. We wrote runbooks covering failure modes, on-call steps, and rollback triggers before the second release, not after the first outage.

When reviewing PRs touching Forms Validation Zod React Hook Form, we ask for measurable outcomes: latency, crash rate, or support ticket volume—not subjective feels faster. If metrics are unavailable, the PR includes a DevTools trace or load test snippet proving the change.

Onboarding engineers paste a checklist into their first Forms Validation Zod React Hook Form PR description: environment setup verified, tests added or updated, accessibility spot-checked, and release notes drafted for user-visible changes.

We keep a living FAQ in the repo wiki for Forms Validation Zod React Hook Form questions repeated in Slack more than twice. FAQ entries link to source files and Slack threads, reducing tribal knowledge and repeated explanations in code review.

Cross-functional review includes design for UX-facing work, security for auth or storage, and platform for native bridges. Forms Validation Zod React Hook Form spans layers; skipping reviewers recreated bugs we fixed months ago.

## Resources

- [Zod documentation](https://zod.dev/)
- [react-hook-form docs](https://react-hook-form.com/)
- [@hookform/resolvers](https://github.com/react-hook-form/resolvers)
- [TypeScript inference with z.infer](https://zod.dev/?id=type-inference)
- [Server Actions validation patterns (Next.js)](https://nextjs.org/docs/app/building-your-application/data-fetching/server-actions-and-mutations)
