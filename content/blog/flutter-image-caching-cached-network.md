---
title: "Image Caching Strategies"
slug: "flutter-image-caching-cached-network"
description: "Cache network images efficiently in Flutter: cached_network_image, cache sizing, placeholders, memory vs disk, and avoiding OOM from unbounded image lists."
datePublished: "2024-11-27"
dateModified: "2024-11-27"
tags: ["Flutter", "Dart"]
keywords: "Flutter image caching, cached_network_image, network image Flutter, image cache OOM, flutter cache manager"
faq:
  - q: "How does Flutter cache network images?"
    a: "Image.network uses Flutter's ImageCache in memory only—no disk persistence by default. cached_network_image wraps flutter_cache_manager to store downloaded files on disk and serve from memory cache on subsequent loads. Configure max cache size and stale period to control storage growth."
  - q: "What is the best package for caching images in Flutter?"
    a: "cached_network_image is the standard choice for most apps, built on flutter_cache_manager. It supports placeholders, error widgets, fade animations, and cache key overrides. For advanced control—custom download headers, cache eviction policies—use flutter_cache_manager directly with Image.file."
  - q: "How do I prevent image cache memory issues?"
    a: "Limit ImageCache size via PaintingBinding.instance.imageCache.maximumSizeBytes in main(). Use memCacheWidth and memCacheHeight on CachedNetworkImage to decode smaller bitmaps for list thumbnails. Clear cache on memory pressure callbacks. Never load full-resolution images in RecyclerView-style lists."
---

A product grid with 200 full-resolution network images ate 400 MB RAM and OOM-killed the app on a mid-range Android phone. `Image.network` fetched and decoded every pixel because nobody set `cacheWidth` or disk caching. Image caching in Flutter is two problems: **disk persistence** (don't re-download) and **memory decode size** (don't decode 4000px images into 80px thumbnails). `cached_network_image` solves the first; explicit mem cache dimensions solve the second.

## cached_network_image setup

```yaml
dependencies:
  cached_network_image: ^3.4.1
```

Basic usage:

```dart
CachedNetworkImage(
  imageUrl: 'https://cdn.example.com/products/42.jpg',
  placeholder: (_, __) => const CircularProgressIndicator(),
  errorWidget: (_, __, ___) => const Icon(Icons.broken_image),
  fit: BoxFit.cover,
)
```

Disk cache handled automatically via `flutter_cache_manager`. Second load reads from disk; hot loads hit memory.

## Memory cache sizing for lists

Critical for scrollable lists—decode at display size, not source size:

```dart
CachedNetworkImage(
  imageUrl: product.thumbnailUrl,
  memCacheWidth: 200,
  memCacheHeight: 200,
  maxWidthDiskCache: 400,
  maxHeightDiskCache: 400,
  fit: BoxFit.cover,
)
```

Flutter decodes bitmap at approximately `memCacheWidth` × `memCacheHeight`, saving 10–50x memory vs full image.

Calculate from display size × device pixel ratio:

```dart
int cacheWidth(BuildContext context, double displayWidth) {
  return (displayWidth * MediaQuery.devicePixelRatioOf(context)).round();
}
```

## Global ImageCache limits

```dart
void main() {
  WidgetsFlutterBinding.ensureInitialized();
  PaintingBinding.instance.imageCache.maximumSize = 200; // image count
  PaintingBinding.instance.imageCache.maximumSizeBytes = 100 << 20; // 100 MB
  runApp(MyApp());
}
```

Tune per app—image-heavy apps need higher limits; text apps can stay low.

Clear on memory warning (Android):

```dart
@override
void didHaveMemoryPressure() {
  PaintingBinding.instance.imageCache.clear();
  PaintingBinding.instance.imageCache.clearLiveImages();
}
```

## Custom cache manager

Separate caches for avatars vs product catalog:

```dart
final avatarCacheManager = CacheManager(
  Config(
    'avatarCache',
    stalePeriod: const Duration(days: 7),
    maxNrOfCacheObjects: 100,
  ),
);

CachedNetworkImage(
  imageUrl: user.avatarUrl,
  cacheManager: avatarCacheManager,
  cacheKey: 'avatar_${user.id}',
)
```

`cacheKey` overrides URL-based key—useful when URL stays same but image content changes (append version query param or custom key).

## Placeholders and fade

