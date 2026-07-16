---
title: "Activity Embedding for Large Screens"
slug: "android-window-manager-embedding-activities"
description: "Activity embedding splits single-activity apps into two-pane layouts on foldables and tablets. Configure WindowManager rules, handle configuration changes, and test on large-screen emulators."
datePublished: "2024-09-15"
dateModified: "2024-09-15"
tags: ["Android", "Large Screens", "WindowManager", "Foldables"]
keywords: "Activity embedding, WindowManager Jetpack, split layout Android, foldable two pane, ActivityRule, SplitPairRule"
faq:
  - q: "What is activity embedding?"
    a: "Activity embedding lets a single app display two activities side-by-side in one task on large screens — list on the left, detail on the right — without rewriting navigation to fragments. WindowManager Jetpack rules define when and how activities split based on window width and device posture."
  - q: "Do I need to rewrite my app with fragments for large screens?"
    a: "No. Activity embedding works with existing multi-activity apps. You declare SplitPairRule or ActivityRule in XML and the system places activities in adjacent panes. It's the fastest path to two-pane UX for apps already using Activities for navigation."
  - q: "How does embedding behave when the user folds a foldable?"
    a: "When the available width drops below your rule's minWidth or minSmallestWidth, the system collapses to single-pane and shows the most recently focused activity. Handle saved state and back stack correctly — the detail activity should restore when unfolding if the list selection persists."
---

Shipping a phone-only activity stack on a 12-inch tablet shows one lonely screen with 60% empty margin. Rewriting to single-activity + Navigation Compose is the long-term fix, but it's a multi-sprint migration. Activity embedding — part of WindowManager Jetpack — gives you list-detail split layouts by declaring XML rules, no fragment refactor required. Google uses this pattern in their own apps on Pixel Fold and Galaxy Tab.

## How it works

Your app remains multiple activities. WindowManager reads `SplitPairRule` definitions and places two activities from the same task in adjacent containers when width thresholds are met.

```
[ ListActivity ] | [ DetailActivity ]   ← width >= 600dp
[ DetailActivity ]                      ← width < 600dp (detail focused)
```

## Dependencies and manifest

```kotlin
implementation("androidx.window:window:1.2.0")
```

Enable embedding in `AndroidManifest.xml`:

```xml
<application>
    <property
        android:name="android.window.PROPERTY_ACTIVITY_EMBEDDING_SPLITS_ENABLED"
        android:value="true" />
</application>
```

## Split pair rules

Create `res/xml/split_config.xml`:

```xml
<resources>
    <SplitPairRule
        android:finishPrimaryWithSecondary="never"
        android:finishSecondaryWithPrimary="always"
        android:clearTop="false"
        android:splitRatio="0.38"
        android:splitMinWidthDp="600"
        android:splitMinSmallestWidthDp="600">
        <SplitPairFilter
            android:primaryActivityName=".ListActivity"
            android:secondaryActivityName=".DetailActivity" />
    </SplitPairRule>
</resources>
```

Reference it from the manifest:

```xml
<application>
    <meta-data
        android:name="android.window.PROPERTY_ACTIVITY_EMBEDDING_RULES"
        android:resource="@xml/split_config" />
</application>
```

`finishSecondaryWithPrimary="always"` closes the detail pane when the user backs out of the list — standard list-detail behavior.

## Launching the secondary activity

From `ListActivity`, launch detail without flags that break embedding:

```kotlin
fun openDetail(itemId: String) {
    startActivity(
        Intent(this, DetailActivity::class.java)
            .putExtra(EXTRA_ITEM_ID, itemId)
    )
}
```

Don't use `FLAG_ACTIVITY_NEW_TASK` — it breaks same-task splitting.

## Programmatic rules (Kotlin API)

For dynamic behavior (feature flags, A/B splits):

```kotlin
class MyApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        val ruleController = SplitController.getInstance(this)
        val rule = SplitPairRule.Builder(
            listOf(
                SplitPairFilter(
                    ComponentName(this, ListActivity::class.java),
                    ComponentName(this, DetailActivity::class.java),
                    null
                )
            )
        )
            .setMinWidthDp(600)
            .setSplitRatio(0.4f)
            .setFinishPrimaryWithSecondary(SplitRule.FinishBehavior.NEVER)
            .setFinishSecondaryWithPrimary(SplitRule.FinishBehavior.ALWAYS)
            .build()
        ruleController.registerRule(rule)
    }
}
```

## Placeholder activity for empty detail

On first launch in split mode, the secondary pane may be empty. Use a placeholder:

```xml
<ActivityRule
    android:alwaysExpand="false"
    android:splitMinWidthDp="600">
    <ActivityFilter android:activityName=".PlaceholderActivity" />
</ActivityRule>
```

`PlaceholderActivity` shows "Select an item" until the user picks from the list.

## Testing

Use Android Studio's resizable emulator or the Desktop AVD for foldables. Test four states:

