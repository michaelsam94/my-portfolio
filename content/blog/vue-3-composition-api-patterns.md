---
title: "Vue 3 Composition API Patterns"
slug: "vue-3-composition-api-patterns"
description: "Practical Vue 3 Composition API patterns: composables, ref vs reactive, provide/inject, script setup, and migrating from Options API without rewriting everything."
datePublished: "2026-03-07"
dateModified: "2026-03-07"
tags: ["Vue", "Web", "JavaScript", "Frontend"]
keywords: "Vue 3, Composition API, composables, script setup, ref, reactive, provide inject"
faq:
  - q: "When should I use the Composition API over the Options API in Vue 3?"
    a: "Use the Composition API for new components and any component with complex logic that benefits from grouping related state and effects together. It excels when multiple concerns interact — fetching data, handling form state, and managing subscriptions in the same component. The Options API remains fully supported and is fine for simple components with straightforward data, methods, and lifecycle hooks. You can mix both in the same project without penalty."
  - q: "What is a composable in Vue 3?"
    a: "A composable is a function that uses Vue's reactivity APIs (ref, reactive, computed, watch) to encapsulate and reuse stateful logic. Named after the Composition API, composables replace mixins as the primary code reuse mechanism. A useFetch composable wraps data fetching logic, a useMouse composable tracks cursor position — any logic that multiple components need can be extracted into a composable and called from script setup."
  - q: "Should I use ref or reactive for component state?"
    a: "Use ref as the default for all reactive state — primitives, objects, and arrays. ref works consistently with .value access in script and auto-unwraps in templates. Use reactive only when you have a grouped object that you never reassign wholesale and want to avoid .value syntax. A common mistake is destructuring reactive objects, which breaks reactivity; ref avoids this pitfall. In script setup, ref is the safer and more common choice."
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

## Common production mistakes

Teams get vue 3 composition api patterns wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of vue 3 composition api patterns fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Resources

- [Vue 3 Composition API FAQ](https://vuejs.org/guide/extras/composition-api-faq.html)
- [Vue 3 script setup](https://vuejs.org/api/sfc-script-setup.html)
- [VueUse composable library](https://vueuse.org/)
- [Vue 3 provide/inject](https://vuejs.org/guide/components/provide-inject.html)
- [Migrating from Vue 2](https://vuejs.org/guide/migration/introduction.html)
