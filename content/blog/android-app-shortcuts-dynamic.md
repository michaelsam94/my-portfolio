---
title: "Dynamic and Pinned App Shortcuts"
slug: "android-app-shortcuts-dynamic"
description: "Implement dynamic and pinned app shortcuts on Android: ShortcutManager, adaptive icons, deep link integration, and keeping shortcuts fresh without annoying users."
datePublished: "2026-07-10"
dateModified: "2026-07-10"
tags: ["Android", "UX", "Deep Links", "App Shortcuts"]
keywords: "Android app shortcuts, dynamic shortcuts, pinned shortcuts, ShortcutManager, Android long press menu"
faq:
  - q: "What are the types of Android app shortcuts?"
    a: "Static shortcuts are declared in XML and always available. Dynamic shortcuts are created at runtime via ShortcutManager and can be updated or removed. Pinned shortcuts are added by the user to the home screen launcher and persist until the user removes them. You can have up to 5 dynamic + static shortcuts shown in the long-press menu."
  - q: "How do dynamic shortcuts differ from static shortcuts?"
    a: "Static shortcuts are defined in shortcuts.xml and ship with the app. Dynamic shortcuts are pushed at runtime based on user behavior — recent contacts, last opened document, favorite items. Dynamic shortcuts should reflect current app state and be refreshed when relevant data changes."
  - q: "Can pinned shortcuts be updated after the user pins them?"
    a: "Yes, but carefully. Use ShortcutManager.updateShortcuts() or disableShortcuts() for pinned shortcuts the user created. Changing the intent target of a pinned shortcut without user expectation is confusing — update labels and icons when the underlying entity changes, but don't redirect a pinned 'Message Alice' shortcut to a different person."
---

App shortcuts — the menu that appears when users long-press your icon — are the fastest path into your app's most common actions, and most apps waste them on static "Settings" and "Help" entries nobody taps. Dynamic shortcuts that surface the user's last three conversations, most recent project, or pinned favorite turn a generic launcher entry into a personalized entry point. I've seen shortcut-driven opens account for 8–12% of daily sessions in messaging and productivity apps that implement them well. The API is straightforward; the design discipline — what to show, when to refresh, when to remove — is what separates useful from cluttered.

## Static, dynamic, and pinned

| Type | Defined | Max shown | Updated | User action |
|------|---------|-----------|---------|-------------|
| Static | XML manifest | 4 | App update | None |
| Dynamic | Runtime code | 4 (shared cap) | Anytime | None |
| Pinned | User long-press → pin | Unlimited pinned | Via updateShortcuts | User pins |

Total shortcuts in the long-press menu: max 4 static + dynamic combined (API limit is 5 including manifest, but launcher UI varies). Pinned shortcuts appear on the home screen separately.

## Static shortcuts in XML

Define infrequent, universal actions:

```xml
<!-- res/xml/shortcuts.xml -->
<shortcuts xmlns:android="http://schemas.android.com/apk/res/android">
    <shortcut
        android:shortcutId="new_note"
        android:enabled="true"
        android:icon="@drawable/ic_shortcut_new"
        android:shortcutShortLabel="@string/shortcut_new_note"
        android:shortcutLongLabel="@string/shortcut_new_note_long">
        <intent
            android:action="android.intent.action.VIEW"
            android:targetPackage="com.example.app"
            android:targetClass="com.example.app.MainActivity"
            android:data="myapp://notes/new" />
    </shortcut>
</shortcuts>
```

Reference in your launcher activity:

```xml
<meta-data
    android:name="android.app.shortcuts"
    android:resource="@xml/shortcuts" />
```

Static shortcuts are fine for "New item" or "Scan QR" — actions that don't depend on user state.

## Dynamic shortcuts at runtime

Push shortcuts based on recent user activity:

