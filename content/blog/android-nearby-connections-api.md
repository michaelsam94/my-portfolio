---
title: "Peer-to-Peer with the Nearby Connections API"
slug: "android-nearby-connections-api"
description: "Build offline peer-to-peer features with Android's Nearby Connections API: strategies, advertising and discovery, the connection handshake, and payload types explained."
datePublished: "2024-07-26"
dateModified: "2024-07-26"
tags: ["Android", "Kotlin", "Nearby", "Connectivity"]
keywords: "Nearby Connections API, Android peer to peer, offline data transfer Android, Nearby strategy, payload transfer Android"
faq:
  - q: "Does the Nearby Connections API need internet?"
    a: "No. Nearby Connections works fully offline by combining Bluetooth, BLE, and Wi-Fi under the hood, negotiating the best available radio automatically. This makes it ideal for local multiplayer, file sharing, and data sync between devices in the same room with no network, no account, and no server."
  - q: "What is the difference between the Nearby Connections strategies?"
    a: "P2P_STAR allows one advertiser to connect to many discoverers (a hub-and-spoke topology) and is good for one-to-many broadcasts. P2P_CLUSTER allows an M-to-N mesh where any device can connect to many others, useful for group scenarios. P2P_POINT_TO_POINT restricts to a single high-bandwidth connection between two devices, best for large transfers between exactly two peers."
  - q: "What payload types does Nearby Connections support?"
    a: "Three: BYTES for small in-memory messages up to a size limit, FILE for large files transferred efficiently from disk, and STREAM for continuous data like audio piped through an InputStream. Use BYTES for control messages and small data, FILE for anything large, and STREAM for live continuous feeds."
---

The Nearby Connections API is Android's answer to "let two phones in the same room talk directly, without internet, an account, or a server." It quietly combines Bluetooth, BLE, and Wi-Fi, negotiates the fastest available radio, and gives you a clean advertise/discover/connect/send flow. I've used it for a local device-to-device data transfer feature, and it's genuinely delightful once you understand the two decisions that shape everything: which *strategy* you pick and which *payload type* you send.

## Why it's different from raw Bluetooth

