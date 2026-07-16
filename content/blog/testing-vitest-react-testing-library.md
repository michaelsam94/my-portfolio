---
title: "Testing React with Vitest"
slug: "testing-vitest-react-testing-library"
description: "Vitest brings fast unit testing to React with native ESM support, Jest-compatible API, and instant HMR. Pair it with Testing Library for behavior-focused component tests."
datePublished: "2026-01-26"
dateModified: "2026-01-26"
tags: ["Testing", "React", "Vitest", "Frontend"]
keywords: "Vitest React testing, React Testing Library, Vitest vs Jest, component testing React, Vitest configuration, userEvent testing"
faq:
  - q: "Should I use Vitest or Jest for a new React project?"
    a: "Use Vitest if your project uses Vite (which most new React projects do). Vitest shares Vite's config, transform pipeline, and ESM support — tests start instantly with native TypeScript. Use Jest if you're on Create React App (Webpack), need specific Jest-only plugins, or have an existing Jest suite you don't want to migrate. Vitest's API is Jest-compatible, so migration is mostly config changes."
  - q: "What should I test in a React component?"
    a: "Test behavior users experience: does clicking Submit send the form? Does an error message appear on invalid input? Does loading state show while fetching? Don't test implementation details — state variable names, internal hook calls, component structure. If a refactor changes internal state management but the UI behavior is identical, tests should still pass."
  - q: "How do I test components that fetch data?"
    a: "Mock the fetch/API layer with MSW (Mock Service Worker) or vi.mock(). Render the component, let it fetch mocked data, assert on rendered output. Use findBy queries (async) for data that loads after render. Test three states: loading, success, and error. Don't mock React hooks — mock the data source the hooks call."
---

Migrating our React test suite from Jest to Vitest cut cold start from 14 seconds to 1.2 seconds. Not because Vitest runs tests faster — the tests themselves take similar time — but because Vitest reuses Vite's already-warm transform pipeline instead of spinning up a separate Babel/Jest config. With 800 component tests, that 12-second difference changed whether developers ran tests on every save or skipped them until CI.

Vitest is a unit test framework built on Vite. It provides a Jest-compatible API (`describe`, `it`, `expect`, `vi.mock`) with native ESM, TypeScript, and JSX support. Combined with React Testing Library, it enables fast, behavior-focused component tests that verify what users see and do.

## Setup

```bash
npm install -D vitest @testing-library/react @testing-library/jest-dom \
  @testing-library/user-event jsdom
```

```typescript
// vite.config.ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
  },
});
```

```typescript
// src/test/setup.ts
import "@testing-library/jest-dom/vitest";
```

```json
// package.json
{ "scripts": { "test": "vitest", "test:ci": "vitest run" } }
```

One config file for both dev server and tests. No separate Jest config, Babel config, or transform overrides.

## Testing component behavior

```tsx
// Counter.tsx
export function Counter() {
  const [count, setCount] = useState(0);
  return (
    <div>
      <p>Count: {count}</p>
      <button onClick={() => setCount(c => c + 1)}>Increment</button>
    </div>
  );
}
```

```tsx
// Counter.test.tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Counter } from "./Counter";

test("increments count on button click", async () => {
  const user = userEvent.setup();
  render(<Counter />);

  expect(screen.getByText("Count: 0")).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Increment" }));

  expect(screen.getByText("Count: 1")).toBeInTheDocument();
});
```

Query by role and accessible name — the same way assistive technology finds elements. Test what the user sees, not component internals.

## Testing async data loading

```tsx
// UserProfile.tsx — fetches user on mount
export function UserProfile({ userId }: { userId: string }) {
  const { data, isLoading, error } = useQuery(["user", userId], () =>
    fetchUser(userId)
  );

  if (isLoading) return <p>Loading...</p>;
  if (error) return <p>Error loading user</p>;
  return <h1>{data.name}</h1>;
}
```

