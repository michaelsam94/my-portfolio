---
title: "The Android 12+ Splash Screen API"
slug: "android-splash-screen-api"
description: "Implement the Android 12+ Splash Screen API: SplashScreen compat library, animated icons, exit animations, and migrating from legacy splash screens."
datePublished: "2026-07-16"
dateModified: "2026-07-16"
tags: ["Android", "UX", "Startup", "Material Design"]
keywords: "Android Splash Screen API, SplashScreen compat, Android 12 splash screen, splash screen exit animation, migrate splash screen Android"
faq:
  - q: "Do I need to implement the Splash Screen API on Android 12+?"
    a: "Android 12+ shows a default system splash screen for every app regardless of your code — your app icon on a themed background. Without the SplashScreen compat library, you can't control its appearance or add an exit animation. Implement it to customize the icon, background, and transition into your app."
  - q: "How is the new Splash Screen API different from a splash Activity?"
    a: "The old pattern used a dedicated SplashActivity with a layout that delayed navigation until init completed. The new API is a system-managed splash that shows instantly on tap and dismisses when your first frame draws. No Activity, no layout, no artificial delay — just a themed icon that transitions into your app."
  - q: "Can I keep showing the splash screen while loading data?"
    a: "Yes — call splashScreen.setKeepOnScreenCondition { !isReady } to hold the splash visible until your condition returns false. Use this sparingly for critical init that must complete before showing UI. Don't hold the splash for analytics init or non-critical SDK setup."
---

Android 12 made splash screens mandatory — every app shows one on launch whether you want it or not. If you don't configure it, users see a generic system splash with your launcher icon on a white or black background. The SplashScreen compat library lets you customize the icon, background color, and exit animation, and critically, it backports the behavior to API 23+. The old pattern of a dedicated SplashActivity with a 2-second delay is dead — it fights the system splash, doubles launch time, and Google explicitly discourages it. Configure the system splash properly and delete your splash Activity.

## Setup

```kotlin
dependencies {
    implementation("androidx.core:core-splashscreen:1.0.1")
}
```

Apply the splash theme to your launcher Activity:

```xml
<!-- themes.xml -->
<style name="Theme.App.Starting" parent="Theme.SplashScreen">
    <item name="windowSplashScreenBackground">@color/splash_background</item>
    <item name="windowSplashScreenAnimatedIcon">@drawable/splash_icon</item>
    <item name="windowSplashScreenAnimationDuration">1000</item>
    <item name="postSplashScreenTheme">@style/Theme.App</item>
</style>
```

```xml
<!-- AndroidManifest.xml -->
<activity
    android:name=".MainActivity"
    android:theme="@style/Theme.App.Starting"
    android:exported="true">
    <intent-filter>...</intent-filter>
</activity>
```

## Install in Activity

```kotlin
class MainActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        installSplashScreen()
        super.onCreate(savedInstanceState)
        setContent { AppTheme { MainScreen() } }
    }
}
```

`installSplashScreen()` must be called before `super.onCreate()`. The splash dismisses automatically when the first frame draws.

## Animated icon

Android 12 supports animated vector drawables as splash icons:

```xml
<!-- res/drawable/splash_icon.xml -->
<animated-vector
    xmlns:android="http://schemas.android.com/apk/res/android"
    android:drawable="@drawable/ic_logo_static">
    <target android:name="path" android:animation="@anim/splash_path_anim"/>
</animated-vector>
```

Keep animations under 1000ms. The system enforces a maximum animation duration. Simple scale/fade works best — complex animations may not render on all devices.

## Exit animation

Customize the transition from splash to app content:

```kotlin
override fun onCreate(savedInstanceState: Bundle?) {
    val splashScreen = installSplashScreen()
    super.onCreate(savedInstanceState)

    splashScreen.setOnExitAnimationListener { splashViewProvider ->
        val slideUp = ObjectAnimator.ofFloat(
            splashViewProvider.view, View.TRANSLATION_Y, 0f, -splashViewProvider.view.height.toFloat()
        ).apply {
            duration = 300
            interpolator = AnticipateInterpolator()
            doOnEnd { splashViewProvider.remove() }
        }
        slideUp.start()
    }

    setContent { AppTheme { MainScreen() } }
}
```

Always call `splashViewProvider.remove()` when the animation ends — the system won't dismiss the splash view otherwise.

## Keep splash visible during init

For critical initialization that must complete before showing UI:

