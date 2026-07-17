---
title: "Vue 3 Composition API Patterns"
slug: "vue-3-composition-api-patterns"
description: "Practical Vue 3 Composition API patterns: composables, ref vs reactive, provide/inject, script setup, and migrating from Options API without rewriting everything."
datePublished: "2026-03-07"
dateModified: "2026-07-17"
tags:
  - "Engineering"
keywords: "Vue 3, Composition API, composables, script setup, ref, reactive, provide inject"
faq:
  - q: "What is the main production risk with vue 3 composition api patterns?"
    a: "Teams ship without field measurement—vue 3 composition api patterns failures appear as silent UX regressions, cost drift, or audit findings rather than clear errors."
  - q: "When should we prioritize vue 3 composition api patterns?"
    a: "Prioritize when user research, CrUX, support tickets, or compliance requirements show pain on critical paths—not when a checklist mentions it abstractly."
  - q: "How do we validate vue 3 composition api patterns changes?"
    a: "Baseline RUM before changes, compare p75 after deploy, and keep rollback via feature flags or cache purge documented in the PR."
---

title: "Vue 3 Composition API Patterns"
slug: "vue-3-composition-api-patterns"
description: "Practical Vue 3 Composition API patterns: composables, ref vs reactive, provide/inject, script setup, and migrating from Options API without rewriting everything."
datePublished: "2026-03-07"
dateModified: "2026-07-17"
tags:
  - "Engineering"
keywords: "Vue 3, Composition API, composables, script setup, ref, reactive, provide inject"
faq:
  - q: "What is the main production risk with vue 3 composition api patterns?"
    a: "Teams ship without field measurement—vue 3 composition api patterns failures appear as silent UX regressions, cost drift, or audit findings rather than clear errors."
  - q: "When should we prioritize vue 3 composition api patterns?"
    a: "Prioritize when user research, CrUX, support tickets, or compliance requirements show pain on critical paths—not when a checklist mentions it abstractly."
  - q: "How do we validate vue 3 composition api patterns changes?"
    a: "Baseline RUM before changes, compare p75 after deploy, and keep rollback via feature flags or cache purge documented in the PR."
---
---

title: "vue-3-composition-api-patterns"
slug: "vue-3-composition-api-patterns"
description: ""
datePublished: "2026-07-17"
dateModified: "2026-07-17"
tags:
  - "Engineering"
keywords: "vue-3-composition-api-patterns"
faq:
  - q: "What is the main production risk with vue 3 composition api patterns?"
    a: "Teams ship without field measurement—vue 3 composition api patterns failures appear as silent UX regressions, cost drift, or audit findings rather than clear errors."
  - q: "When should we prioritize vue 3 composition api patterns?"
    a: "Prioritize when user research, CrUX, support tickets, or compliance requirements show pain on critical paths—not when a checklist mentions it abstractly."
  - q: "How do we validate vue 3 composition api patterns changes?"
    a: "Baseline RUM before changes, compare p75 after deploy, and keep rollback via feature flags or cache purge documented in the PR."
---
---

title: "vue-3-composition-api-patterns"
slug: "vue-3-composition-api-patterns"
description: ""
datePublished: "2026-07-17"
dateModified: "2026-07-17"
tags:
  - "Engineering"
keywords: "vue-3-composition-api-patterns"
faq:
  - q: "What is the main production risk with vue 3 composition api patterns?"
    a: "Teams ship without field measurement—vue 3 composition api patterns failures appear as silent UX regressions, cost drift, or audit findings rather than clear errors."
  - q: "When should we prioritize vue 3 composition api patterns?"
    a: "Prioritize when user research, CrUX, support tickets, or compliance requirements show pain on critical paths—not when a checklist mentions it abstractly."
  - q: "How do we validate vue 3 composition api patterns changes?"
    a: "Baseline RUM before changes, compare p75 after deploy, and keep rollback via feature flags or cache purge documented in the PR."
---
---

title: "vue-3-composition-api-patterns"
slug: "vue-3-composition-api-patterns"
description: ""
datePublished: "2026-07-17"
dateModified: "2026-07-17"
tags:
  - "Engineering"
keywords: "vue-3-composition-api-patterns"
faq:
  - q: "What is the main production risk with vue 3 composition api patterns?"
    a: "Teams ship without field measurement—vue 3 composition api patterns failures appear as silent UX regressions, cost drift, or audit findings rather than clear errors."
  - q: "When should we prioritize vue 3 composition api patterns?"
    a: "Prioritize when user research, CrUX, support tickets, or compliance requirements show pain on critical paths—not when a checklist mentions it abstractly."
  - q: "How do we validate vue 3 composition api patterns changes?"
    a: "Baseline RUM before changes, compare p75 after deploy, and keep rollback via feature flags or cache purge documented in the PR."
---
---