```tsx
// UserProfile.test.tsx
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { vi } from "vitest";
import { UserProfile } from "./UserProfile";

vi.mock("./api", () => ({
  fetchUser: vi.fn(),
}));

import { fetchUser } from "./api";

function renderWithQuery(ui: React.ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>{ui}</QueryClientProvider>
  );
}

test("shows user name after loading", async () => {
  vi.mocked(fetchUser).mockResolvedValue({ name: "Ada Lovelace" });

  renderWithQuery(<UserProfile userId="123" />);

  expect(screen.getByText("Loading...")).toBeInTheDocument();
  expect(await screen.findByRole("heading", { name: "Ada Lovelace" }))
    .toBeInTheDocument();
});

test("shows error on fetch failure", async () => {
  vi.mocked(fetchUser).mockRejectedValue(new Error("Network error"));

  renderWithQuery(<UserProfile userId="123" />);

  expect(await screen.findByText("Error loading user")).toBeInTheDocument();
});
```

`findBy` queries wait for elements to appear — essential for async rendering. Mock at the API module level, not the hook level.

## MSW for API mocking

For tests that hit multiple endpoints or need realistic HTTP behavior:

```typescript
// src/test/handlers.ts
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

export const handlers = [
  http.get("/api/users/:id", ({ params }) => {
    return HttpResponse.json({ id: params.id, name: "Ada Lovelace" });
  }),
];

export const server = setupServer(...handlers);
```

```typescript
// src/test/setup.ts
import { server } from "./handlers";
beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
```

MSW intercepts fetch at the network level — components use real fetch calls, tests control responses. More realistic than mocking fetch directly.

## Testing forms and user input

```tsx
test("submits form with valid data", async () => {
  const onSubmit = vi.fn();
  const user = userEvent.setup();

  render(<LoginForm onSubmit={onSubmit} />);

  await user.type(screen.getByLabelText("Email"), "ada@example.com");
  await user.type(screen.getByLabelText("Password"), "secret123");
  await user.click(screen.getByRole("button", { name: "Sign in" }));

  expect(onSubmit).toHaveBeenCalledWith({
    email: "ada@example.com",
    password: "secret123",
  });
});

test("shows validation error for empty email", async () => {
  const user = userEvent.setup();
  render(<LoginForm onSubmit={vi.fn()} />);

  await user.click(screen.getByRole("button", { name: "Sign in" }));

  expect(screen.getByText("Email is required")).toBeInTheDocument();
});
```

`userEvent` simulates realistic input — focus, keydown, input, keyup events — unlike `fireEvent` which dispatches a single event.

## Vitest-specific features

```typescript
// Inline snapshots
expect(formatPrice(1234.5)).toMatchInlineSnapshot(`"$1,234.50"`);

// Test concurrent rendering
test.concurrent("renders list items", async () => { /* ... */ });

// Watch mode with HMR — tests re-run on save instantly
// vitest --watch (default in dev)

// Coverage
// vitest run --coverage
```

## Testing async data with MSW

Mock Service Worker intercepts network requests at the service worker level, so your components call real fetch while tests control responses:

```typescript
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';

const server = setupServer(
  http.get('/api/user', () => HttpResponse.json({ name: 'Ada' })),
);

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
```

MSW catches bugs that vi.mock misses because the component still runs its actual fetch logic — only the network boundary is mocked.

## Snapshot testing: use sparingly

Snapshot tests break on intentional UI changes and encourage approving diffs without reading them. Prefer asserting on visible text and roles. If you snapshot, limit to stable structural components — not entire pages that change weekly.

## CI parallelization

Vitest runs test files in parallel by default. Split slow integration suites into separate CI jobs if total time exceeds your budget. Use `test.concurrent` within files only when tests don't share mutable state.

## Resources

- [Vitest documentation](https://vitest.dev/guide/)
- [React Testing Library docs](https://testing-library.com/docs/react-testing-library/intro/)
- [Testing Library query priorities](https://testing-library.com/docs/queries/about/#priority)
- [MSW (Mock Service Worker) documentation](https://mswjs.io/docs/)
- [Vitest migration from Jest guide](https://vitest.dev/guide/migration.html)
