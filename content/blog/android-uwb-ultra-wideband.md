---
title: "Ultra-Wideband Ranging on Android"
slug: "android-uwb-ultra-wideband"
description: "How Ultra-Wideband (UWB) ranging works on Android: the Jetpack UWB API, controller vs controllee roles, distance and angle measurements, and realistic use cases."
datePublished: "2024-07-28"
dateModified: "2024-07-28"
tags: ["Android", "Kotlin", "UWB", "IoT"]
keywords: "Ultra-Wideband Android, UWB ranging, Jetpack UWB, androidx.core.uwb, UWB controller controlee"
faq:
  - q: "What can Ultra-Wideband do that Bluetooth cannot?"
    a: "UWB measures distance between two devices with centimeter-level accuracy and, on capable hardware, the angle of arrival — precise spatial awareness that Bluetooth RSSI can only crudely approximate. This enables features like precise device finding, secure proximity unlocking that resists relay attacks, and spatially aware interactions, none of which Bluetooth signal strength can do reliably."
  - q: "Which Android devices support UWB?"
    a: "UWB requires dedicated hardware, so it's limited to specific higher-end phones that ship a UWB chip — not the general Android fleet. Always check availability at runtime through the UWB manager rather than assuming support, and design your feature to degrade gracefully to BLE or another fallback when UWB isn't present."
  - q: "What are the controller and controllee roles in UWB ranging?"
    a: "A UWB ranging session has two roles: the controller initiates and manages the session parameters, and the controllee (sometimes spelled controlee) joins with matching parameters. Both devices exchange configuration out-of-band first — typically over BLE — then start ranging. The roles determine who drives the session setup, but both receive distance measurements."
---

Ultra-Wideband is the technology behind "point your phone at the thing to find it." UWB measures the distance between two devices with centimeter-level precision and, on capable hardware, the *angle* they're at relative to each other — spatial awareness that Bluetooth's signal-strength guessing can't touch. Jetpack's `androidx.core.uwb` library brings this to Android, and while the hardware is still limited to specific phones, the API is clean enough to build against today. I'll walk through how ranging actually works and where it earns its place over cheaper radios.

## What UWB measures, and why it's special

UWB works by timing radio pulses across a very wide frequency band. Because it measures *time of flight* directly rather than inferring distance from signal strength, it gets:

- **Distance** accurate to roughly ten centimeters, stable even with obstacles and reflections that wreck RSSI-based estimates.
- **Angle of arrival** (azimuth, and on some hardware elevation), so a device knows not just *how far* but *which direction* a peer is.

That precision unlocks things Bluetooth fundamentally can't do safely: proximity unlocking that resists relay attacks (you can't spoof time-of-flight the way you can boost a signal), precise item finding with directional guidance, and spatially aware handoffs. If your feature only needs "roughly nearby," [BLE](https://blog.michaelsam94.com/android-ble-bluetooth-low-energy/) is cheaper and more widely supported. If it needs *precise* nearby, UWB is the tool.

## Check for hardware first — always

UWB is not on the general fleet; only specific higher-end phones ship the chip. So the very first thing any UWB code does is check availability at runtime and plan a fallback:

```kotlin
val uwbManager = UwbManager.createInstance(context)
val isAvailable = uwbManager.isAvailable()   // gate everything on this
```

Never assume support. Design the feature so it degrades — to BLE proximity, to a map, to manual entry — when UWB is absent, or you've built something that works for a sliver of your users.

## The roles: controller and controllee

A ranging session has two roles. The **controller** initiates and owns the session parameters; the **controllee** joins with matching parameters. Both sides receive distance measurements — the role is about who drives setup, not who gets data.

Crucially, the two devices must agree on session parameters (a session ID, channel, and complex addresses) *before* ranging starts, and UWB itself doesn't do that discovery. You exchange those parameters **out-of-band**, almost always over BLE. So a real UWB feature is actually a two-radio dance: BLE to find each other and swap config, then UWB to range precisely.

## Setting up a session

The controller creates a session and shares its parameters:

```kotlin
val sessionScope = uwbManager.controllerSessionScope()

val myAddress = sessionScope.localAddress          // send this to the peer via BLE
val myChannel = sessionScope.uwbComplexChannel     // send this too

val partnerParams = RangingParameters(
    uwbConfigType = RangingParameters.CONFIG_UNICAST_DS_TWR,
    sessionId = agreedSessionId,
    subSessionId = 0,
    sessionKeyInfo = agreedKey,
    subSessionKeyInfo = null,
    complexChannel = myChannel,
    peerDevices = listOf(UwbDevice.createForAddress(peerAddress)),
    updateRateType = RangingParameters.RANGING_UPDATE_RATE_AUTOMATIC
)
```

The controllee builds a mirror-image session with `controleeSessionScope()` and the parameters it received over BLE. The `sessionKeyInfo` is a shared secret that authenticates the session — this is part of what makes UWB resistant to relay attacks. Get the parameter exchange right and ranging just works; get it subtly wrong and the session silently never produces measurements.

## Collecting measurements

Once both sides start, you collect a flow of ranging results:

```kotlin
sessionScope.prepareSession(partnerParams)
    .collect { result ->
        when (result) {
            is RangingResult.RangingResultPosition -> {
                val distance = result.position.distance?.value      // meters
                val azimuth = result.position.azimuth?.value        // degrees
                val elevation = result.position.elevation?.value
                updateArrow(distance, azimuth)
            }
            is RangingResult.RangingResultPeerDisconnected -> onLost()
        }
    }
```

Distance comes on nearly every device; azimuth and elevation depend on antenna hardware, so treat them as optional. Measurements update several times a second — smooth them for UI (a moving average) rather than binding a directional arrow directly to raw, jittery readings.

## Where UWB actually pays off

Realistic use cases from what the hardware is good at:

1. **Precise finding.** "Your keys are 2m to your left" with a directional arrow — the flagship UWB demo, and genuinely useful.
2. **Secure proximity actions.** Unlock a door or a car only when the phone is verifiably *right here*, not merely reachable by a relayed Bluetooth signal.
3. **Spatial handoff.** Transfer content by pointing one device at another.
4. **Presence with distance.** Trigger actions based on how close, not just whether, a device is near.

The common thread: features that need trustworthy *physical* distance. Anything that tolerates fuzzy proximity doesn't justify UWB's hardware limits.

## What I'd take away

UWB gives you centimeter-accurate, direction-aware, relay-resistant ranging — a genuinely new capability, not a faster Bluetooth. Build every UWB feature behind a runtime availability check with a graceful fallback, because the hardware is limited to specific phones. Understand that it's a two-radio pattern: BLE (or another channel) to discover peers and exchange session parameters out-of-band, then UWB for the precise ranging. Set up matching controller/controllee sessions with a shared key, collect and smooth the distance/angle flow, and reserve UWB for features that genuinely need trustworthy physical distance. Used where it fits, it enables experiences no other radio on the phone can deliver.

UWB ranging requires line-of-sight calibration per device model — lab accuracy numbers don't transfer to real-world multipath environments.

## Resources

- [Ultra-wideband (UWB) communication (Android)](https://developer.android.com/develop/connectivity/uwb)
- [Jetpack UWB library releases](https://developer.android.com/jetpack/androidx/releases/core-uwb)
- [FiRa Consortium (UWB standards)](https://www.firaconsortium.org/)
- [androidx.core.uwb reference](https://developer.android.com/reference/androidx/core/uwb/package-summary)
- [Bluetooth Low Energy overview](https://developer.android.com/develop/connectivity/bluetooth/ble/ble-overview)