title: "Vue 3 Composition API Patterns"
slug: "vue-3-composition-api-patterns"
description: "Practical Vue 3 Composition API patterns: composables, ref vs reactive, provide/inject, script setup, and migrating from Options API without rewriting everything."
datePublished: "2026-03-07"
dateModified: "2026-07-17"
tags:
  - "Engineering"
keywords: "Vue 3, Composition API, composables, script setup, ref, reactive, provide inject"
faq:
  - q: "What is the main production risk with vue 3 composition api patterns?"
    a: "Teams ship without field measurement—vue 3 composition api patterns failures appear as silent UX regressions, cost drift, or audit findings rather than clear errors."
  - q: "When should we prioritize vue 3 composition api patterns?"
    a: "Prioritize when user research, CrUX, support tickets, or compliance requirements show pain on critical paths—not when a checklist mentions it abstractly."
  - q: "How do we validate vue 3 composition api patterns changes?"
    a: "Baseline RUM before changes, compare p75 after deploy, and keep rollback via feature flags or cache purge documented in the PR."
---
---

I inherited a Vue 2 codebase with 40-line mixins that injected mystery properties into every component. `this.fetchData` came from somewhere — the data mixin, the auth mixin, or maybe the route mixin. Tracing behavior meant reading four files. Migrating to Vue 3's Composition API with composables replaced all of that with explicit `const { data, loading } = useFetch(url)` calls at the top of each script setup block. The logic didn't change. The traceability changed completely. These are the patterns I use daily in Vue 3 production code.

## script setup: the default

`<script setup>` is the concise syntax for Composition API components:

```vue
<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'

const count = ref(0)
const doubled = computed(() => count.value * 2)

function increment() {
  count.value++
}

onMounted(() => {
  console.log('mounted with count:', count.value)
})
</script>

<template>
  <button @click="increment">{{ doubled }}</button>
</template>
```

Top-level bindings are automatically exposed to the template. No `return` statement, no `export default`.

## Composables: reusable stateful logic

Extract logic into functions that use Vue's reactivity:

```typescript
// composables/useFetch.ts
import { ref, type Ref } from 'vue'

interface UseFetchReturn<T> {
  data: Ref<T | null>
  error: Ref<string | null>
  loading: Ref<boolean>
  refetch: () => Promise<void>
}

export function useFetch<T>(url: string): UseFetchReturn<T> {
  const data = ref<T | null>(null) as Ref<T | null>
  const error = ref<string | null>(null)
  const loading = ref(true)

  async function refetch() {
    loading.value = true
    error.value = null
    try {
      const res = await fetch(url)
      if (!res.ok) throw new Error(res.statusText)
      data.value = await res.json()
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Unknown error'
    } finally {
      loading.value = false
    }
  }

  refetch()
  return { data, error, loading, refetch }
}
```

Usage in any component:

```vue
<script setup lang="ts">
import { useFetch } from '@/composables/useFetch'

interface User { id: string; name: string }
const { data: users, loading, error, refetch } = useFetch<User[]>('/api/users')
</script>

<template>
  <div v-if="loading">Loading...</div>
  <div v-else-if="error">{{ error }}</div>
  <ul v-else>
    <li v-for="user in users" :key="user.id">{{ user.name }}</li>
  </ul>
</template>
```

## ref vs reactive

```typescript
// ref: works for everything, requires .value in script
const count = ref(0)
const user = ref({ name: 'Alice', age: 30 })

count.value++           // 1
user.value.name = 'Bob' // reactive

// reactive: objects only, no .value, but can't reassign
const state = reactive({ count: 0, items: [] as string[] })
state.count++           // works
state.items.push('a')   // works

// DANGER: destructuring breaks reactivity
const { count } = reactive({ count: 0 })  // count is NOT reactive

// SAFE: use toRefs
const state = reactive({ count: 0, name: 'Alice' })
const { count, name } = toRefs(state)  // both reactive refs
```

My rule: default to `ref`. Use `reactive` only for form state objects where you mutate properties but never replace the object.

## provide/inject for dependency sharing

Skip prop drilling for deeply nested or cross-cutting concerns:

```typescript
// parent component
import { provide, ref, type InjectionKey } from 'vue'

interface Theme { primary: string; mode: 'light' | 'dark' }
const ThemeKey: InjectionKey<Ref<Theme>> = Symbol('theme')

const theme = ref<Theme>({ primary: '#3b82f6', mode: 'light' })
provide(ThemeKey, theme)
```

```typescript
// deeply nested child
import { inject } from 'vue'

const theme = inject(ThemeKey)
if (!theme) throw new Error('Theme not provided')
```

Use typed `InjectionKey` for type safety. Reserve provide/inject for app-wide concerns (theme, auth, i18n) — not for parent-child communication that props handle fine.

## watch and watchEffect

