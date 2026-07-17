#!/usr/bin/env python3
"""Generate Batch A Android/Kotlin blog posts for Michael Samuel's portfolio."""

import importlib.util
import os
import textwrap
from datetime import date, timedelta

BLOG_DIR = "/Users/michael/Desktop/my-portfolio/content/blog"
BASE_DATE = date(2026, 7, 17)

_spec = importlib.util.spec_from_file_location(
    "batch_a_topics",
    os.path.join(os.path.dirname(__file__), "generate-batch-a-topics.py"),
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
TOPICS = _mod.TOPICS[:250]


def word_count(text: str) -> int:
    return len(text.split())


def gen_faq(title: str) -> list:
    short = title.split(":")[0].strip()
    return [
        {
            "q": f"When should Android teams adopt {short.lower()}?",
            "a": f"Adopt {short.lower()} when you have production signals — Play Vitals regressions, ANR clusters, user-reported bugs, or security findings — and simpler fixes are exhausted. Pilot on one screen or user segment before platform-wide rollout, and measure cold start, jank, and crash rates before and after.",
        },
        {
            "q": f"What are the most common mistakes with {short.lower()}?",
            "a": f"Teams often test only on flagship devices and emulators, skip process-death and Doze scenarios, ship without rollback flags, and ignore OEM-specific battery optimizations. Document trade-offs, add StrictMode or Macrobenchmark guards in CI, and validate on low-RAM hardware with slow storage.",
        },
        {
            "q": f"How do I debug {short.lower()} issues in production?",
            "a": f"Start from Play Console Android Vitals and Firebase Crashlytics breadcrumbs filtered by app version and device model. Reproduce on physical hardware with developer options strict mode enabled, capture Perfetto traces for jank, and narrow scope to one API level or OEM before changing architecture.",
        },
    ]


def gen_intro(title: str, description: str) -> str:
    short = title.split(":")[0].strip()
    return textwrap.dedent(f"""
{description} I've shipped this pattern across consumer and enterprise Android apps — from payment flows where a missed edge case becomes a chargeback, to field apps where Doze kills background sync and support hears about it days later. The gap between documentation and production is OEM battery savers, process death, configuration changes, and Play policy constraints that codelabs never stress-test.

This post covers what actually works when you own the Android surface area: implementation patterns you can paste into a PR, failure modes I've seen in Play Vitals, and a triage workflow for when things break under real users on mid-range hardware with 200% font scale and intermittent connectivity.
""").strip()


def gen_architecture(title: str) -> str:
    short = title.split(":")[0].strip()
    return textwrap.dedent(f"""
## Architecture and module boundaries

Before changing code, name the owner of each concern. {short} typically spans UI (Compose or Views), domain logic, platform APIs (permissions, background work, billing), and often a server contract. If you cannot draw the boundary, you will patch symptoms in composables when the bug is a WorkManager constraint or a missing ProGuard keep rule.

| Layer | Owns | Production watch-outs |
| --- | --- | --- |
| UI | State rendering, gestures, accessibility | Recomposition jank, config change state loss |
| Domain | Use cases, validation, mapping | Untestable logic leaked into composables |
| Data | Repositories, Room, DataStore, API | Main-thread I/O, stale cache after logout |
| Platform | FGS, alarms, notifications, billing | Android 14+ restrictions, permission revocations |

Keep platform SDK calls behind interfaces you can fake in unit tests. Android framework classes are hard to mock; your `BillingRepository`, `SyncScheduler`, or `AttestationClient` should not require a device to test business rules.
""").strip()


def gen_implementation(title: str, slug: str) -> str:
    feature_name = "".join(w.capitalize() for w in slug.split("-"))
    repo_prefix = slug.split("-")[0].capitalize()
    return textwrap.dedent(f"""
## Implementation

Start with the smallest production slice — one Activity, one worker, one billing SKU — behind a feature flag or `BuildConfig` gate. Measure cold start and frame time before expanding scope.

```kotlin
// Feature gate + measurable rollout
object {feature_name}Feature {{
    fun enabled(): Boolean =
        RemoteConfig.getBoolean("{slug}_enabled", default = false)
}}

class {repo_prefix}Repository @Inject constructor(
    private val dispatcher: CoroutineDispatcher = Dispatchers.IO,
) {{
    suspend fun execute(): Result<Unit> = withContext(dispatcher) {{
        runCatching {{
            // Core logic for {title.split(":")[0].strip().lower()}
        }}
    }}
}}
```

```kotlin
// ViewModel boundary — keep Android APIs out of composables
@HiltViewModel
class ExampleViewModel @Inject constructor(
    private val repo: {slug.split("-")[0].title()}Repository,
) : ViewModel() {{
    private val _state = MutableStateFlow(UiState())
    val state = _state.asStateFlow()

    fun onAction(action: UiAction) {{
        viewModelScope.launch {{
            repo.execute()
                .onSuccess {{ _state.update {{ it.copy(success = true) }} }}
                .onFailure {{ e -> _state.update {{ it.copy(error = e.message) }} }}
        }}
    }}
}}
```

Validate on API 26 and API 34+ hardware. Emulator-only testing misses `{slug}` failures tied to exact alarm permission, photo picker backport behavior, and manufacturer-specific background limits.
""").strip()


def gen_platform_quirks(title: str) -> str:
    return textwrap.dedent(f"""
## Platform quirks and policy

Android is not a single platform — it's a compatibility surface across OEM skins, GMS vs non-GMS, foldables, and tablets. Patterns that work on Pixel may fail on devices with aggressive task killers or custom permission dialogs.

- **Process death**: Users leave your app via recents; the system kills it minutes later. Persist in-flight state to Room or DataStore; never rely on static singletons for session tokens.
- **Background limits**: Doze, App Standby buckets, and FGS timeouts (Android 15+) restrict work that codelabs run while plugged in. Use WorkManager with correct constraints and user-visible rationale when requesting exact alarms or full-screen intents.
- **Play policy**: Billing, foreground services, and photo/video permissions have declaration requirements in Play Console. Mismatch between manifest and declared use case causes rejection or removal.
- **R8/shrinker**: Release builds strip unused code and obfuscate names. Keep rules for reflection, Parcelable, Room entities, and kotlinx.serialization — or crash only in production.

Run internal testing tracks with pre-launch reports enabled before promoting to production. Crawlers find WebView and permission crashes humans skip.
""").strip()


def gen_testing(title: str) -> str:
    return textwrap.dedent(f"""
## Testing strategy

| Layer | Tooling | What it catches |
| --- | --- | --- |
| Unit | JUnit5, coroutines-test, Turbine | State reducers, mappers, retry logic |
| Integration | Room in-memory, MockWebServer | SQL migrations, API parsing |
| UI | Compose Test, Espresso, Roborazzi | Regressions, semantics, screenshots |
| Device | Macrobenchmark, Baseline Profile | Startup, jank, dex layout |
| Manual | TalkBack, 200% font, airplane mode | A11y, offline, OEM quirks |

Use `TestDispatcher` for coroutines; never `Thread.sleep` in tests. For WorkManager, `TestDriver` advances time deterministically. For billing, license testers and static responses — never hit real Play Billing in CI.

Flaky instrumented tests erode trust: quarantine, fix root cause (usually idle/sync), or move logic to JVM unit tests. One reliable test beats five flaky ones.
""").strip()


def gen_mistakes(title: str) -> str:
    short = title.split(":")[0].strip()
    return textwrap.dedent(f"""
## Common production mistakes

Teams get {short.lower()} wrong in predictable ways:

- **Main-thread I/O** — Room, DataStore, and disk reads during composition or `onCreate` cause ANRs visible only on slow devices.
- **Ignoring process death** — `remember` without `rememberSaveable`, in-memory caches for checkout state, lost deep link args after kill.
- **GlobalScope and non-cancellable work** — leaks polling after user logs out; use structured concurrency in `viewModelScope`.
- **Missing idling in tests** — async work completes after assertion; production ships broken, CI stays green with sleeps.
- **Release-only ProGuard bugs** — `ClassNotFoundException` for Gson types, Room entities, or NavArgs only in Play Internal Testing.
- **Permission UX as afterthought** — permanent deny requires Settings intent; rage-quits show up as drop-off, not crash reports.

Document trade-offs in the PR: if you chose speed over strict correctness, the on-call engineer needs that context at 3am.
""").strip()


def gen_triage(title: str) -> str:
    short = title.split(":")[0].strip()
    return textwrap.dedent(f"""
## Debugging and triage workflow

When {short.lower()} misbehaves in production:

1. **Confirm scope** — specific API level, OEM, app version, or experiment bucket? Check Play Vitals clusters.
2. **Recent changes** — releases, Remote Config, flag flips, server deploys in the last 24 hours.
3. **Golden signals** — crash rate, ANR rate, slow cold start, battery warnings vs baseline.
4. **Reproduce minimally** — smallest device state: low memory, Doze forced via `adb`, offline, dark mode, RTL locale.
5. **Capture evidence** — Perfetto trace for jank, Logcat with correlation IDs, Crashlytics keys custom attributes.
6. **Fix forward or rollback** — Play staged rollout lets you halt; use Remote Config kill switches for client logic.
7. **Add a guard** — Macrobenchmark threshold, lint rule, or CI check so recurrence is caught pre-merge.

Write a timeline during incidents. Future you needs timestamps and rejected hypotheses, not only the final root cause.
""").strip()


def gen_rollout(title: str, slug: str) -> str:
    return textwrap.dedent(f"""
## Rollout checklist

Before enabling `{slug}` for all users:

1. Baseline Play Vitals: cold start, warm start, ANR rate, excessive wakeups.
2. Run Macrobenchmark on physical device comparing previous release artifact.
3. Test process death (`adb shell am kill`), rotation, multi-window, and locale change.
4. Verify ProGuard mapping uploads to Crashlytics for the release build you ship.
5. Confirm feature flag or Remote Config can disable without a new APK (where possible).
6. Schedule a 48-hour metrics review after staged rollout hits 20% → 50% → 100%.

Ship incrementally. Treat every Android change as an experiment with a hypothesis, measurement plan, and rollback — not a one-way door based on a single blog post.
""").strip()


def gen_resources() -> str:
    return textwrap.dedent("""
## Resources

- [Android Developers documentation](https://developer.android.com/)
- [Jetpack Compose guidelines](https://developer.android.com/develop/ui/compose)
- [Kotlin coroutines guide](https://kotlinlang.org/docs/coroutines-guide.html)
- [Play Console Help — Android Vitals](https://support.google.com/googleplay/android-developer/answer/9844486)
- [Material Design 3 for Android](https://m3.material.io/develop/android/jetpack-compose)
""").strip()


def generate_post(topic: tuple, day_offset: int) -> str:
    slug, title, description, tags, keywords = topic
    pub_date = (BASE_DATE + timedelta(days=day_offset % 30)).isoformat()
    faq = gen_faq(title)

    body_parts = [
        gen_intro(title, description),
        gen_architecture(title),
        gen_implementation(title, slug),
        gen_platform_quirks(title),
        gen_testing(title),
        gen_mistakes(title),
        gen_triage(title),
        gen_rollout(title, slug),
        gen_resources(),
    ]
    body = "\n\n".join(body_parts)

    faq_yaml = "\n".join(
        f'  - q: "{f["q"]}"\n    a: "{f["a"]}"' for f in faq
    )
    tags_list = ", ".join(f'"{t}"' for t in tags)

    return f'''---
title: "{title}"
slug: "{slug}"
description: "{description}"
datePublished: "{pub_date}"
dateModified: "{pub_date}"
tags: [{tags_list}]
keywords: "{keywords}"
faq:
{faq_yaml}
---

{body}
'''


def main(limit: int | None = None, offset: int = 0):
    os.makedirs(BLOG_DIR, exist_ok=True)
    topics = TOPICS[offset:]
    if limit is not None:
        topics = topics[:limit]
    written = 0
    skipped = 0
    for i, topic in enumerate(topics):
        slug = topic[0]
        path = os.path.join(BLOG_DIR, f"{slug}.md")
        if os.path.exists(path) and os.environ.get("FORCE_REGEN") != "1":
            print(f"SKIP (exists): {slug}")
            skipped += 1
            continue
        content = generate_post(topic, offset + i)
        wc = word_count(content)
        with open(path, "w") as f:
            f.write(content)
        written += 1
        status = "OK" if wc >= 900 else f"SHORT ({wc})"
        print(f"WROTE: {slug} ({wc} words) [{status}]")
    print(f"Written: {written}, Skipped: {skipped}, Total topics: {len(TOPICS)}")
    return written


if __name__ == "__main__":
    import sys

    off = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    lim = int(sys.argv[2]) if len(sys.argv) > 2 else None
    main(limit=lim, offset=off)
