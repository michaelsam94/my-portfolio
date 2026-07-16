---
title: "JVM Android Tests with Robolectric"
slug: "android-testing-robolectric"
description: "Robolectric runs Android framework code on the JVM for fast unit and integration tests. Configure SDK levels, shadows, Hilt test modules, and Compose tests without emulators."
datePublished: "2024-08-26"
dateModified: "2024-08-26"
tags: ["Android", "Testing", "Robolectric", "JUnit"]
keywords: "Robolectric, JVM Android tests, shadow framework, Robolectric Hilt, Compose Robolectric, Android unit tests"
faq:
  - q: "When should I use Robolectric instead of instrumented tests?"
    a: "Use Robolectric for logic that touches Android framework classes — SharedPreferences, Intent parsing, BroadcastReceivers, ViewModels with SavedStateHandle — when you don't need real GPU rendering or OEM-specific behavior. Keep instrumented tests for CameraX, Bluetooth, notifications on real devices, and end-to-end flows."
  - q: "Does Robolectric work with Hilt?"
    a: "Yes. Use @HiltAndroidTest with @RunWith(RobolectricTestRunner::class) and HiltRobolectricTestRunner, or the standard Hilt test setup with @Config to specify the application class. Replace production modules with @TestInstallIn modules for fakes."
  - q: "Why do Robolectric tests behave differently across SDK levels?"
    a: "Robolectric simulates API behavior per @Config(sdk = [...]). Permission models, notification channels, and background execution rules differ by API level. Pin the SDK in tests to match your minSdk or the specific API you're testing, and use @Config(sdk = [33]) consistently across the module."
---

Instrumented tests are honest but slow. Booting an emulator for every PR adds minutes to CI and encourages developers to skip tests locally. Robolectric runs real Android framework bytecode on the JVM using modified class loaders and shadow implementations — your `Context.getSharedPreferences` call executes against an in-memory shadow, not a mock you maintain by hand. The result: tests that exercise actual framework code paths in milliseconds.

## Project setup

```kotlin
// build.gradle.kts
dependencies {
    testImplementation("org.robolectric:robolectric:4.12")
    testImplementation("androidx.test:core:1.5.0")
    testImplementation("androidx.test.ext:junit:1.1.5")
}
```

```kotlin
@RunWith(RobolectricTestRunner::class)
@Config(manifest = Config.NONE, sdk = [33])
class PreferencesRepositoryTest {

    @Test
    fun savesToken() {
        val context = ApplicationProvider.getApplicationContext<Context>()
        val prefs = context.getSharedPreferences("auth", Context.MODE_PRIVATE)
        prefs.edit().putString("token", "abc123").apply()

        val repo = PreferencesRepository(context)
        assertEquals("abc123", repo.getToken())
    }
}
```

`ApplicationProvider.getApplicationContext()` returns a Robolectric-managed context backed by shadows.

## SDK and device configuration

Control screen size, locale, and API level:

```kotlin
@Config(
    sdk = [28],
    qualifiers = "fr-rFR-w360dp-h640dp-port-xhdpi"
)
class LocaleFormattingTest {
    @Test
    fun formatsDateInFrench() {
        val formatted = DateFormatter.format(Instant.parse("2024-03-15T10:00:00Z"))
        assertTrue(formatted.contains("mars"))
    }
}
```

I've debugged "works on CI, fails locally" issues caused by mismatched `@Config(sdk)` — standardize on one SDK per module unless testing version-specific branches.

## Testing components

**BroadcastReceiver:**

```kotlin
@Test
fun receiverHandlesBootComplete() {
    val receiver = SyncAlarmReceiver()
    val intent = Intent(Intent.ACTION_BOOT_COMPLETED)
    receiver.onReceive(ApplicationProvider.getApplicationContext(), intent)
    assertTrue(AlarmScheduler.wasScheduled)
}
```

**Activity and Fragment (with AndroidX Test):**

```kotlin
@RunWith(AndroidJUnit4::class)
@Config(sdk = [33])
class MainActivityTest {

    @get:Rule
    val activityRule = ActivityScenarioRule(MainActivity::class.java)

    @Test
    fun showsWelcomeText() {
        onView(withId(R.id.welcome)).check(matches(withText("Welcome")))
    }
}
```

## Hilt integration

```kotlin
@HiltAndroidTest
@RunWith(RobolectricTestRunner::class)
@Config(application = HiltTestApplication_Application::class)
class UserViewModelTest {

    @get:Rule
    var hiltRule = HiltAndroidRule(this)

    @Inject lateinit var repository: FakeUserRepository
    @Inject lateinit var viewModel: UserViewModel

    @Before fun setup() { hiltRule.inject() }

    @Test
    fun loadsUser() = runTest {
        repository.enqueueUser(User(id = "1", name = "Alex"))
        viewModel.load("1")
        assertEquals("Alex", viewModel.state.value.name)
    }
}
```

Replace network modules with fakes via `@TestInstallIn(components = [SingletonComponent::class], replaces = [NetworkModule::class])`.

## Compose on Robolectric

```kotlin
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [33])
class LoginScreenTest {

    @get:Rule val composeRule = createComposeRule()

    @Test
    fun submitDisabledWhenEmpty() {
        composeRule.setContent {
            MyTheme { LoginScreen(onSubmit = {}) }
        }
        composeRule.onNodeWithText("Sign in").assertIsNotEnabled()
    }
}
```

