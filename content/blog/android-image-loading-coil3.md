---
title: "Image Loading with Coil 3: Compose, KMP, and the Cache"
slug: "android-image-loading-coil3"
description: "Image loading with Coil 3 on Android and Compose: the multiplatform rewrite, AsyncImage, memory and disk cache tuning, crossfade, and avoiding jank in lazy lists."
datePublished: "2024-08-22"
dateModified: "2024-08-22"
tags: ["Android", "Jetpack Compose", "Kotlin"]
keywords: "Coil 3, Coil Compose, AsyncImage, image loading Android, ImageLoader cache, Kotlin Multiplatform images"
faq:
  - q: "What changed between Coil 2 and Coil 3?"
    a: "Coil 3 is a Kotlin Multiplatform rewrite: the core moved off Android-only APIs and onto Okio and kotlinx primitives so it can run on Android, iOS, JVM, and JS/Wasm. The networking layer became pluggable, so you add a separate artifact for OkHttp or Ktor rather than getting OkHttp baked in. Package names moved under coil3, and image requests now use a platform-neutral model, though the Compose AsyncImage API stays familiar."
  - q: "How do I configure the memory and disk cache in Coil?"
    a: "Build a single app-wide ImageLoader and set its MemoryCache and DiskCache explicitly, sizing the memory cache as a fraction of available heap and the disk cache with a fixed byte budget. Provide that loader via a singleton or SingletonImageLoader.Factory so every AsyncImage shares one cache instead of creating ad-hoc loaders. Sharing one loader is what makes scrolling back up a list instant rather than re-fetching."
  - q: "Why do images flicker or reload when scrolling a lazy list?"
    a: "Usually because each item creates its own ImageLoader, the memory cache is too small for the working set, or the composable's request key changes every recomposition. Use one shared ImageLoader, size the memory cache to hold a screen or two of images, and make sure the model passed to AsyncImage is stable. A stable key plus a shared cache eliminates the reload-on-scroll flicker."
---

Coil 3 is the version I now reach for on any Compose project, and the headline is that it's no longer an Android-only library. It's a Kotlin Multiplatform rewrite: the core sits on Okio and kotlinx primitives instead of `android.graphics` and OkHttp directly, which means the same image-loading code runs on Android, iOS, desktop JVM, and Wasm. If you're building a shared Compose Multiplatform UI, that alone is the reason to upgrade. If you're Android-only, you still benefit from a cleaner request model and a pluggable network stack — but you also have to make a couple of choices Coil 2 made for you.

I'll cover the migration surprises, the Compose API, and the cache tuning that actually determines whether your lists scroll smoothly.

## What moved in the rewrite

The changes that bit me during migration, in order of annoyance:

- **Package rename** to `coil3.*`. Mechanical, but touches every import.
- **Networking is now opt-in.** Coil 3 core has no HTTP client. You add `coil-network-okhttp` (or the Ktor variant) as a separate dependency, otherwise `https://` URLs fail with a "no support" error that confuses everyone the first time.
- **Platform-neutral model.** `Bitmap` gave way to a multiplatform `Image` type; if you were poking at bitmaps directly you'll adjust.
- **`SingletonImageLoader.Factory`** replaces the old `ImageLoaderFactory` on `Application` for providing the app-wide loader.

None are hard, but the "why can't it load a URL" moment costs everyone twenty minutes, so: add the network artifact.

## The Compose API you'll use 95% of the time

`AsyncImage` is the same ergonomic entry point:

```kotlin
AsyncImage(
    model = ImageRequest.Builder(LocalContext.current)
        .data(user.avatarUrl)
        .crossfade(true)
        .build(),
    contentDescription = user.name,   // real description, not null
    contentScale = ContentScale.Crop,
    placeholder = painterResource(R.drawable.avatar_placeholder),
    error = painterResource(R.drawable.avatar_error),
    modifier = Modifier.size(48.dp).clip(CircleShape),
)
```

