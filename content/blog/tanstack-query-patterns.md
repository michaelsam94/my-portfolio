---
title: "TanStack Query Patterns for Server State"
slug: "tanstack-query-patterns"
description: "Practical TanStack Query patterns for server state: query keys, cache invalidation, optimistic mutations, and prefetching that keep React apps fast and consistent."
datePublished: "2026-06-24"
dateModified: "2026-06-24"
tags: ["React", "TanStack Query", "State Management", "Frontend"]
keywords: "TanStack Query, React Query, server state, data fetching, caching React, mutations, query keys"
faq:
  - q: "What problem does TanStack Query solve?"
    a: "TanStack Query manages server state — data that lives on a backend and is fetched asynchronously — including caching, background refetching, deduplication, and staleness. It replaces the hand-rolled loading/error/data useEffect boilerplate and keeps cached server data consistent across your components."
  - q: "Should I use TanStack Query or a global store like Redux?"
    a: "Use TanStack Query for server state (anything fetched from an API) and a lightweight client-state tool for genuine UI state. Most apps that adopt TanStack Query find their global store shrinks dramatically, because the majority of what was in it was really cached server data."
  - q: "How does query invalidation work in TanStack Query?"
    a: "You call queryClient.invalidateQueries with a query key, which marks matching cached queries as stale and triggers a refetch for any that are actively rendered. Because query keys are hierarchical, invalidating a prefix invalidates all queries nested under it, which makes cache updates after mutations straightforward."
---

The single most useful reframing TanStack Query gives you is that **server state is not client state**. The data in your Redux store that came from an API isn't really application state you own — it's a local cache of state that lives on a server, and it can go stale the moment you fetch it. Treating cached server data like owned client state is why so many React apps accumulate tangled `useEffect` fetching, manual loading flags, and stores full of data that's silently out of date. TanStack Query (formerly React Query) exists to manage that cache properly.

I'll skip the "what is a query" intro and go straight to the patterns that actually determine whether a TanStack Query codebase stays clean or turns into a mess: query keys, invalidation, optimistic mutations, and prefetching.

## Query keys are your cache's schema — design them

Everything in TanStack Query hangs off the query key. It's the cache identity, the dependency array, and the invalidation target all at once. Sloppy keys are the root cause of most "stale data" and "why did everything refetch" complaints. The pattern that scales is hierarchical, structured keys — general to specific:

```ts
const todoKeys = {
  all: ["todos"] as const,
  lists: () => [...todoKeys.all, "list"] as const,
  list: (filters: string) => [...todoKeys.lists(), filters] as const,
  details: () => [...todoKeys.all, "detail"] as const,
  detail: (id: string) => [...todoKeys.details(), id] as const,
};

useQuery({ queryKey: todoKeys.list("active"), queryFn: () => fetchTodos("active") });
useQuery({ queryKey: todoKeys.detail(id), queryFn: () => fetchTodo(id) });
```

The payoff is precise invalidation. `invalidateQueries({ queryKey: todoKeys.all })` refetches everything todo-related; `todoKeys.lists()` refetches only the lists and leaves individual details cached; `todoKeys.detail(id)` refetches one item. Because keys are matched by prefix, this hierarchy gives you exactly the granularity you need. Centralizing keys in a factory object like this — rather than scattering string arrays across files — is the difference between a maintainable cache and a guessing game.

## staleTime is the setting everyone gets wrong

By default TanStack Query treats data as immediately stale (`staleTime: 0`), which means it refetches aggressively on mount, window focus, and reconnect. That's safe but chatty, and it's why newcomers see "it fetches constantly." The fix is to set `staleTime` deliberately based on how fresh each kind of data needs to be:

```ts
useQuery({
  queryKey: todoKeys.detail(id),
  queryFn: () => fetchTodo(id),
  staleTime: 60_000,       // trust this data for 60s before refetching
});
```

Think of `staleTime` as "how long is this data good enough" and `gcTime` (garbage collection time) as "how long to keep it cached after nothing is using it." A reference list that changes hourly can have a `staleTime` of minutes; a live price should be seconds or zero. Setting this per-query is the main lever for balancing freshness against request volume, and it's directly relevant when your users are on [flaky mobile networks](https://blog.michaelsam94.com/handling-flaky-networks-mobile/) where every avoided refetch matters.

