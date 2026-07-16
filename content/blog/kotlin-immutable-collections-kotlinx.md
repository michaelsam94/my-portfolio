---
title: "kotlinx.collections.immutable in Compose"
slug: "kotlin-immutable-collections-kotlinx"
description: "Use kotlinx.collections.immutable for stable Compose lists and maps: persistent collections, @Immutable, recomposition savings, and state update patterns."
datePublished: "2025-12-11"
dateModified: "2025-12-11"
tags: ["Android", "Kotlin"]
keywords: "kotlinx.collections.immutable, Compose stability, persistent list, ImmutableList, recomposition, @Immutable"
faq:
  - q: "Why does Compose care if my list is mutable?"
    a: "Compose skips recomposition when parameters are considered stable and equal. MutableList is unstable—you can mutate it without changing reference, so Compose must recompose conservatively. ImmutableList guarantees structural sharing and stable reads, enabling skip when content is equal."
  - q: "Should I replace every List with ImmutableList?"
    a: "Use immutable collections in state hoisted to ViewModels and Composable parameters passed to expensive child trees. Local ephemeral lists inside a single Composable rarely matter. The cost is slightly more allocation on write—persistent data structures copy-on-write."
  - q: "How do I convert between List and ImmutableList?"
    a: "Use list.toImmutableList() and map.toPersistentMap(). For updates, use add, set, and remove on persistent collections—they return new instances sharing unchanged structure."
---

Profiler showed `ProductGrid` recomposing 400 cells when one item's favorite toggle changed. State held `List<Product>` as a mutable list copied with `.toMutableList()` on every tap—same list reference sometimes, new reference other times, stability annotations inconsistent. Switching UI state to `ImmutableList<Product>` and updating with persistent `add`/`set` cut recompositions to the toggled row and header.

Compose's compiler tracks **stability** of parameters. Standard `List` and `Map` interfaces are marked **unstable** because implementers might mutate. **kotlinx.collections.immutable** provides persistent immutable collections that compose well with `@Immutable` state classes.

## Setup

```kotlin
implementation("org.jetbrains.kotlinx:kotlinx-collections-immutable:0.3.8")
```

```kotlin
import kotlinx.collections.immutable.*
import kotlinx.collections.immutable.persistentListOf
```

## State in ViewModels

```kotlin
@Immutable
data class ProductUiState(
    val items: ImmutableList<Product>,
    val filter: String
)

class ProductViewModel : ViewModel() {
    private val _state = MutableStateFlow(
        ProductUiState(persistentListOf(), "")
    )
    val state = _state.asStateFlow()

    fun toggleFavorite(id: String) {
        _state.update { current ->
            current.copy(
                items = current.items.map { product ->
                    if (product.id == id) product.copy(favorite = !product.favorite)
                    else product
                }.toImmutableList()
            )
        }
    }
}
```

`map { }.toImmutableList()` creates new persistent list; unchanged elements are shared internally.

## Persistent updates

```kotlin
val list = persistentListOf(1, 2, 3)
val added = list.add(4)      // list unchanged
val removed = list.removeAt(1)
val updated = list.set(0, 99)

val map = persistentMapOf("a" to 1)
val map2 = map.put("b", 2)
```

Prefer builder for batch updates:

```kotlin
val built = persistentListOf<String>().builder().apply {
    addAll(source)
    add("extra")
}.build()
```

## Compose compiler reports

Enable stability configuration to verify:

```kotlin
// compose_compiler_config.conf
stableConfiguration = stability.conf
```

Compiler report flags unstable parameters:

```
ProductGrid(items: List<Product>) // unstable
ProductGrid(items: ImmutableList<Product>) // stable when Product is stable
```

Mark domain types `@Immutable` or `@Stable` when all properties are stable primitives or immutable collections.

## Lazy lists and keys

```kotlin
@Composable
fun ProductGrid(items: ImmutableList<Product>) {
    LazyVerticalGrid(columns = GridCells.Adaptive(160.dp)) {
        items(items, key = { it.id }) { product ->
            ProductCard(product)
        }
    }
}
```