```kotlin
var isReady = false

override fun onCreate(savedInstanceState: Bundle?) {
    val splashScreen = installSplashScreen()
    splashScreen.setKeepOnScreenCondition { !isReady }
    super.onCreate(savedInstanceState)

    lifecycleScope.launch {
        loadCriticalData()
        isReady = true
    }

    setContent { AppTheme { MainScreen() } }
}
```

Use this only for data the first screen absolutely requires. For everything else, show the UI immediately and load asynchronously — see [startup optimization](https://blog.michaelsam94.com/android-app-startup-metrics-optimization/).

## Migrating from legacy splash

Delete:
- SplashActivity class
- splash_layout.xml
- Intent filter pointing to SplashActivity
- Handler.postDelayed navigation logic
- Any artificial delay

Replace with:
- SplashScreen theme on MainActivity
- `installSplashScreen()` in onCreate
- Move init logic to Application.onCreate or background coroutines

The system splash shows instantly on tap — faster than any custom splash Activity could render.

## Icon sizing

Splash icon guidelines:
- With background: 240×240 dp container, icon within the inner 160 dp circle
- Without background: 288×288 dp
- Use adaptive icon layers for best results on all device shapes

Test on circular, squircle, and rounded-square icon masks.

## SplashScreen API on Android 12+ vs older devices

`core-splashscreen` library backports the Android 12 splash to API 23+:

```kotlin
// build.gradle
implementation("androidx.core:core-splashscreen:1.0.1")

// themes.xml — both values and values-v31
<style name="Theme.App.Starting" parent="Theme.SplashScreen">
    <item name="windowSplashScreenBackground">@color/splash_bg</item>
    <item name="windowSplashScreenAnimatedIcon">@drawable/ic_splash</item>
    <item name="windowSplashScreenAnimationDuration">1000</item>
    <item name="postSplashScreenTheme">@style/Theme.App</item>
</style>

// Android 12+ only (values-v31/themes.xml)
<item name="android:windowSplashScreenBrandingImage">@drawable/branding</item>
```

On API 31+, system controls splash timing. On API 23–30, library emulates behavior — test both paths.

## Conditional splash screen retention

Keep splash visible until critical init completes — but cap retention time:

```kotlin
override fun onCreate(savedInstanceState: Bundle?) {
    val splashScreen = installSplashScreen()
    super.onCreate(savedInstanceState)

    var isReady = false
    splashScreen.setKeepOnScreenCondition { !isReady }

    lifecycleScope.launch {
        try {
            withTimeout(3000) {  // never block splash >3 seconds
                awaitAll(async { initAuth() }, async { loadConfig() })
            }
        } finally {
            isReady = true
        }
    }
}
```

Without timeout cap, slow network hangs splash indefinitely — users think app is frozen. 2–3 second maximum retention; show loading UI in app for longer operations.

## Splash screen theming for dark mode

Provide separate splash themes for light and dark:

```xml
<!-- values/themes.xml -->
<style name="Theme.App.Starting" parent="Theme.SplashScreen">
    <item name="windowSplashScreenBackground">@color/splash_bg_light</item>
    ...
</style>

<!-- values-night/themes.xml -->
<style name="Theme.App.Starting" parent="Theme.SplashScreen">
    <item name="windowSplashScreenBackground">@color/splash_bg_dark</item>
    ...
</style>
```

Splash background must match app's first screen background — jarring color flash on transition signals poor polish.

## Failure modes

- **Custom SplashActivity still present** — double splash; slower startup
- **Artificial delay (Thread.sleep)** — Google Play policy violation; users abandon app
- **Splash retention without timeout** — infinite splash on network failure
- **Mismatched splash and app background** — visible flash on transition
- **Icon too large/small** — clipped on circular masks; test all shapes

## Production checklist

- Legacy SplashActivity deleted; MainActivity uses SplashScreen theme
- `installSplashScreen()` called before `super.onCreate()`
- Retention capped at 3 seconds with timeout
- Light and dark splash themes matching app first screen
- Icon tested on circular, squircle, and rounded-square masks
- No artificial delays in splash or startup path

## Resources

- [Splash Screen API guide (Android)](https://developer.android.com/develop/ui/views/launch/splash-screen)
- [core-splashscreen library reference](https://developer.android.com/reference/kotlin/androidx/core/splashscreen/SplashScreen)
- [Migrate existing splash screens](https://developer.android.com/develop/ui/views/launch/splash-screen/migrate)
- [App startup optimization](https://blog.michaelsam94.com/android-app-startup-metrics-optimization/)
- [Adaptive icons for splash screens](https://developer.android.com/develop/ui/views/launch/icon_design_adaptive)
