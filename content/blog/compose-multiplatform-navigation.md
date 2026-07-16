---
title: "Navigation in Compose Multiplatform"
slug: "compose-multiplatform-navigation"
description: "Set up type-safe navigation in Compose Multiplatform with Voyager, Decompose, or Navigation Compose patterns shared across Android, iOS, and desktop."
datePublished: "2025-04-03"
dateModified: "2025-04-03"
tags: ["Android", "Compose"]
keywords: "Compose Multiplatform navigation, Voyager navigator, Decompose router, KMP navigation, type-safe routes"
faq:
  - q: "Does Navigation Compose work on Compose Multiplatform?"
    a: "Jetpack Navigation Compose targets Android. For KMP, teams use Voyager, Decompose, PreCompose, or custom router implementations in commonMain. These libraries provide back stack, screen parameters, and lifecycle in shared code while platform entry points host the NavHost equivalent on each target."
  - q: "How do I pass arguments between screens in KMP?"
    a: "Prefer type-safe serializable route objects over string paths. Voyager uses Screen classes with constructor params; Decompose uses sealed configurations parsed from back stack entries. Avoid global singletons for navigation args—they break process death recovery and test isolation."
  - q: "How is deep linking handled in Compose Multiplatform?"
    a: "Parse platform URLs in androidMain/iosMain entry Activity or UIViewController, map to a shared route object, and push onto the common navigator. iOS universal links and Android App Links resolve in platform code; navigation state lives in commonMain ViewModels tied to the router."
---

Compose Multiplatform lets you share UI across Android, iOS, desktop, and Web—but Navigation Compose stopped at the JVM/Android fence. Every KMP app picks a third-party navigator or rolls a back stack in `commonMain`. The decision matters early: navigation touches ViewModels, dependency injection, and deep links. Switching libraries after forty screens is miserable.

## Architecture split

```
commonMain/
  navigation/ Routes.kt, AppNavigator.kt
  ui/screens/ HomeScreen.kt, DetailScreen.kt
  viewmodel/ Shared ViewModels

androidMain/ MainActivity hosts Navigator
iosMain/     ComposeUIViewController hosts Navigator
jvmMain/     Window hosts Navigator
```

Platform code creates the root navigator and passes platform-specific dependencies (browser opener, share sheet) through interfaces.

## Voyager: Screen-based navigation

Voyager models each destination as a `Screen` composable:

```kotlin
// commonMain
class HomeScreen : Screen {
    @Composable
    override fun Content() {
        val navigator = LocalNavigator.currentOrThrow
        Button(onClick = { navigator.push(DetailScreen(id = "42")) }) {
            Text("Open detail")
        }
    }
}

class DetailScreen(private val id: String) : Screen {
    @Composable
    override fun Content() {
        Text("Detail $id")
    }
}

@Composable
fun App() {
    Navigator(HomeScreen())
}
```

Voyager provides `ScreenModel` (similar to ViewModel) scoped to screens, tab navigation, and bottom sheet integration. It is pure Compose—no external lifecycle dependency.

## Decompose: component tree + router

Decompose fits teams already using explicit component lifecycles:

```kotlin
// commonMain
interface RootComponent {
    val childStack: Value<ChildStack<Config, Child>>
    fun onBackClicked()
}

@Serializable
sealed class Config {
    @Serializable data object Home : Config()
    @Serializable data class Detail(val id: String) : Config()
}

class DefaultRootComponent(
    componentContext: ComponentContext,
) : RootComponent, ComponentContext by componentContext {

    private val navigation = StackNavigation<Config>()

    override val childStack: Value<ChildStack<Config, Child>> =
        childStack(
            source = navigation,
            serializer = Config.serializer(),
            initialConfiguration = Config.Home,
            handleBackButton = true,
            childFactory = ::createChild,
        )

    private fun createChild(config: Config, context: ComponentContext): Child =
        when (config) {
            Config.Home -> Child.Home(HomeComponent(context) { id ->
                navigation.push(Config.Detail(id))
            })
            is Config.Detail -> Child.Detail(DetailComponent(context, config.id))
        }
}
```

Decompose integrates with ` kotlinx.serialization` for state preservation across process death on Android and configuration changes.

## Shared ViewModel pattern

Regardless of library, scope ViewModels to navigation entries:

```kotlin
// Voyager ScreenModel example
class DetailScreenModel(private val id: String) : ScreenModel {
    private val _state = MutableStateFlow(DetailState())
    val state = _state.asStateFlow()

    init { loadDetail(id) }
}
```

