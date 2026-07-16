---
title: "GraphQL in Flutter with Ferry"
slug: "flutter-graphql-ferry-artemis"
description: "Type-safe GraphQL in Flutter with Ferry: codegen queries, cache policies, optimistic updates, and the setup that beats string-built GraphQL requests."
datePublished: "2024-11-21"
dateModified: "2024-11-21"
tags: ["Flutter", "Dart"]
keywords: "Flutter GraphQL, Ferry GraphQL, GraphQL codegen Flutter, gql_client, Flutter API GraphQL"
faq:
  - q: "What is Ferry in Flutter GraphQL?"
    a: "Ferry is a GraphQL client for Flutter and Dart built on gql and normalized caching. It pairs with ferry_generator to produce typed request and data classes from .graphql schema files. Requests execute via Ferry client with configurable cache policies, optimistic updates, and stream-based watch queries."
  - q: "How is Ferry different from graphql_flutter?"
    a: "graphql_flutter wraps the reference gql client with Flutter widgets like GraphQLProvider and Query. Ferry emphasizes codegen-first typed operations, built-in normalized cache similar to Apollo, and Request/Operation patterns. Teams wanting compile-time query safety often prefer Ferry; widget-centric quick setups may use graphql_flutter."
  - q: "How do I generate GraphQL types in Flutter?"
    a: "Place .graphql operation files in lib/graphql/, configure build.yaml for ferry_generator and graphql_codegen, run build_runner. Generated classes include typed variables, response data classes, and document serializers. Import generated files in Ferry Client request calls for fully typed results."
---

Our REST layer had twelve endpoints returning overlapping user data—classic over-fetching. GraphQL fixed the API; Ferry fixed the client. String-built queries with manual `Map<String, dynamic>` parsing broke every schema change. Ferry's codegen turns `.graphql` files into typed requests, and its normalized cache means updating a user's name in one screen reflects everywhere without manual cache invalidation spaghetti.

## Project setup

```yaml
dependencies:
  ferry: ^0.16.0
  gql_http_link: ^1.0.0

dev_dependencies:
  ferry_generator: ^0.12.0
  build_runner: ^2.4.12
```

**build.yaml:**

```yaml
targets:
  $default:
    builders:
      ferry_generator|graphql_builder:
        enabled: true
        options:
          schema: lib/graphql/schema.graphql
      ferry_generator|serializer_builder:
        enabled: true
        options:
          schema: lib/graphql/schema.graphql
```

**lib/graphql/get_user.graphql:**

```graphql
query GetUser($id: ID!) {
  user(id: $id) {
    id
    name
    email
    posts {
      id
      title
    }
  }
}
```

Generate:

```bash
dart run build_runner build --delete-conflicting-outputs
```

## Ferry client configuration

```dart
final link = Link.from([
  AuthLink(getToken: () async => 'Bearer ${await tokenStorage.read()}'),
  HttpLink('https://api.example.com/graphql'),
]);

final client = Client(
  link: link,
  cache: Cache(
    typePolicies: {
      'User': TypePolicy(
        keyFields: {'id'},
      ),
    },
  ),
);
```

Register as singleton in DI; dispose on logout with `client.cache.clear()`.

## Executing queries

```dart
final request = GGetUserReq((b) => b..vars.id = '42');

final response = await client.request(request).first;

if (response.hasErrors) {
  throw GraphQLException(response.graphqlErrors);
}

final user = response.data?.user;
```

**Watch for reactive UI:**

```dart
StreamBuilder<GGetUserData?>(
  stream: client.request(GGetUserReq((b) => b..vars.id = userId))
      .map((r) => r.data),
  builder: (_, snapshot) {
    final user = snapshot.data?.user;
    if (user == null) return LoadingView();
    return ProfileView(user: user);
  },
)
```

Cache emits new data when related entities update.

## Mutations and optimistic updates

**lib/graphql/update_user.graphql:**

```graphql
mutation UpdateUser($id: ID!, $name: String!) {
  updateUser(id: $id, name: $name) {
    id
    name
  }
}
```

```dart
final request = GUpdateUserReq(
  (b) => b
    ..vars.id = '42'
    ..vars.name = 'New Name'
    ..optimisticResponse.updateUser
        .replace(GUpdateUserData_updateUser((b) => b
          ..id = '42'
          ..name = 'New Name')),
);

await client.request(request).first;
```

