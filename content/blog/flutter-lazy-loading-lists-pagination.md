---
title: "Lazy Loading and Pagination"
slug: "flutter-lazy-loading-lists-pagination"
description: "Implement infinite scroll and pagination in Flutter: scroll listeners, cursor vs offset paging, PagingController, and avoiding duplicate fetches."
datePublished: "2024-12-21"
dateModified: "2024-12-21"
tags: ["Flutter", "Dart"]
keywords: "Flutter pagination, infinite scroll Flutter, lazy loading list, PagingController, cursor pagination Flutter"
faq:
  - q: "How do I implement infinite scroll in Flutter?"
    a: "Attach a ScrollController listener detecting when scroll position reaches maxScrollExtent minus threshold, then fetch the next page and append to your list state. Use ListView.builder for lazy item building—only visible items render. Debounce fetch calls and guard with isLoading flag to prevent duplicate requests."
  - q: "What is the difference between offset and cursor pagination?"
    a: "Offset pagination requests page by number or skip/limit—simple but inconsistent if data changes between requests (duplicates or skips). Cursor pagination uses an opaque token from the previous response (last item ID or createdAt) pointing to the next set—stable for real-time feeds and large datasets."
  - q: "Should I use the infinite_scroll_pagination package?"
    a: "infinite_scroll_pagination provides PagingController managing page keys, error/retry states, and append logic—reduces boilerplate for standard list pagination. Custom ScrollController implementation suits atypical UX like bidirectional chat history or grid pagination with variable row heights."
---

The feed loaded 500 posts on first paint—8 seconds, 200 MB RAM, angry users. Pagination seems trivial until you hit duplicate pages from concurrent fetches, missing loading indicators, and offset drift when new items insert at the top. Lazy loading with `ListView.builder` plus disciplined page state fixes the performance side; cursor-based API paging fixes the consistency side.

## ListView.builder foundation

Never use `ListView(children: items.map(...))` for long lists:

```dart
ListView.builder(
  controller: _scrollController,
  itemCount: _items.length + (_hasMore ? 1 : 0),
  itemBuilder: (context, index) {
    if (index >= _items.length) {
      return const Center(child: CircularProgressIndicator());
    }
    return ItemTile(item: _items[index]);
  },
)
```

Extra item at end shows loading indicator while fetching next page.

## ScrollController pagination

```dart
class _FeedState extends State<Feed> {
  final _scrollController = ScrollController();
  final List<Post> _posts = [];
  String? _cursor;
  bool _isLoading = false;
  bool _hasMore = true;

  @override
  void initState() {
    super.initState();
    _scrollController.addListener(_onScroll);
    _fetchNextPage();
  }

  void _onScroll() {
    if (!_hasMore || _isLoading) return;
    final threshold = 200.0;
    if (_scrollController.position.pixels >=
        _scrollController.position.maxScrollExtent - threshold) {
      _fetchNextPage();
    }
  }

  Future<void> _fetchNextPage() async {
    setState(() => _isLoading = true);
    try {
      final page = await _api.fetchPosts(cursor: _cursor, limit: 20);
      setState(() {
        _posts.addAll(page.items);
        _cursor = page.nextCursor;
        _hasMore = page.hasMore;
      });
    } finally {
      setState(() => _isLoading = false);
    }
  }

  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }
}
```

Threshold triggers fetch before user hits absolute bottom—perceived infinite scroll.

## Cursor vs offset API

**Offset (simple API):**

```dart
Future<Page> fetch({required int page, int limit = 20}) async {
  final response = await dio.get('/posts', queryParameters: {
    'page': page,
    'limit': limit,
  });
  return Page.fromJson(response.data);
}
```

**Cursor (stable feeds):**

```dart
Future<CursorPage> fetch({String? cursor, int limit = 20}) async {
  final response = await dio.get('/posts', queryParameters: {
    if (cursor != null) 'cursor': cursor,
    'limit': limit,
  });
  return CursorPage.fromJson(response.data);
}
```

Prefer cursor when items can be inserted/deleted during browsing.

## infinite_scroll_pagination package

```yaml
dependencies:
  infinite_scroll_pagination: ^4.0.0
```

