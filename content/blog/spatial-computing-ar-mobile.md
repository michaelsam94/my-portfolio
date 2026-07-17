---
title: "Spatial Computing and AR on Mobile"
slug: "spatial-computing-ar-mobile"
description: "A mobile engineer's guide to spatial computing and AR: how ARCore and SLAM work, anchors and plane detection, performance realities, and where AR is worth shipping."
datePublished: "2026-07-13"
dateModified: "2026-07-17"
tags: ["AR", "Mobile", "Spatial Computing", "Android"]
keywords: "spatial computing, augmented reality, AR mobile, ARCore, mixed reality, SLAM, anchors"
faq:
  - q: "What's the difference between AR and spatial computing?"
    a: "AR overlays digital content on a camera view of the real world. Spatial computing is the broader idea of software that understands and interacts with 3D physical space — tracking, mapping, and anchoring content persistently. AR is one expression of spatial computing; headsets and robotics are others."
  - q: "How does a phone know where it is in a room for AR?"
    a: "Through SLAM — Simultaneous Localization and Mapping. The device fuses camera images with IMU (gyroscope and accelerometer) data to track its own motion and build a sparse map of feature points in the environment, so virtual content stays fixed relative to the real world as you move."
  - q: "Is mobile AR worth building, or should I wait for headsets?"
    a: "Mobile AR is worth building today for specific use cases — measurement, product visualization, navigation, and training — because billions of capable phones already exist. Headsets are the richer platform long-term, but the phone in someone's pocket is the AR device with actual reach right now."
faqAnswers:
  - question: "When is spatial computing ar mobile the wrong approach?"
    answer: "When a simpler control already covers the risk, or when the operational cost exceeds the benefit for your threat and traffic model."
  - question: "What should we measure for spatial computing ar mobile?"
    answer: "Pair a leading operational signal with a lagging user or risk outcome, reviewed on a fixed cadence with a named owner."
  - question: "How do we roll back spatial computing ar mobile safely?"
    answer: "Keep the prior artifact or config warm, rehearse the revert once in staging, and document the one-command rollback for on-call."
---
Spatial computing is software that understands and acts in three-dimensional physical space, and on mobile the everyday face of it is augmented reality — digital content anchored convincingly to the real world through a phone's camera. The magic that makes a virtual object sit on your actual table and stay there as you walk around it isn't rendering; it's the device figuring out, in real time, where it is in the room. Understand that and mobile AR stops being mysterious and becomes a tractable engineering problem with well-known trade-offs.

I come at this from the mobile side — a decade of Android and cross-platform work — and the useful truth is that AR reuses a lot of what real-time systems engineers already know: sensor fusion, clock discipline, tight frame budgets, and honest performance thinking. The framework does the hard math, but the failure modes are the ordinary ones of running heavy work at 60 frames per second on a battery-powered device.

## SLAM: how the phone knows where it is

The foundation of mobile AR is **SLAM — Simultaneous Localization and Mapping.** The device tracks its own position (localization) while building a map of the environment (mapping), and it does both at once from a phone's camera and IMU. Camera frames provide visual feature points; the gyroscope and accelerometer provide fast motion data. Fusing them gives a robust pose estimate that neither sensor could produce alone — the camera is accurate but slow and confused by motion blur, the IMU is fast but drifts.

