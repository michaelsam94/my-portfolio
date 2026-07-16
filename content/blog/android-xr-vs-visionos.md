---
title: "Building for Android XR vs visionOS"
slug: "android-xr-vs-visionos"
description: "Building for Android XR vs visionOS: comparing the SDKs, spatial UI models, input paradigms, tooling, and how a mobile developer should think about targeting both headsets."
datePublished: "2026-04-23"
dateModified: "2026-04-23"
tags: ["Spatial Computing", "Android", "AR/VR"]
keywords: "Android XR, visionOS, spatial computing, XR development, Jetpack XR, mixed reality apps, headset development"
faq:
  - q: "What is the difference between Android XR and visionOS?"
    a: "Android XR is Google's operating system and SDK for extended-reality headsets and glasses, built on Android with Jetpack XR APIs and deep integration with Gemini, so existing Android and Compose knowledge transfers. visionOS is Apple's platform for the Vision Pro, built on its own frameworks (SwiftUI, RealityKit, ARKit) with an eye-and-hand input model. They target the same category but come from opposite ecosystems and design philosophies."
  - q: "Can I reuse my existing mobile app on these XR platforms?"
    a: "Partly. Both platforms can run existing 2D apps in floating windows with little to no change — an Android app runs on Android XR, an iPad/iOS app runs on visionOS. But to build genuinely spatial experiences with 3D content, volumetric layouts, and hand or eye input, you write to each platform's spatial APIs, and that work does not port automatically between them."
  - q: "Which language and tools do Android XR and visionOS use?"
    a: "Android XR uses Kotlin with Jetpack Compose and Jetpack XR, plus Unity and OpenXR for 3D-heavy apps, within Android Studio. visionOS uses Swift with SwiftUI and RealityKit, plus Reality Composer Pro and Unity's PolySpatial, within Xcode. If you already ship Android, Android XR has the shorter learning curve; if you ship iOS, visionOS does."
---

Two of the biggest platform owners have now planted flags in spatial computing, and they've done it in characteristically different ways. Android XR is Google building headset and glasses software on top of Android, so Kotlin, Jetpack Compose, and your existing Android instincts carry forward, with Gemini woven in as an assistant layer. visionOS is Apple building an entirely Apple-shaped platform for Vision Pro — Swift, SwiftUI, RealityKit, and an input model driven by where your eyes look and how your fingers pinch. For a mobile developer deciding where to invest, the interesting question isn't which is "better," it's which fits your existing skills and product, and what actually transfers.

I come at this as an Android and Flutter developer, so I'll be honest about my starting bias while trying to give visionOS a fair reading. The short version: the platforms rhyme conceptually and diverge sharply in execution.

## The ecosystem starting point

The most important fact about each platform is where it comes from, because that determines your ramp-up cost.

| Aspect | Android XR | visionOS |
|---|---|---|
| Language | Kotlin | Swift |
| Declarative UI | Jetpack Compose | SwiftUI |
| 3D framework | Jetpack XR / OpenXR / Unity | RealityKit / Unity PolySpatial |
| Tooling | Android Studio | Xcode + Reality Composer Pro |
| AI layer | Gemini integration | Apple Intelligence |
| Runs existing apps | Android apps in windows | iPad/iOS apps in windows |

