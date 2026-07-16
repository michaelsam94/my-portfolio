---
title: "Bluetooth Low Energy on Android, Sanely"
slug: "android-ble-bluetooth-low-energy"
description: "A survival guide to Bluetooth Low Energy on Android: the new permission model, scanning without draining battery, the GATT connection lifecycle, and OEM quirks."
datePublished: "2024-07-25"
dateModified: "2024-07-25"
tags: ["Android", "Kotlin", "Bluetooth", "IoT"]
keywords: "Bluetooth Low Energy Android, BLE Android, GATT, BLE scanning, BLUETOOTH_SCAN permission, BLE connection"
faq:
  - q: "What Bluetooth permissions do I need on Android 12+?"
    a: "Android 12 (API 31) split Bluetooth into BLUETOOTH_SCAN, BLUETOOTH_CONNECT, and BLUETOOTH_ADVERTISE runtime permissions. If your scan never derives location you can declare BLUETOOTH_SCAN with usesPermissionFlags=neverForLocation to avoid needing location permission; otherwise scanning still requires location access. On Android 11 and below you needed ACCESS_FINE_LOCATION for scanning, which surprises many developers."
  - q: "Why is my BLE scan not finding devices?"
    a: "The most common causes are missing runtime permissions, location services being turned off (required for scanning on many versions), or an overly restrictive scan filter. Also, aggressive scan modes are throttled by the system if you start and stop scans too frequently — Android limits scans to about five starts in 30 seconds. Check permissions, ensure location is enabled, and verify your filters and scan mode."
  - q: "Why do BLE connections fail with status 133 on Android?"
    a: "GATT error 133 is a generic connection failure and is notoriously common on Android, often caused by connecting from a non-main thread, connecting too quickly after a scan, or OEM stack quirks. The reliable workarounds are to call connectGatt with autoConnect handling tuned per case, add small retry-with-backoff logic, always close the BluetoothGatt on failure, and connect from the main thread on problematic devices."
---

Bluetooth Low Energy on Android is one of those APIs where the documentation makes it look simple and reality makes it hurt. The core flow — scan, connect, discover services, read/write/subscribe to characteristics — is straightforward. What isn't straightforward: the permission model changed in Android 12, scanning is a battery and throttling minefield, the connection lifecycle is unforgiving, and OEM Bluetooth stacks disagree with each other and with the spec. I've shipped BLE against custom hardware, and this is the survival guide I wish I'd had.

## Permissions: the thing that changed

Android 12 (API 31) split the old monolithic Bluetooth permission into three runtime permissions:

- **`BLUETOOTH_SCAN`** — to discover devices.
- **`BLUETOOTH_CONNECT`** — to connect and exchange data.
- **`BLUETOOTH_ADVERTISE`** — to advertise as a peripheral.

The critical detail: on Android 11 and below, *scanning required `ACCESS_FINE_LOCATION`*, because BLE beacons can infer location. On Android 12+, if your scan genuinely doesn't derive location, you declare:

```xml
<uses-permission android:name="android.permission.BLUETOOTH_SCAN"
    android:usesPermissionFlags="neverForLocation" />
<uses-permission android:name="android.permission.BLUETOOTH_CONNECT" />
```

That `neverForLocation` flag lets you scan without asking for location — a big UX win. But if you *do* use BLE for positioning (beacons), you still need location. And you still request `BLUETOOTH_SCAN`/`BLUETOOTH_CONNECT` as runtime permissions. Getting this wrong is the number-one "my scan returns nothing" cause.

## Scanning without killing the battery

A scan is a radio running continuously — the fastest way to drain a battery and get your app throttled. Discipline:

1. **Filter in the system, not in your callback.** Pass `ScanFilter`s for the service UUID you care about so the OS wakes you only for relevant devices. Scanning unfiltered and filtering in code wastes power and CPU.
2. **Pick the right scan mode.** `SCAN_MODE_LOW_POWER` for background discovery, `SCAN_MODE_LOW_LATENCY` only while a UI is open and the user is actively pairing. Never leave low-latency running.
3. **Stop when you've found it.** Don't scan indefinitely. Stop the scan the moment you have the device, then connect.
4. **Respect the throttle.** Android limits you to roughly five scan starts in 30 seconds; hammering start/stop gets your scans silently ignored.