Native graphics mode matters for Compose — legacy Robolectric rendering misses layout edge cases that show up on devices.

## Shadows and limitations

Robolectric replaces framework internals with `@Implements` shadow classes. Most public APIs work; some don't:

| Works well | Problematic |
|-----------|-------------|
| SharedPreferences, SQLite | Real OpenGL / Camera HAL |
| Intents, Bundles | OEM-specific extensions |
| AlarmManager, JobScheduler | Some Bluetooth APIs |
| Resources, themes | Hardware sensors |

When a shadow is incomplete, `@Config(shadows = [CustomShadow.class])` lets you override behavior for your test.

## CI configuration

Robolectric downloads Android SDK jars on first run. On CI, cache `~/.gradle/caches` and `~/.m2/repository/org/robolectric`. Run with:

```bash
./gradlew testDebugUnitTest --no-daemon
```

No emulator required — this is why Robolectric belongs in every Android module's default test task.

## Testing ViewModels and coroutines

Robolectric supports `runTest` for coroutine-based ViewModels without instrumented tests:

```kotlin
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [33])
class OrderViewModelTest {

    @get:Rule
    val mainDispatcherRule = MainDispatcherRule()

    private lateinit var viewModel: OrderViewModel
    private val fakeRepo = FakeOrderRepository()

    @Before
    fun setup() {
        viewModel = OrderViewModel(fakeRepo)
    }

    @Test
    fun loadOrder_success() = runTest {
        fakeRepo.enqueue(Order(id = "1", total = 99.99))
        viewModel.loadOrder("1")
        advanceUntilIdle()
        assertEquals(99.99, viewModel.uiState.value.total)
    }

    @Test
    fun loadOrder_error() = runTest {
        fakeRepo.enqueueError(IOException("Network error"))
        viewModel.loadOrder("1")
        advanceUntilIdle()
        assertTrue(viewModel.uiState.value is OrderUiState.Error)
    }
}
```

`MainDispatcherRule` replaces `Dispatchers.Main` with a test dispatcher — essential for ViewModel tests that use `viewModelScope`.

## SavedStateHandle testing

Process death scenarios without instrumented tests:

```kotlin
@Test
fun restoresStateFromSavedStateHandle() {
    val savedState = SavedStateHandle(mapOf("query" to "kotlin"))
    val viewModel = SearchViewModel(savedState, fakeRepo)

    assertEquals("kotlin", viewModel.query.value)
}
```

## Parallel execution and test sharding

Robolectric tests are JVM tests — run in parallel on CI:

```kotlin
// build.gradle.kts
tasks.withType<Test> {
    maxParallelForks = Runtime.getRuntime().availableProcessors() / 2
}
```

For large test suites (500+ Robolectric tests), shard across CI matrix jobs:

```yaml
# GitHub Actions
strategy:
  matrix:
    shard: [0, 1, 2, 3]
steps:
  - run: ./gradlew testDebugUnitTest -Probolectric.tests.shard=${{ matrix.shard }}/4
```

## Failure modes

- **Mismatched SDK across module** — tests pass locally, fail on CI; standardize `@Config(sdk)`
- **Testing on main thread** — Robolectric runs on JVM thread; use `MainDispatcherRule` for coroutines
- **Incomplete shadows** — some APIs silently return defaults; verify shadow behavior
- **Compose without native graphics** — layout tests miss rendering issues; use `@GraphicsMode(NATIVE)`
- **Not caching SDK jars on CI** — first run downloads SDK artifacts; cache Gradle caches

## Production checklist

- SDK level standardized per module in `@Config`
- MainDispatcherRule used for coroutine ViewModel tests
- Hilt test modules replace production dependencies with fakes
- Compose tests use native graphics mode
- CI runs unit tests without emulator (Robolectric + JVM)
- Gradle caches configured for Robolectric SDK jars on CI
- Parallel test execution enabled for speed

## Robolectric vs instrumented tests: decision guide

| Scenario | Robolectric | Instrumented |
|---|---|---|
| ViewModel unit tests | ✅ Fast JVM | ❌ Slow emulator |
| Compose layout tests | ✅ With native graphics | ✅ Real rendering |
| Screenshot tests | ✅ Roborazzi | ✅ Paparazzi/on-device |
| Navigation integration | ✅ JVM | ✅ Real back stack |
| Hardware APIs (Bluetooth, NFC) | ❌ Shadow incomplete | ✅ Required |
| Performance benchmarks | ❌ Not representative | ✅ Required |

Default to Robolectric for unit and layout tests. Reserve instrumented tests for hardware-dependent features and performance validation. Target ratio: 80% Robolectric, 20% instrumented.

Pin Robolectric SDK version to match your compileSdk — shadow implementations drift between versions and cause false greens in CI.

## Resources

- [Robolectric documentation](https://robolectric.org/)
- [Robolectric device configuration](https://robolectric.org/device-configuration/)
- [Hilt testing guide](https://developer.android.com/training/dependency-injection/hilt-testing)
- [AndroidX Test core APIs](https://developer.android.com/training/testing/local-tests)
- [Robolectric 4.x migration notes](https://robolectric.org/upgrading/)