```kotlin
fun updateRecentShortcuts(context: Context, recentItems: List<RecentItem>) {
    val shortcuts = recentItems.take(4).map { item ->
        ShortcutInfo.Builder(context, "recent_${item.id}")
            .setShortLabel(item.title)
            .setLongLabel("Open ${item.title}")
            .setIcon(Icon.createWithAdaptiveBitmap(item.iconBitmap))
            .setIntent(
                Intent(context, MainActivity::class.java)
                    .setAction(Intent.ACTION_VIEW)
                    .setData("myapp://items/${item.id}".toUri())
                    .setFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP)
            )
            .setRank(recentItems.indexOf(item))
            .build()
    }

    ShortcutManagerCompat.setDynamicShortcuts(context, shortcuts)
}
```

Call this when recent items change — after the user opens/closes items, on app foreground, or via a WorkManager periodic refresh for time-sensitive data.

## Ranking and the cap

You get 4 dynamic shortcut slots (shared with static in the menu). Rank matters — lower rank = higher position:

```kotlin
.setRank(0)  // top of the list
```

When you have more candidates than slots, pick by recency + frequency, not just last opened. A item opened once yesterday shouldn't displace one opened ten times this week.

Remove stale shortcuts explicitly:

```kotlin
ShortcutManagerCompat.removeDynamicShortcuts(context, listOf("recent_old_id"))
// Or replace the entire set:
ShortcutManagerCompat.setDynamicShortcuts(context, newShortcuts)
```

Don't let shortcuts accumulate for deleted entities. A shortcut to a deleted conversation erodes trust.

## Pinned shortcuts

Users can drag a shortcut from the long-press menu to their home screen. These persist across app updates and even app data clears (the pin survives, but the intent may break if IDs changed).

Report usage for analytics:

```kotlin
ShortcutManagerCompat.reportShortcutUsed(context, "recent_${item.id}")
```

This helps the system prioritize which shortcuts to show other users and improves your ranking signal.

## Deep link integration

Every shortcut intent should use a [deep link URI](https://blog.michaelsam94.com/android-deeplink-attribution-install/) your app handles uniformly:

```kotlin
// MainActivity or NavHost handles myapp://items/{id}
when (uri.pathSegments.firstOrNull()) {
    "items" -> navController.navigate("item/${uri.lastPathSegment}")
    "notes" -> navController.navigate("notes/new")
}
```

Test shortcuts the same way you test deep links — they're the same mechanism with a different entry point.

## Refresh strategy

| Trigger | Action |
|---------|--------|
| User completes action | Update recents immediately |
| App foreground | Refresh if >30 min stale |
| Data sync completes | Rebuild affected shortcuts |
| Entity deleted | Remove corresponding shortcut |
| Logout | Clear all dynamic shortcuts |

Avoid refreshing on every frame or database write — batch updates and debounce.

## Dynamic shortcuts update

```kotlin
shortcutManager.dynamicShortcuts = listOf(
    ShortcutInfo.Builder(context, "order_${order.id}")
        .setShortLabel("Track order #${order.id}")
        .setIntent(trackIntent)
        .build()
)
```

Max 4 dynamic + 4 pinned shortcuts. Update when order status changes — stale shortcuts erode trust.

## Common production mistakes

Teams get app shortcuts dynamic wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Shipping app shortcuts dynamic on Android fails quietly when you test only on flagship devices, skip process-death scenarios, or assume `minSdk` behavior matches latest API docs. Emulator-only validation misses OEM-specific battery optimizations and background execution limits.

## Debugging and triage workflow

When app shortcuts dynamic misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [App shortcuts overview (Android)](https://developer.android.com/develop/ui/views/launch/shortcuts)
- [ShortcutManager reference](https://developer.android.com/reference/android/content/pm/ShortcutManager)
- [AndroidX ShortcutManagerCompat](https://developer.android.com/reference/androidx/core/content/pm/ShortcutManagerCompat)
- [Adaptive icons for shortcuts](https://developer.android.com/develop/ui/views/launch/icon_design_adaptive)
- [Deferred deep links and attribution](https://blog.michaelsam94.com/android-deeplink-attribution-install/)