```dart
class _FeedState extends State<Feed> {
  static const _pageSize = 20;
  final PagingController<String?, Post> _pagingController =
      PagingController(firstPageKey: null);

  @override
  void initState() {
    super.initState();
    _pagingController.addPageRequestListener(_fetchPage);
  }

  Future<void> _fetchPage(String? cursor) async {
    try {
      final page = await _api.fetchPosts(cursor: cursor, limit: _pageSize);
      final isLastPage = !page.hasMore;
      if (isLastPage) {
        _pagingController.appendLastPage(page.items);
      } else {
        _pagingController.appendPage(page.items, page.nextCursor);
      }
    } catch (e) {
      _pagingController.error = e;
    }
  }

  @override
  Widget build(BuildContext context) {
    return PagedListView<String?, Post>(
      pagingController: _pagingController,
      builderDelegate: PagedChildBuilderDelegate<Post>(
        itemBuilder: (_, post, __) => PostTile(post: post),
        firstPageErrorIndicatorBuilder: (_) => ErrorRetry(
          onRetry: () => _pagingController.refresh(),
        ),
      ),
    );
  }

  @override
  void dispose() {
    _pagingController.dispose();
    super.dispose();
  }
}
```

Handles error, empty, and loading states declaratively.

## Pull-to-refresh with pagination

Reset cursor and clear list:

```dart
Future<void> _onRefresh() async {
  _cursor = null;
  _hasMore = true;
  _posts.clear();
  await _fetchNextPage();
}

RefreshIndicator(
  onRefresh: _onRefresh,
  child: ListView.builder(...),
)
```

With PagingController: `_pagingController.refresh()`.

## Riverpod / Bloc integration

**Cubit state:**

```dart
class FeedState {
  final List<Post> posts;
  final String? cursor;
  final bool isLoading;
  final bool hasMore;
  final Object? error;
}

class FeedCubit extends Cubit<FeedState> {
  Future<void> loadMore() async {
    if (state.isLoading || !state.hasMore) return;
    emit(state.copyWith(isLoading: true));
    // fetch and emit appended posts
  }
}
```

Widget listens; scroll listener calls `context.read<FeedCubit>().loadMore()`.

### Grid pagination

`GridView.builder` with same scroll listener pattern. Calculate `maxScrollExtent` identically. For staggered grids, `flutter_staggered_grid_view` + manual pagination works; ensure item heights stabilize or scroll extent jumps.

### Pitfalls

1. **Duplicate fetches** — guard with `_isLoading`; debounce scroll events.
2. **setState after dispose** — check `mounted` before setState after async.
3. **Refresh during load** — cancel in-flight request or ignore stale responses with request token.
4. **Empty first page** — show empty state, not infinite spinner.
5. **Memory growth** — for very long sessions, consider windowing (remove off-screen pages) rarely needed unless 10k+ items.

Pagination done right feels invisible—content appears as user scrolls, never stutters, never duplicates.

### Bidirectional pagination for chat

Message lists load older pages when scrolling up—reverse ListView with scroll controller checking pixels == 0:

```dart
ListView.builder(
  reverse: true,
  controller: _scrollController,
  itemBuilder: ...
)
```

Maintain scroll position when prepending items using ScrollController.jumpTo adjusted for height delta—packages like scrollable_positioned_list simplify this math.

Search-as-you-type pagination resets cursor on each query change—debounce search input before fetch to avoid orphan in-flight requests appending wrong results. CancelToken or request generation counter discards stale responses when query string changed during network round trip.

Production teams should treat this guidance as living documentation: revisit assumptions after major platform upgrades, measure outcomes with real metrics rather than checklist compliance, and pair written standards with automated checks in CI. The patterns here reflect what held up in shipped apps—not theoretical perfection. Adapt thresholds, timeouts, and tooling to your stack, but keep the underlying principles: explicit configuration, testable behavior, and failure modes users can understand.

When onboarding new engineers, walk through one end-to-end example in a debug build before asking them to extend the pattern. Most failures I have seen came from skipped platform setup steps—manifest entries, API keys, code generation, or permission prompts—not from misunderstanding the Dart layer. Keep a troubleshooting section in your team wiki linking official docs and the exact commands that worked for your last upgrade.

Schedule a quarterly review of this implementation against current SDK release notes—Flutter and cloud providers ship breaking changes on six-month cadences, and assumptions that held last year may need adjustment. Capture before-and-after metrics when you change configuration so regressions are obvious in retrospect rather than debated from memory.

## Resources

- [ListView.builder API](https://api.flutter.dev/flutter/widgets/ListView/ListView.builder.html)
- [ScrollController](https://api.flutter.dev/flutter/widgets/ScrollController-class.html)
- [infinite_scroll_pagination package](https://pub.dev/packages/infinite_scroll_pagination)
- [Flutter lazy loading cookbook patterns](https://docs.flutter.dev/cookbook/lists/infinite-list)
- [API pagination best practices](https://www.martinfowler.com/eaaCatalog/remoteFacade.html)