You could build peer-to-peer on [raw BLE](https://blog.michaelsam94.com/android-ble-bluetooth-low-energy/), but you'd hand-manage radio selection, throughput, and reconnection. Nearby Connections abstracts all of that: it starts on a low-power radio for discovery, then upgrades to Wi-Fi for bandwidth once connected, transparently. You get encryption on the connection for free and a single API regardless of the underlying transport. The trade-off is less control and a dependency on Google Play Services — fine for most consumer apps, a dealbreaker for devices without GMS.

## Pick a strategy — it defines your topology

The `Strategy` you choose determines what connection shapes are legal, and you can't easily change it later:

| Strategy | Topology | Use for |
|---|---|---|
| `P2P_STAR` | One advertiser, many discoverers | Broadcast / hub, one-to-many |
| `P2P_CLUSTER` | M-to-N mesh | Group chat, multiplayer lobbies |
| `P2P_POINT_TO_POINT` | Exactly two devices, high bandwidth | Big file transfer between two peers |

For a two-device file transfer I use `P2P_POINT_TO_POINT` because it prioritizes throughput. For a "one host shares with the room" pattern, `P2P_STAR`. Choose based on the shape of your feature, not the size of the data.

## Advertise and discover

One side advertises, the other discovers. In many apps a device does both so either party can initiate:

```kotlin
val options = AdvertisingOptions.Builder().setStrategy(Strategy.P2P_POINT_TO_POINT).build()

Nearby.getConnectionsClient(context)
    .startAdvertising(userName, SERVICE_ID, connectionLifecycleCallback, options)

val discoveryOptions = DiscoveryOptions.Builder().setStrategy(Strategy.P2P_POINT_TO_POINT).build()

Nearby.getConnectionsClient(context)
    .startDiscovery(SERVICE_ID, endpointDiscoveryCallback, discoveryOptions)
```

`SERVICE_ID` (usually your package name) namespaces your app so it only finds *your* peers, not every Nearby-using app around. The strategy must match on both sides.

## The connection handshake

Discovery finds an endpoint; connecting is a two-sided handshake with an authentication token both users can verify — a nice built-in defense against connecting to the wrong device:

```kotlin
val endpointDiscoveryCallback = object : EndpointDiscoveryCallback() {
    override fun onEndpointFound(id: String, info: DiscoveredEndpointInfo) {
        Nearby.getConnectionsClient(context)
            .requestConnection(userName, id, connectionLifecycleCallback)
    }
    override fun onEndpointLost(id: String) { /* remove from UI */ }
}

val connectionLifecycleCallback = object : ConnectionLifecycleCallback() {
    override fun onConnectionInitiated(id: String, info: ConnectionInfo) {
        // Optionally show info.authenticationDigits so both users confirm
        Nearby.getConnectionsClient(context).acceptConnection(id, payloadCallback)
    }
    override fun onConnectionResult(id: String, result: ConnectionResolution) {
        if (result.status.isSuccess) onConnected(id)
    }
    override fun onDisconnected(id: String) { onLost(id) }
}
```

For sensitive transfers, show the `authenticationDigits` on both screens and have users confirm they match before accepting — it's the API's version of a pairing code.

## Payload types: match the data

Once connected, you send `Payload`s, and picking the right type matters for performance:

- **`Payload.fromBytes(...)`** — small in-memory messages (control signals, JSON, chat). There's a size cap; don't push files through it.
- **`Payload.fromFile(...)`** — large files, transferred efficiently straight from disk without loading into memory. This is what you want for photos, videos, documents.
- **`Payload.fromStream(...)`** — continuous data through an `InputStream`, e.g. live audio.

```kotlin
val payload = Payload.fromFile(file)
Nearby.getConnectionsClient(context).sendPayload(endpointId, payload)
```

The receiving side gets the payload in `onPayloadReceived` and progress updates in `onPayloadTransferUpdate` — wire the latter to a progress bar, because large transfers take real time and users need feedback.

## The permission and lifecycle reality

Nearby needs a cluster of permissions depending on the radios it uses — Bluetooth (scan/connect/advertise), Wi-Fi, and on some versions location — plus `NEARBY_WIFI_DEVICES` on Android 13+. Request the set upfront with a clear rationale, because a partial grant makes discovery mysteriously fail. And always stop advertising and discovery once connected (`stopAdvertising`, `stopDiscovery`) to save battery — leaving them running is a common drain. Tear down connections in your lifecycle teardown so you don't leak them.

## What I'd take away

Nearby Connections is the fastest path to offline, serverless, device-to-device features on Android. Choose your `Strategy` first because it fixes your topology — point-to-point for two-device throughput, star for one-to-many, cluster for meshes. Namespace with a `SERVICE_ID`, verify the authentication digits for sensitive connections, and match your `Payload` type to the data: bytes for control, file for large transfers, stream for continuous feeds. Wire up transfer-progress callbacks, request the full permission set upfront, and stop advertising/discovery once connected. Do that and two phones in a room can share data with no internet and no setup — which still feels a little like magic.

## Common production mistakes

Teams get nearby connections api wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Shipping nearby connections api on Android fails quietly when you test only on flagship devices, skip process-death scenarios, or assume `minSdk` behavior matches latest API docs. Emulator-only validation misses OEM-specific battery optimizations and background execution limits.

## Resources

- [Nearby Connections overview](https://developers.google.com/nearby/connections/overview)
- [Get started with Nearby Connections](https://developers.google.com/nearby/connections/android/get-started)
- [Strategies](https://developers.google.com/nearby/connections/strategies)
- [Manage connections and payloads](https://developers.google.com/nearby/connections/android/manage-connections)
- [NEARBY_WIFI_DEVICES permission](https://developer.android.com/develop/connectivity/wifi/wifi-permissions)