Stable list + stable items lets Compose reuse measured slots efficiently during updates.

## Interop with regular collections

At API boundaries:

```kotlin
fun ApiResponse.toUiState(): ProductUiState =
    ProductUiState(
        items = products.toImmutableList(),
        filter = ""
    )
```

Do not pass network DTO mutable lists directly into Composables.

## Trade-offs

Persistent collections allocate on write. For tiny lists (under ~10 items), `List` inside `@Immutable` data class with copy-on-write discipline may suffice:

```kotlin
@Immutable
data class TinyState(val ids: List<String>) // ok if never mutate in place
```

For large lists or frequent diffs, immutable collections win measurably.

## Snapshot lists in remember

When derived UI state filters a list, wrap the result in `remember` with proper keys so you do not rebuild immutable lists every recomposition:

```kotlin
val visibleItems = remember(items, filter) {
    items.filter { it.matches(filter) }.toImmutableList()
}
```

Without `remember`, each frame allocates a new persistent vector—cheap per call, expensive at 60fps on large catalogs.

## Benchmark before optimizing

Compose Compiler reports flag unstable parameters; Macrobenchmark measures frame time. Immutable collections help when parent state updates frequently while child list content is unchanged. If parent rarely recomposes, mutable `List` inside `@Immutable` state may suffice—profile first.


## What to measure after rollout

Track error rates, tail latency, and resource utilization for two weeks after changes land—most regressions appear under real traffic mixes, not in staging smoke tests. Keep a rollback path documented: feature flags, Helm revision, or Git revert with known good digest. Review on-call pages tied to the topic quarterly; delete alerts that never fire and add thresholds that would have caught your last incident.

Run a short blameless postmortem if production surprised you, even for minor issues. The goal is updating this runbook section with one concrete lesson per quarter so the next engineer inherits context, not just configuration snippets.


## Documentation your team should maintain

Maintain a one-page runbook link from your main service README: prerequisites, owner rotation, last drill date, and known sharp edges. Link to vendor docs in the Resources section below but capture org-specific decisions (CIDR ranges, cluster names, approval gates) in internal docs that stay current. New hires should deploy a safe canary within a week using only that runbook—if they cannot, the doc is incomplete.


## Pre-production checklist

Before promoting to production, walk through this list with someone who was not the primary author—fresh eyes catch assumptions.

- **Staging parity**: The staging environment exercises the same code paths as production, including failure modes you expect to handle (timeouts, retries, partial outages).
- **Observability**: Dashboards and alerts exist for the metrics and log patterns discussed above; on-call knows where to look first.
- **Rollback**: You can revert to the previous known-good state in one documented step without improvising.
- **Access control**: Only the principals that need access have it; audit logs are enabled where the topic touches secrets or infrastructure APIs.
- **Load test**: You have evidence—not intuition—about behavior at expected peak plus headroom.

If any item is "we will do that later," treat it as a release blocker for tier-1 services.


## Common questions from reviewers

Reviewers and auditors often ask whether this approach scales with team growth and whether it fails safely. Answer explicitly in your design doc: what happens when dependencies are down, when credentials expire, and when traffic doubles overnight. Prefer defaults that deny or degrade gracefully over defaults that fail open. Document known limits (throughput ceilings, supported versions, regions) in the same place operators look during incidents—avoid scattering critical constraints across Slack threads.


## Resources

- [kotlinx.collections.immutable GitHub](https://github.com/Kotlin/kotlinx.collections.immutable) — API and performance notes
- [Compose stability documentation](https://developer.android.com/develop/ui/compose/performance/stability) — stable vs unstable types
- [Compose compiler metrics guide](https://developer.android.com/develop/ui/compose/performance/stability/fix#diagnose-issues) — finding unstable parameters
- [Persistent data structures overview](https://en.wikipedia.org/wiki/Persistent_data_structure) — structural sharing concept