Inject repositories in commonMain via Koin or manual constructor injection from platform entry points.

## Bottom navigation and tabs

Multi-tab apps need parallel back stacks—one per tab:

```kotlin
// Voyager
TabNavigator(HomeTab) {
    Scaffold(
        bottomBar = { /* CurrentTab NavigationBar */ },
    ) {
        CurrentTab()
    }
}
```

Decompose offers `ChildPages` or separate stack components per tab with a parent coordinating tab selection.

## iOS-specific hosting

On iOS, wrap the shared `@Composable fun App()` in `ComposeUIViewController`. Handle swipe-back by forwarding to navigator pop:

```kotlin
fun MainViewController(): UIViewController = ComposeUIViewController {
    App(onBack = { /* navigator pop if can */ })
}
```

System back gesture on iOS is not automatic—wire edge swipe to your navigator.

## Testing navigation in commonTest

Voyager screens are composable—use Compose UI testing on Android JVM or Robolectric. Decompose components test via direct navigation calls:

```kotlin
val root = DefaultRootComponent(DefaultComponentContext(LifecycleRegistry()))
root.childStack.value.active.instance // assert Home
// trigger navigation callback
root.childStack.value.active.instance // assert Detail
```

## Choosing a library

| Library | Best for | Trade-off |
|---------|----------|-----------|
| Voyager | Pure Compose teams, quick start | Smaller ecosystem |
| Decompose | Explicit lifecycle, complex flows | Learning curve |
| PreCompose | Navigation Compose-like API | Maintenance varies |

Pick one before building more than five screens. Migration cost rises fast.

## Shared navigation state across platforms

Pass navigation state through a common ViewModel or repository:

```kotlin
// commonMain
class AppNavigator {
    private val _backStack = mutableStateListOf<Screen>()
    val backStack: List<Screen> get() = _backStack

    fun navigate(screen: Screen) { _backStack.add(screen) }
    fun pop() { if (_backStack.size > 1) _backStack.removeLast() }
}

// Platform-specific back gesture
// Android: BackHandler { navigator.pop() }
// iOS: swipe-back gesture via Voyager navigator
// Desktop: window close button
```

Centralize back stack in common code — platform code only wires hardware back button or gesture to `navigator.pop()`.

## Deep linking on mobile targets

Voyager supports deep links via initial screen parameter:

```kotlin
// androidMain
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val deepLinkScreen = intent.data?.let { parseDeepLink(it) }
        setContent {
            App(initialScreen = deepLinkScreen ?: HomeScreen)
        }
    }
}
```

Parse deep link URLs in platform-specific code, pass resolved screen to shared App composable. iOS handles Universal Links similarly in `iosMain`.

## Platform-specific transitions

Navigation transitions differ by platform — abstract behind expect/actual:

```kotlin
// commonMain
expect fun defaultTransition(): ScreenTransition

// androidMain
actual fun defaultTransition() = SlideTransition()

// iosMain
actual fun defaultTransition() = CupertinoTransition()
```

Users expect platform-native feel — sliding on Android, Cupertino push on iOS. Voyager and Decompose both support custom transitions per platform.

## Failure modes

- **Mixing navigation libraries mid-project** — migration cost exponential after 5+ screens
- **Navigation state in platform code** — can't test in commonTest; keep in shared layer
- **No deep link handling on one platform** — broken links from marketing campaigns
- **Desktop back button not wired** — users trapped in nested screens
- **Shared ViewModel scoped wrong** — state leaks between screens after pop

## Production checklist

- Navigation library chosen before building 5+ screens
- Back stack managed in commonMain code
- Platform back gesture/button wired to shared navigator
- Deep links parsed in platform code, resolved screen passed to App
- Platform-native transitions configured per target
- Navigation testable in commonTest without platform dependencies

## Common production mistakes

Teams get multiplatform navigation wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Compose UI work on multiplatform navigation janks when recomposition scope is too wide, `remember` keys omit stable inputs, and semantics for TalkBack are added only after QA finds focus traps.

## Resources

- [Voyager documentation](https://voyager.adriel.cafe/)
- [Decompose overview](https://arkivanov.github.io/Decompose/)
- [Compose Multiplatform setup](https://www.jetbrains.com/help/kotlin-multiplatform-dev/compose-multiplatform.html)
- [Kotlin Multiplatform samples navigation](https://github.com/Kotlin/kmp-native-wizard)