A few opinions baked in there. Always set a real `contentDescription` for anything meaningful — this is the same discipline as [testing accessibility with TalkBack](https://blog.michaelsam94.com/android-accessibility-talkback-testing/); a decorative image gets `null`, a user avatar gets the name. Always provide `error` and `placeholder` states, because network images fail and an empty box looks broken. And `crossfade(true)` softens the pop-in, but keep it short (the default ~100ms) or fast scrolling looks laggy.

For custom loading UI, `SubcomposeAsyncImage` lets you render your own composable per state, at the cost of an extra subcomposition — don't reach for it in a hot list unless you need it.

## One ImageLoader, shared everywhere

The single biggest performance lever is using **one** `ImageLoader` for the whole app, with an explicitly sized cache. Ad-hoc loaders per screen fragment the cache and re-download everything.

```kotlin
class App : Application(), SingletonImageLoader.Factory {
    override fun newImageLoader(context: PlatformContext): ImageLoader =
        ImageLoader.Builder(context)
            .memoryCache {
                MemoryCache.Builder()
                    .maxSizePercent(context, 0.25) // 25% of available heap
                    .build()
            }
            .diskCache {
                DiskCache.Builder()
                    .directory(context.cacheDir.resolve("image_cache"))
                    .maxSizeBytes(256L * 1024 * 1024) // 256 MB
                    .build()
            }
            .crossfade(true)
            .build()
}
```

The memory cache holds decoded bitmaps — the fast path when you scroll back up a list. Size it to hold a screen or two of images; too small and you get the classic reload-on-scroll flicker. The disk cache holds the encoded bytes, avoiding re-download across app launches. These are two separate caches with separate budgets, and understanding that split is what lets you diagnose "why does scrolling up re-decode" (memory too small) versus "why does it re-download after restart" (disk cache off or tiny).

## Killing jank in lazy lists

Images are the usual suspect when a `LazyColumn` stutters. My checklist:

1. **Share the loader** (above) so cache hits are actually hits.
2. **Size the request.** By default Coil sizes to the target composable, which is good — but if you hand it a giant image into a 48dp avatar, you're decoding far more than you show. Let Coil measure the target; avoid forcing `Size.ORIGINAL`.
3. **Stable models and keys.** If the `model` you pass changes identity every recomposition (e.g. building a new object each time), Coil may re-request. Keep the URL/model stable, and give `items(key = ...)` a stable key — the same [recomposition hygiene](https://blog.michaelsam94.com/jetpack-compose-lessons-10-years-android/) that helps everything else.
4. **Don't over-crossfade.** Long crossfades during a fling read as lag.

With those four, a list of remote thumbnails scrolls at a locked frame rate because most items resolve from the memory cache synchronously.

## Preloading and precise cache control

For a detail screen you're about to navigate to, preloading avoids a visible load:

```kotlin
val request = ImageRequest.Builder(context)
    .data(nextImageUrl)
    .build()
imageLoader.enqueue(request)   // warms memory + disk cache
```

And when a user updates their avatar, you often need to *evict* the stale entry so the new one shows immediately rather than serving the cached old image — reach into `imageLoader.memoryCache?.remove(key)` and use a cache-busting key or `memoryCachePolicy`/`diskCachePolicy` on that specific request.

## Where I've landed

Coil 3's multiplatform core is the right direction, and for Android it's a clean, fast default. Add the OkHttp network artifact, provide exactly one `ImageLoader` with a memory cache around 25% of heap and a disk cache in the hundreds of MB, always set `contentDescription`, placeholder, and error, and keep your list models stable. That configuration is the difference between buttery scrolling and a feed that reloads every thumbnail every time you flick past it.

## Resources

- [Coil documentation](https://coil-kt.github.io/coil/)
- [Coil 3 upgrade guide](https://coil-kt.github.io/coil/upgrading_to_coil3/)
- [Coil Compose (AsyncImage)](https://coil-kt.github.io/coil/compose/)
- [Coil image loaders and caching](https://coil-kt.github.io/coil/image_loaders/)
- [Android: loading images efficiently](https://developer.android.com/develop/ui/compose/graphics/images/loading)