UI updates immediately; rolls back on server error.

## Cache policies

```dart
final request = GGetUserReq(
  (b) => b
    ..vars.id = userId
    ..fetchPolicy = FetchPolicy.CacheAndNetwork,
);
```

| Policy | Behavior |
|--------|----------|
| CacheFirst | Return cache, fetch if miss |
| NetworkOnly | Skip cache |
| CacheAndNetwork | Return cache, then network update |
| CacheOnly | Offline read |

Use `NetworkOnly` for auth-sensitive one-time operations; `CacheAndNetwork` for profile screens.

## Error handling

```dart
extension ResponseX<T> on OperationResponse<T, T> {
  Either<GraphQLFailure, T> toEither() {
    if (hasErrors) {
      return Left(GraphQLFailure(graphqlErrors!.first.message));
    }
    if (data == null) {
      return const Left(GraphQLFailure('No data'));
    }
    return Right(data as T);
  }
}
```

Handle network errors via link exceptions and `DioLink` if using Dio transport.

### Ferry vs Artemis

**Artemis** is another codegen GraphQL client generating client classes per query. Less active maintenance recently; Ferry has stronger cache story. **graphql_flutter** suits widget-heavy apps with minimal codegen. Evaluate based on team preference for code generation vs runtime query strings.

For new Flutter projects in 2024–2025, Ferry + codegen is my default recommendation for typed GraphQL at scale.

### Testing

Mock the link layer:

```dart
final mockLink = MockLink();
when(() => mockLink.request(any())).thenAnswer(
  (_) => Stream.value(
    Response(
      data: {'user': {'id': '1', 'name': 'Test'}},
      response: http.Response('', 200),
    ),
  ),
);

final client = Client(link: mockLink, cache: Cache());
```

Widget tests pump with Provider exposing test client.

### Persisted queries and GET requests

For CDN cacheability, configure APQ (automatic persisted queries) on server and link layer—reduces payload size and enables GET caching for read-heavy operations. Ferry link chain can include DedupeLink preventing duplicate inflight requests when multiple widgets watch same query on mount.

Offline-first GraphQL apps cache with Ferry normalized store—define typePolicies merge functions for paginated list fields appending vs replacing edges. Test offline mode by toggling airplane mode in integration tests verifying cached queries render without network.

Production teams should treat this guidance as living documentation: revisit assumptions after major platform upgrades, measure outcomes with real metrics rather than checklist compliance, and pair written standards with automated checks in CI. The patterns here reflect what held up in shipped apps—not theoretical perfection. Adapt thresholds, timeouts, and tooling to your stack, but keep the underlying principles: explicit configuration, testable behavior, and failure modes users can understand.

When onboarding new engineers, walk through one end-to-end example in a debug build before asking them to extend the pattern. Most failures I have seen came from skipped platform setup steps—manifest entries, API keys, code generation, or permission prompts—not from misunderstanding the Dart layer. Keep a troubleshooting section in your team wiki linking official docs and the exact commands that worked for your last upgrade.

Schedule a quarterly review of this implementation against current SDK release notes—Flutter and cloud providers ship breaking changes on six-month cadences, and assumptions that held last year may need adjustment. Capture before-and-after metrics when you change configuration so regressions are obvious in retrospect rather than debated from memory.

Version-pin dependencies mentioned here in your pubspec.lock or infrastructure modules, and note the Flutter/Dart SDK constraint your team validated. Upgrading without re-running the verification steps in this article is the most common source of regressions. If something fails after an upgrade, compare release notes first, then your git history for the last known-good configuration.

Pair this setup with logging sufficient to diagnose field failures: request identifiers, cache keys, and user-visible error codes. Support teams need traceability from a screenshot to the underlying state without redeploying debug builds.

Normalize GraphQL cache keys by typename and ID — default cache policies duplicate entities across queries and inflate memory.

## Resources

- [Ferry documentation](https://ferrygraphql.com/)
- [Ferry package](https://pub.dev/packages/ferry)
- [ferry_generator](https://pub.dev/packages/ferry_generator)
- [GraphQL Flutter (alternative)](https://pub.dev/packages/graphql_flutter)
- [gql_http_link](https://pub.dev/packages/gql_http_link)