```dart
CachedNetworkImage(
  imageUrl: url,
  fadeInDuration: const Duration(milliseconds: 200),
  placeholder: (_, __) => Container(
    color: Colors.grey.shade200,
    child: const Center(child: Icon(Icons.image, color: Colors.grey)),
  ),
  errorWidget: (_, __, error) {
    debugPrint('Image load failed: $error');
    return const Icon(Icons.error_outline);
  },
)
```

**Progressive loading** with blur hash or low-res thumbnail URL in placeholder while full res loads—pattern:

```dart
Stack(
  fit: StackFit.expand,
  children: [
    CachedNetworkImage(imageUrl: product.blurUrl, fit: BoxFit.cover),
    CachedNetworkImage(imageUrl: product.fullUrl, fit: BoxFit.cover),
  ],
)
```

## Auth headers for protected images

```dart
CachedNetworkImage(
  imageUrl: 'https://api.example.com/private/image/42',
  httpHeaders: {'Authorization': 'Bearer $token'},
)
```

Headers participate in cache key—different tokens create separate cache entries.

### Preloading and precaching

Scroll performance—preload next page images:

```dart
Future<void> preloadImages(List<String> urls) async {
  for (final url in urls) {
    await precacheImage(
      CachedNetworkImageProvider(url),
      context,
    );
  }
}
```

Call when pagination fetches new data, before user scrolls there.

### Image.network when caching isn't needed

One-time display, unique URLs, or extremely large images you don't want on disk:

```dart
Image.network(
  url,
  cacheWidth: 300,
  loadingBuilder: (_, child, progress) {
    if (progress == null) return child;
    return CircularProgressIndicator(
      value: progress.expectedTotalBytes != null
          ? progress.cumulativeBytesLoaded / progress.expectedTotalBytes!
          : null,
    );
  },
)
```

Still set `cacheWidth` for memory control.

### Eviction and cache busting

Force refresh after CDN update:

```dart
await DefaultCacheManager().removeFile(url);
// or append ?v=2 to URL
```

Expose "Clear cache" in settings for support debugging:

```dart
await DefaultCacheManager().emptyCache();
PaintingBinding.instance.imageCache.clear();
```

### ListView cache extent tuning

```dart
ListView.builder(
  cacheExtent: 500,
  itemBuilder: ...
)
```

Prefetch images slightly off-screen for smoother fast scroll—balance memory. For grid layouts, staggered loading with lower memCacheWidth on off-screen rows via VisibilityDetector reduces peak memory during flings.

SVG network images need flutter_svg, not CachedNetworkImage—raster caching pipeline doesn't apply. Lottie animations similarly separate from bitmap cache strategy. Document asset type per screen in design specs to pick correct loading widget upfront.

Production teams should treat this guidance as living documentation: revisit assumptions after major platform upgrades, measure outcomes with real metrics rather than checklist compliance, and pair written standards with automated checks in CI. The patterns here reflect what held up in shipped apps—not theoretical perfection. Adapt thresholds, timeouts, and tooling to your stack, but keep the underlying principles: explicit configuration, testable behavior, and failure modes users can understand.

When onboarding new engineers, walk through one end-to-end example in a debug build before asking them to extend the pattern. Most failures I have seen came from skipped platform setup steps—manifest entries, API keys, code generation, or permission prompts—not from misunderstanding the Dart layer. Keep a troubleshooting section in your team wiki linking official docs and the exact commands that worked for your last upgrade.

Schedule a quarterly review of this implementation against current SDK release notes—Flutter and cloud providers ship breaking changes on six-month cadences, and assumptions that held last year may need adjustment. Capture before-and-after metrics when you change configuration so regressions are obvious in retrospect rather than debated from memory.

Version-pin dependencies mentioned here in your pubspec.lock or infrastructure modules, and note the Flutter/Dart SDK constraint your team validated. Upgrading without re-running the verification steps in this article is the most common source of regressions. If something fails after an upgrade, compare release notes first, then your git history for the last known-good configuration.

Set max cache size based on analytics storage budget — image caches without limits consume user storage and trigger uninstalls.

## Resources

- [cached_network_image package](https://pub.dev/packages/cached_network_image)
- [flutter_cache_manager](https://pub.dev/packages/flutter_cache_manager)
- [ImageCache API](https://api.flutter.dev/flutter/painting/ImageCache-class.html)
- [CachedNetworkImage documentation](https://pub.dev/documentation/cached_network_image/latest/)
- [Flutter assets and images guide](https://docs.flutter.dev/ui/assets/assets-and-images)