That fusion is exactly the [sensor-fusion and clock-sync problem](https://blog.michaelsam94.com/sensor-fusion-clock-sync-real-time/) I've written about: camera and IMU readings must be aligned in time before they're combined, or tracking jitters. ARCore and ARKit handle this internally, but knowing it's happening explains the failure modes — poor tracking in low texture (no visual features), fast motion (blur plus IMU drift), and low light. When AR "loses tracking," it's SLAM failing to match features, not a rendering bug.

## The building blocks you actually work with

As a developer using [ARCore](https://developers.google.com/ar) or ARKit, you don't touch SLAM directly. You work with a small set of higher-level primitives:

| Concept | What it gives you |
| --- | --- |
| Motion tracking | The device's pose in the world, per frame |
| Plane detection | Detected horizontal/vertical surfaces (floors, tables, walls) |
| Anchors | A fixed point in the world that content attaches to |
| Hit testing | Ray from a screen tap into the 3D world to place objects |
| Light estimation | Ambient light so virtual objects match the scene |
| Depth | Per-pixel depth for occlusion (real objects hiding virtual) |

**Anchors are the concept to internalize.** An anchor is a promise from the framework to keep a world position stable as its map improves. You attach content to an anchor, not to raw coordinates, because the underlying map is constantly being refined and raw coordinates drift. Placing an object is: hit-test a tap onto a detected plane, create an anchor there, attach your renderable.

```kotlin
// ARCore: place content where the user tapped a detected plane
override fun onTap(hitResult: HitResult) {
    val trackable = hitResult.trackable
    if (trackable is Plane && trackable.isPoseInPolygon(hitResult.hitPose)) {
        val anchor = hitResult.createAnchor()
        renderableManager.attach(model, anchor) // content follows the anchor
    }
}
```

Depth and occlusion are what sell the illusion — when a real chair correctly hides part of a virtual object behind it, the brain accepts it as present. Modern devices provide a depth map (from time-of-flight sensors or depth-from-motion) that makes this possible without dedicated hardware on many phones.

## Performance is the whole game

AR runs a camera at high frame rate, SLAM tracking, 3D rendering, and often ML models simultaneously — on a phone that gets hot and drains fast. The performance discipline is the strictest in mobile:

- **Frame budget is brutal.** At 60 fps you have ~16 ms per frame for tracking *and* rendering *and* your app logic. Overrun it and the whole experience judders, breaking presence.
- **Thermal throttling is real.** Sustained AR heats the device; after a few minutes the SoC throttles and frame rate drops. Test long sessions, not 30-second demos.
- **Battery drain is heavy.** Camera plus GPU plus sensors is among the most power-hungry things a phone does.

These are the same jank-and-startup concerns that dominate any serious Android app — the techniques in [killing ANRs and jank](https://blog.michaelsam94.com/killing-anrs-android-jank/) apply directly, just with a tighter budget and higher stakes because dropped frames in AR feel like the world glitching rather than a slow scroll.

## Where mobile AR is worth shipping

AR is over-applied to novelty and under-applied to utility. The use cases that earn their keep on mobile today:

- **Measurement and space planning** — measuring a room, previewing furniture in place. The value is obvious and the tech is mature.
- **Product visualization** — see the product at true scale in your space before buying. This measurably reduces returns in retail.
- **Navigation** — directional overlays in complex indoor spaces.
- **Training and field service** — overlay instructions on real equipment, guiding a technician through a repair step by step.

What ties the winners together: AR provides *spatial context that a flat screen can't*, and the interaction is short and purposeful. The losers are long AR sessions (thermal and fatigue kill them) and gimmicks where a normal UI would work better.

## The headset question

Spatial computing's richer future is on headsets, and Android is building toward it with [Android XR](https://developer.android.com/develop/xr). But the phone is the AR device with reach *now* — billions of capable devices already in pockets, no new hardware to buy. For a mobile team, the pragmatic move is to build AR where it genuinely helps on phones today, using skills that transfer directly to headsets later, since ARCore concepts (anchors, planes, SLAM, depth) carry forward. If you're weighing an AR feature and want a candid read on whether it's worth it, [get in touch](https://michaelsam94.com/) — the honest answer is sometimes no, and knowing which cases are which saves a lot of wasted effort.

Mobile AR isn't magic; it's SLAM, sensor fusion, and a merciless frame budget, wrapped in a framework that hides the math. Treat it as the demanding real-time system it is, and it becomes a genuinely useful tool rather than a demo that impresses once and drains your battery.

## Session lifecycle UX

Pause ARKit session on `visibilitychange` hidden — continuous plane detection drained 18% battery in 12-minute furniture preview session. WebXR unsupported: show static 3D model with orbit controls instead of blank error. Lock lighting estimate after first good frame — flickering shadows on virtual product read as cheap render.

## Session lifecycle UX

Pause ARKit session on `visibilitychange` hidden — continuous plane detection drained 18% battery in 12-minute furniture preview session. WebXR unsupported: show static 3D model with orbit controls instead of blank error. Lock lighting estimate after first good frame — flickering shadows on virtual product read as cheap render.

## Resources

- [Google ARCore developer documentation](https://developers.google.com/ar)
- [Android XR — developer site](https://developer.android.com/develop/xr)
- [Apple ARKit documentation](https://developer.apple.com/augmented-reality/arkit/)
- [ARCore Depth API](https://developers.google.com/ar/develop/depth)
- [WebXR Device API (W3C)](https://www.w3.org/TR/webxr/)
- [OpenXR — cross-platform XR standard (Khronos)](https://www.khronos.org/openxr/)

## An operator's checklist for spatial computing ar mobile

Operating spatial computing ar mobile well means tying design choices to measurable outcomes and explicit owners. Ambiguous ownership is how pages rot.

For spatial computing ar mobile:
- Write the SLO and the user journey it protects
- Automate the boring verification; reserve humans for judgment calls
- Prefer progressive delivery with fast rollback over big-bang cuts
- Keep runbooks next to the code that can break

Revisit the design when the metric that justified spatial computing ar mobile stops moving — sunsetting is a feature.

| Signal | Target | Alarm |
|--------|--------|-------|
| Crawl / index ratio | Team-defined SLO | Page on burn rate |
| Rich result valid % | Baseline − noise | Ticket if sustained |
| Organic landing LCP | Budget cap | Weekly review |

## Ownership and on-call for spatial computing ar mobile

Reviewers should challenge assumptions encoded in spatial computing ar mobile: defaults copied from tutorials, timeouts that exceed upstream SLAs, and authz checks applied only on the primary UI path. Require a short threat or failure note in the PR when the change touches a trust boundary.

Concrete probes:
1. Scenario C for spatial computing ar mobile: traffic 3× baseline — prove autoscaling or shedding keeps the golden journey healthy.
2. Scenario A for spatial computing ar mobile: partial dependency outage — prove clients degrade gracefully and retries do not amplify load.
3. Scenario B for spatial computing ar mobile: bad config shipped — prove rollback within the declared RTO without data corruption.

## Post-incident changes after spatial computing ar mobile failures

Roll out spatial computing ar mobile behind a flag or weighted route when possible. Start with internal users or a low-risk geography. Watch the signals in the table for at least one full business cycle before calling the migration done. Keep the previous path warm until error budgets stabilize.

Document the owner, the dashboard, and the single command that reverts the change. If that sentence is hard to write, the design is not ready for production traffic.

## Developer experience when changing spatial computing ar mobile

Detail 1 (394): for spatial computing ar mobile, define the contract between producers and consumers explicitly — payload shape, timeout, and idempotency key. When developer experience when changing spatial computing ar mobile becomes painful, it is usually because that contract was implicit.

I keep a short matrix: who can break spatial computing ar mobile, how we detect it within five minutes, and who is paged. Update the matrix when ownership moves. Add one synthetic check that exercises the failure path, not only the happy path. Prefer checks that run continuously over quarterly manual reviews that everyone skips under deadline pressure.

If you only remember one thing about spatial computing ar mobile: optimize for reversible decisions. Reversibility beats cleverness when the incident channel is busy and the blast radius is unclear.

## Observability cardinality around spatial computing ar mobile

Detail 2 (22): for spatial computing ar mobile, define the contract between producers and consumers explicitly — payload shape, timeout, and idempotency key. When observability cardinality around spatial computing ar mobile becomes painful, it is usually because that contract was implicit.

I keep a short matrix: who can break spatial computing ar mobile, how we detect it within five minutes, and who is paged. Update the matrix when ownership moves. Add one synthetic check that exercises the failure path, not only the happy path. Prefer checks that run continuously over quarterly manual reviews that everyone skips under deadline pressure.

If you only remember one thing about spatial computing ar mobile: optimize for reversible decisions. Reversibility beats cleverness when the incident channel is busy and the blast radius is unclear.