1. Unfolded, list focused
2. Unfolded, detail focused
3. Folded portrait (single pane)
4. Configuration change (rotation) mid-split

Verify `ViewModel` state survives — `SavedStateHandle` works normally across embedded activities in the same task.

## Embedding vs responsive Compose

| Approach | Effort | Best for |
|----------|--------|----------|
| Activity embedding | Low | Existing multi-activity apps |
| Navigation Compose adaptive | Medium | New apps, shared ViewModels |
| Fragments + SlidingPaneLayout | Medium–High | Legacy single-activity |

If you're already on [Material3 adaptive navigation](https://blog.michaelsam94.com/android-material3-adaptive-navigation/), embedding is a bridge, not the destination. But for apps with 15 activities and a tablet launch deadline, embedding ships in days.

## Split behavior on foldables

Foldables add posture transitions that pure width-based rules don't cover:

```xml
<SplitPairRule
    android:splitMinWidthDp="600"
    android:splitMinSmallestWidthDp="600"
    android:splitRatio="0.38"
    android:finishPrimaryWithSecondary="never"
    android:finishSecondaryWithPrimary="always">
    <SplitPairFilter
        android:primaryActivityName=".ListActivity"
        android:secondaryActivityName=".DetailActivity" />
</SplitPairRule>
```

When user folds from tablet to phone:
1. System collapses to single pane
2. Most recently focused activity shown (usually detail)
3. List selection state must persist in ViewModel/SavedStateHandle
4. When unfolded, split restores if width threshold met

Test the fold/unfold cycle specifically — not just static tablet and phone layouts. `WindowInfoTracker` provides fold state:

```kotlin
WindowInfoTracker.getOrCreate(context)
    .windowLayoutInfo(activity)
    .collect { layoutInfo ->
        val foldingFeature = layoutInfo.displayFeatures
            .filterIsInstance<FoldingFeature>()
            .firstOrNull()
        // Adjust UI based on fold state
    }
```

## Back stack management in split mode

Back button behavior in embedded activities requires careful configuration:

| Setting | Behavior |
|---|---|
| `finishSecondaryWithPrimary="always"` | Back from list closes detail (standard) |
| `finishSecondaryWithPrimary="never"` | Detail persists when navigating list |
| `finishPrimaryWithSecondary="always"` | Back from detail closes list too |
| `clearTop="true"` | New detail replaces existing detail in pane |

For master-detail: `finishSecondaryWithPrimary="always"` and `finishPrimaryWithSecondary="never"` — standard Gmail/Settings pattern.

## Multi-pane with three activities

Some apps need three-pane layouts (navigation rail + list + detail):

```xml
<SplitPlaceholderRule
    android:splitMinWidthDp="840"
    android:splitRatio="0.25"
    android:placeholderActivityName=".NavPlaceholder">
    <SplitPairFilter
        android:primaryActivityName=".NavActivity"
        android:secondaryActivityName=".ListActivity" />
</SplitPlaceholderRule>

<SplitPairRule android:splitMinWidthDp="840" android:splitRatio="0.5">
    <SplitPairFilter
        android:primaryActivityName=".ListActivity"
        android:secondaryActivityName=".DetailActivity" />
</SplitPairRule>
```

Three-pane requires 840dp+ width — target unfolded foldables and large tablets.

## Failure modes

- **FLAG_ACTIVITY_NEW_TASK on detail launch** — breaks same-task embedding
- **No placeholder activity** — empty secondary pane on first launch in split mode
- **State lost on fold/unfold** — ViewModel not scoped correctly across configuration change
- **Back stack confusion** — wrong finishPrimary/Secondary settings
- **Not tested on foldable** — works on tablet emulator but breaks on actual fold transition

## Production checklist

- Split rules defined in XML with width and smallestWidth thresholds
- Placeholder activity for empty detail pane on first launch
- No FLAG_ACTIVITY_NEW_TASK on embedded activity launches
- Fold/unfold transition tested on physical foldable device
- Back stack finish behaviors configured for master-detail pattern
- ViewModel state survives configuration changes and fold transitions
- Large screen quality guidelines met (Google Play tablet/foldable badges)

Google Play's large screen quality tier requires activity embedding or adaptive layouts for tablet/foldable badge eligibility — embedding is the fastest path for existing multi-activity apps.

Test activity embedding on foldables in both folded and unfolded postures — split ratios that work on desktop emulators break on narrow cover displays.

## Resources

- [Activity embedding overview](https://developer.android.com/guide/topics/large-screens/activity-embedding)
- [WindowManager Jetpack SplitController](https://developer.android.com/reference/androidx/window/embedding/SplitController)
- [SplitPairRule XML reference](https://developer.android.com/reference/androidx/window/embedding/SplitPairRule)
- [Large screen app quality guidelines](https://developer.android.com/docs/quality-guidelines/large-screen-app-quality)
- [Test foldable apps guide](https://developer.android.com/guide/topics/large-screens/test-on-foldables)