If you already ship Android, Android XR is a genuinely gentle on-ramp — the same [Compose Multiplatform shared UI](https://blog.michaelsam94.com/compose-multiplatform-shared-ui/) mental model applies, and much of your 2D UI can appear as a floating panel with minimal changes. If you ship iOS, visionOS is the natural extension. The platforms deliberately let your existing 2D app show up in a window on day one, which lowers the barrier but is also a trap: a floating phone app in a headset is not a spatial app, and users can tell.

## The spatial UI models

Both platforms think in a progression from familiar to fully immersive, and the vocabulary maps closely even though the APIs don't:

- **Windows / 2D panels** — your existing flat UI, floating in space. Cheapest to build, least "spatial."
- **Volumes / bounded 3D** — a 3D object or scene contained in a box you can walk around. This is where spatial design actually begins.
- **Immersive / unbounded space** — content fills the room or replaces it entirely, mixing with or occluding the real world.

On Android XR you express these through Jetpack XR's spatial APIs, promoting Compose UI into spatial panels and adding 3D content. On visionOS you use SwiftUI scene types (`WindowGroup`, `Volume`, `ImmersiveSpace`) alongside RealityKit entities. The senior observation: the hard part isn't the API, it's the design. Laying out a comfortable, legible spatial UI — how far away, how big, how it reacts to your head moving — is a new discipline, and both platforms make it easy to build something technically working but physically uncomfortable. Depth, scale, and reachability are the new constraints, and neither SDK saves you from bad spatial design.

## Input: the real divergence

This is where the platforms feel most different in the hand (literally). visionOS bet hard on **eye tracking plus pinch**: you look at a target and pinch your fingers to select. It's uncannily good when it works and means UI elements need generous hit targets and hover states designed for gaze. Android XR supports a broader range — controllers, hand tracking, and gaze — reflecting a more heterogeneous hardware landscape across devices and glasses form factors.

The practical implication for you as a developer: on visionOS you design primarily for gaze-and-pinch and must respect its ergonomics (no tiny buttons, clear focus feedback). On Android XR you can't assume a single input modality, so you design for input flexibility. The AR/UX principles carry over from mobile AR — the spatial reasoning I wrote about in [spatial computing and AR on mobile](https://blog.michaelsam94.com/spatial-computing-ar-mobile/) is directly relevant — but the input abstraction is genuinely new and worth prototyping early rather than assuming.

## A taste of the code

The frameworks feel like their parent ecosystems. Android XR leans on Compose:

```kotlin
// Conceptual Jetpack XR: promote Compose content into a spatial panel
Subspace {
    SpatialPanel(
        modifier = SubspaceModifier
            .width(1024.dp)
            .height(640.dp)
            .depth(24.dp)
    ) {
        // ordinary Compose UI renders inside the spatial panel
        DashboardScreen(state = uiState)
    }
}
```

visionOS reads like SwiftUI with a RealityKit scene mixed in:

```swift
// Conceptual visionOS: a volumetric window with 3D content
struct EngineView: Scene {
    var body: some Scene {
        WindowGroup {
            RealityView { content in
                let model = try? await Entity(named: "Engine")
                if let model { content.add(model) }
            }
        }
        .windowStyle(.volumetric)
    }
}
```

Neither snippet is production-complete, but they show the ergonomics: you stay in your native UI framework and add spatial containers around it. That's the deliberate design of both SDKs — meet developers where they are.

## The pragmatic path for a cross-platform team

If you need both — and for a serious spatial product you eventually will — the realistic strategy mirrors mobile: share the logic, fork the presentation. Your domain models, networking, and business rules can live in shared code (Kotlin Multiplatform reaches Android XR naturally), while the spatial UI and interaction layer are written per platform to respect each one's input model and design language. The 3D asset pipeline is the other shared concern; Unity with OpenXR (Android XR) and PolySpatial (visionOS) is the common route for teams that want one 3D engine across both, at the cost of not using each platform's native rendering.

My honest take: don't try to write one spatial UI codebase for both today. The input paradigms differ too much for a shared abstraction to feel native on either. Share what's genuinely platform-agnostic, and treat the spatial front-end as bespoke — the same discipline that keeps cross-platform mobile apps from feeling like the lowest common denominator.

Spatial computing is early enough that the winning move for most mobile teams is to start with the platform matching your existing stack, build one genuinely spatial feature (not just a floating panel), and learn the ergonomics before betting big. Android XR and visionOS are converging on similar capabilities from opposite ecosystems, and the skills — spatial layout, comfortable input, depth-aware design — transfer between them even when the code doesn't.

## Resources

- [Android XR developer documentation](https://developer.android.com/develop/xr)
- [Jetpack XR SDK overview](https://developer.android.com/jetpack/androidx/releases/xr)
- [Apple visionOS developer documentation](https://developer.apple.com/visionos/)
- [RealityKit documentation](https://developer.apple.com/documentation/realitykit)
- [OpenXR — Khronos standard for XR](https://www.khronos.org/openxr/)
- [Unity XR development documentation](https://docs.unity3d.com/Manual/XR.html)