## Optimistic mutations without the mess

Mutations are where apps feel fast or sluggish. The naive flow — mutate, wait for the server, refetch, then update the UI — makes every action feel like it lags. Optimistic updates apply the change locally first and roll back if the server rejects it. TanStack Query has a clean structure for this with `onMutate`, `onError`, and `onSettled`:

```ts
useMutation({
  mutationFn: (updated: Todo) => api.updateTodo(updated),
  onMutate: async (updated) => {
    await queryClient.cancelQueries({ queryKey: todoKeys.detail(updated.id) });
    const previous = queryClient.getQueryData(todoKeys.detail(updated.id));
    queryClient.setQueryData(todoKeys.detail(updated.id), updated); // optimistic
    return { previous };                                            // context for rollback
  },
  onError: (_err, updated, ctx) => {
    queryClient.setQueryData(todoKeys.detail(updated.id), ctx?.previous); // rollback
  },
  onSettled: (_data, _err, updated) => {
    queryClient.invalidateQueries({ queryKey: todoKeys.detail(updated.id) }); // reconcile
  },
});
```

The three-phase shape is the pattern worth memorizing: snapshot and apply in `onMutate`, restore the snapshot in `onError`, and reconcile against the server in `onSettled`. The `cancelQueries` call matters — it prevents an in-flight refetch from clobbering your optimistic update with stale data. This gives instant-feeling UI with correct rollback, and it's the same optimistic-update discipline I use for offline writes on mobile.

## Prefetch to kill the loading spinner

The best loading state is none. When you can predict what the user will need next — hovering a link, viewing a list before a detail — prefetch it so the data is warm in the cache by the time they navigate:

```ts
// On hover or in a server component / route loader
queryClient.prefetchQuery({
  queryKey: todoKeys.detail(id),
  queryFn: () => fetchTodo(id),
});
```

Prefetching turns navigation that would show a spinner into an instant transition. Paired with `staleTime`, the prefetched data is served immediately and only refetched if it's gone stale. In frameworks doing server rendering, you can prefetch on the server and hydrate the cache so the client mounts with data already present — which composes neatly with the streaming model in [React Server Components](https://blog.michaelsam94.com/react-server-components-production/).

## Don't put server state in your global store

The architectural consequence of adopting TanStack Query is that your global client store should shrink. Before, teams dumped fetched data into Redux/Zustand and wrote reducers to keep it fresh. With TanStack Query owning the server cache, the global store is left with what it should have always held: genuine client state — UI toggles, form drafts, the current theme, a wizard's step. That separation — server state in the query cache, client state in a small store — is the cleanest React data architecture I've worked in, and it removes a whole category of "the store is stale" bugs.

## A few patterns that pay off

- **`enabled` for dependent queries.** Gate a query on data it needs: `enabled: !!userId` so it waits for the id instead of firing with `undefined`.
- **`select` to derive and narrow.** Transform or pick fields in `select` so components re-render only when the slice they use changes.
- **`placeholderData` for smooth pagination.** Keep the previous page's data visible while the next loads, avoiding a flash of empty state.
- **Retry config for resilience.** TanStack Query retries failed queries by default; tune it so client errors don't retry and transient failures do — the same backoff thinking as any network layer.

## The bottom line

TanStack Query is less a fetching library than a server-state cache manager, and using it well is mostly about respecting that framing. Design hierarchical query keys so invalidation is surgical. Set `staleTime` per query instead of fighting the defaults. Structure mutations with the snapshot/rollback/reconcile pattern for instant, correct UI. Prefetch predictable navigations. And let it own server state so your client store stays small. Do those and your data layer stops being the buggy, boilerplate-heavy part of the app and becomes the part you don't think about — which is the whole goal.

## Resources

- [TanStack Query documentation](https://tanstack.com/query/latest)
- [TanStack Query: Query Keys guide](https://tanstack.com/query/latest/docs/framework/react/guides/query-keys)
- [TanStack Query: Optimistic Updates](https://tanstack.com/query/latest/docs/framework/react/guides/optimistic-updates)
- [React docs: You Might Not Need an Effect](https://react.dev/learn/you-might-not-need-an-effect)
- [TkDodo's blog: Practical React Query](https://tkdodo.eu/blog/practical-react-query)
- [MDN: Using Fetch](https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API/Using_Fetch)