```kotlin
val filters = listOf(
    ScanFilter.Builder().setServiceUuid(ParcelUuid(MY_SERVICE_UUID)).build()
)
val settings = ScanSettings.Builder()
    .setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY)
    .build()
scanner.startScan(filters, settings, scanCallback)
```

## The GATT lifecycle is a state machine you must respect

Once connected you get a `BluetoothGatt`, and everything after is asynchronous and *strictly sequential*. The GATT stack processes one operation at a time — issue a read while a write is in flight and you get silent failures or corruption. So you must queue operations:

```
connectGatt()  -> onConnectionStateChange(CONNECTED)
discoverServices() -> onServicesDiscovered()
readCharacteristic() -> onCharacteristicRead()
writeCharacteristic() -> onCharacteristicWrite()
setCharacteristicNotification() + write CCCD descriptor -> onDescriptorWrite()
```

The rule I enforce: maintain an explicit operation queue and only dispatch the next operation after the previous one's callback fires. Nearly every "flaky BLE" bug I've fixed was two operations issued without waiting for the first to complete.

To actually receive notifications, you must both call `setCharacteristicNotification(...)` *and* write the Client Characteristic Configuration Descriptor (CCCD, UUID `00002902-...`). People forget the descriptor write constantly and then wonder why notifications never arrive.

## Status 133 and the OEM tax

If you do BLE on Android long enough you will meet GATT error `133` — a generic connection failure with no useful detail. It correlates with:

- Connecting too soon after a scan (stop the scan, then connect).
- Calling GATT operations off the main thread on some stacks.
- Not closing a previous `BluetoothGatt` before reconnecting.

The defensive recipe that made my connections reliable:

- Always `gatt.close()` on disconnect or failure — leaked GATT clients poison future connections.
- Add retry-with-backoff around connect (2–3 attempts) since 133 is often transient.
- Serialize connect attempts; don't connect to multiple devices simultaneously unless you must.
- Test on Samsung, Xiaomi, and a Pixel — their stacks behave differently, and "works on my Pixel" means nothing for the fleet.

BLE is one of those [IoT-adjacent Android surfaces](https://blog.michaelsam94.com/android-ble-bluetooth-low-energy/) where the device diversity, not the API, is the hard part.

## MTU and throughput

Default BLE payloads are tiny (~20 bytes usable). If you move real data, request a larger MTU right after connecting (`requestMtu(517)`) and wait for `onMtuChanged` before sizing your writes. And for bulk transfer use write-without-response with careful flow control — but know that throughput varies wildly across devices, so never assume a data rate; measure it on target hardware.

## What I'd take away

BLE on Android is manageable if you respect four things. Get the Android 12+ permission model right — `BLUETOOTH_SCAN` with `neverForLocation` when you can, and remember older versions need location. Scan with system-side filters, the right mode, and a hard stop, staying under the throttle. Treat GATT as a strictly sequential state machine with an explicit operation queue, and never forget the CCCD descriptor write for notifications. And build in the defenses for status 133 and OEM quirks: always close the GATT, retry with backoff, and test across manufacturers. Do that and BLE goes from maddening to merely tedious — which, for Bluetooth, is a win.

Test BLE reconnection after Android 12+ background location restrictions — scan failures in production often trace to permission prompts users dismissed once.

## Resources

- [Bluetooth Low Energy overview (Android)](https://developer.android.com/develop/connectivity/bluetooth/ble/ble-overview)
- [Bluetooth permissions](https://developer.android.com/develop/connectivity/bluetooth/bt-permissions)
- [Find BLE devices](https://developer.android.com/develop/connectivity/bluetooth/ble/find-ble-devices)
- [Connect to a GATT server](https://developer.android.com/develop/connectivity/bluetooth/ble/connect-gatt-server)
- [Bluetooth Core Specification (Bluetooth SIG)](https://www.bluetooth.com/specifications/specs/core-specification/)