```typescript
// watch: explicit source, runs on change
watch(count, (newVal, oldVal) => {
  console.log(`count: ${oldVal} → ${newVal}`)
})

// watch multiple sources
watch([firstName, lastName], ([first, last]) => {
  fullName.value = `${first} ${last}`
})

// watchEffect: auto-tracks dependencies, runs immediately
watchEffect(() => {
  document.title = `${count.value} items`
})
```

`watchEffect` is for side effects that depend on reactive state (DOM updates, logging). `watch` is for reacting to specific changes with access to old values.

## Migrating from Options API incrementally

Vue 3 supports both APIs in the same component and project:

```vue
<script lang="ts">
import { defineComponent, ref } from 'vue'

export default defineComponent({
  setup() {
    const count = ref(0)
    return { count }
  },
  // Options API still works alongside setup()
  computed: {
    label() { return `Count: ${this.count}` }
  }
})
</script>
```

Migration strategy:
1. New components use `<script setup>` exclusively
2. Existing simple components stay on Options API until touched
3. Complex components migrate to composables when you need to fix a bug or add a feature
4. Extract mixin logic into composables first, then update components one at a time

## Composable composition

Composables can call other composables:

```typescript
function useUserProfile(userId: Ref<string>) {
  const url = computed(() => `/api/users/${userId.value}`)
  const { data, loading, error } = useFetch<User>(url.value)

  watch(userId, () => refetch())

  const displayName = computed(() =>
    data.value ? `${data.value.firstName} ${data.value.lastName}` : ''
  )

  return { profile: data, loading, error, displayName }
}
```

This is the Composition API's core advantage: logic composes like functions, not like mixin chains.

## Advanced composable patterns

**Composable with arguments and defaults:**

```typescript
export function useFetch<T>(url: MaybeRef<string>, options?: RequestInit) {
  const data = ref<T | null>(null)
  const error = ref<Error | null>(null)
  const loading = ref(false)

  async function execute() {
    loading.value = true
    try {
      const res = await fetch(toValue(url), options)
      data.value = await res.json()
    } catch (e) {
      error.value = e as Error
    } finally {
      loading.value = false
    }
  }

  watch(() => toValue(url), execute, { immediate: true })
  return { data, error, loading, execute }
}
```

**Shared state via composable factory:**

```typescript
const createState = () => {
  const count = ref(0)
  return { count, increment: () => count.value++ }
}
let instance: ReturnType<typeof createState> | null = null
export function useSharedCounter() {
  if (!instance) instance = createState()
  return instance
}
```

Use sparingly—prefer Pinia for truly global state.

## SSR considerations

`onMounted` only runs client-side—fetch in setup without guarding runs on server too. Use `import.meta.env.SSR` or Nuxt's `useAsyncData` for isomorphic data. Mismatch between server HTML and client hydration causes warnings—align initial ref values with server-rendered content.

## DevTools and debugging

Vue DevTools 6 shows setup state, composable sources when using `<script setup>`. Name components with `defineOptions({ name: 'UserList' })` for traceability in profiler.

## provide/inject for theme and auth

Replace prop drilling with typed injection keys:

```typescript
const AuthKey: InjectionKey<Ref<User | null>> = Symbol('auth')
provide(AuthKey, user)
const user = inject(AuthKey)!
```

Document injection keys in design system — magic string keys break silently on refactor.

## Pinia vs composables boundary

Pinia for cross-route shared server-backed state; composables for component-scoped logic. Duplicating fetch logic in composable and store creates two caches — pick one source of truth per resource.

## Practical follow-through (1)

Ship the smallest vertical slice first — one route, one widget, one index configuration — with rollback documented before expanding scope. Baseline the user-visible metric this work protects (latency, recall, conversion, task success rate) for seven days before change and seven days after in your largest market.

Compare canary p75 to control before full rollout. Exercise edge paths manually: refresh, back navigation, double-submit, offline mode, and keyboard-only flows. When assumptions change — traffic doubles, vendor upgrades, org restructure — revisit whether the original design still fits; quiet periods hide drift until the next incident.

## Practical follow-through (2)

Ship the smallest vertical slice first — one route, one widget, one index configuration — with rollback documented before expanding scope. Baseline the user-visible metric this work protects (latency, recall, conversion, task success rate) for seven days before change and seven days after in your largest market.

Compare canary p75 to control before full rollout. Exercise edge paths manually: refresh, back navigation, double-submit, offline mode, and keyboard-only flows. When assumptions change — traffic doubles, vendor upgrades, org restructure — revisit whether the original design still fits; quiet periods hide drift until the next incident.

## Resources

- [Vue 3 Composition API FAQ](https://vuejs.org/guide/extras/composition-api-faq.html)
- [Vue 3 script setup](https://vuejs.org/api/sfc-script-setup.html)
- [VueUse composable library](https://vueuse.org/)
- [Vue 3 provide/inject](https://vuejs.org/guide/components/provide-inject.html)
- [Migrating from Vue 2](https://vuejs.org/guide/migration/introduction.html)
