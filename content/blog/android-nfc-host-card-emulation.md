---
title: "NFC Host Card Emulation on Android"
slug: "android-nfc-host-card-emulation"
description: "Implement NFC Host Card Emulation (HCE) on Android: the HostApduService, AIDs and APDU routing, the tap lifecycle, and the security limits you must design around."
datePublished: "2024-07-23"
dateModified: "2024-07-23"
tags: ["Android", "Kotlin", "NFC", "Security"]
keywords: "Host Card Emulation Android, HostApduService, NFC HCE, APDU Android, AID routing NFC"
faq:
  - q: "What is Host Card Emulation on Android?"
    a: "Host Card Emulation (HCE) lets your app emulate an NFC smart card in software, so an external reader talks to your app instead of a physical secure-element card. When a reader taps the phone and selects your registered application ID (AID), Android routes the reader's APDU commands to your HostApduService, which responds — enabling contactless features like transit, loyalty, and access cards without dedicated hardware."
  - q: "Does HCE work when the screen is off or the app is closed?"
    a: "It can. HCE routes to your HostApduService based on the registered AID, and the service can be started by the system when a matching tap occurs, even if your app isn't in the foreground. Whether it works with the screen off depends on the device and how the service is categorized (payment vs other); payment category apps generally require the device unlocked, while other categories can respond more freely."
  - q: "Is Host Card Emulation secure enough for payments?"
    a: "HCE runs in the normal application environment, not a hardware secure element, so it does not provide the same tamper resistance. Real payment systems that use HCE compensate with tokenization, short-lived keys provisioned from a server, and device attestation rather than storing durable secrets on the device. For sensitive use cases, never keep long-lived credentials in the app; use one-time tokens."
---

Host Card Emulation lets your Android app pretend to be a contactless smart card entirely in software — no secure-element hardware, no carrier deal. When a reader taps the phone and selects your registered application ID, Android routes the reader's APDU commands to your `HostApduService`, and your code answers. That's the whole magic behind app-based transit passes, building access badges, and loyalty cards. I've built an HCE access-card feature, and while the API surface is small, the protocol details and security constraints are where people get hurt.

## The mental model: you are a card

An NFC reader speaks ISO 7816-4 APDUs — application protocol data units. A physical card receives these command APDUs and returns response APDUs. HCE inserts your app into that role: the reader has no idea it's talking to software. The conversation always starts with the reader *selecting* an application by its AID (Application Identifier), and if that AID is registered to your service, Android delivers everything to you.

So implementing HCE is really two jobs: register the AIDs you answer to, and implement the APDU request/response state machine.

## Register the service and your AIDs

You declare a `HostApduService` and an APDU service XML that lists your AIDs and a category:

```xml
<!-- res/xml/apduservice.xml -->
<host-apdu-service xmlns:android="http://schemas.android.com/apk/res/android"
    android:description="@string/service_desc"
    android:requireDeviceUnlock="true">
    <aid-group android:description="@string/aid_group_desc"
        android:category="other">
        <aid-filter android:name="F0010203040506"/>
    </aid-group>
</host-apdu-service>
```

```xml
<service
    android:name=".CardService"
    android:exported="true"
    android:permission="android.permission.BIND_NFC_SERVICE">
    <intent-filter>
        <action android:name="android.nfc.cardemulation.action.HOST_APDU_SERVICE"/>
    </intent-filter>
    <meta-data android:name="android.nfc.cardemulation.host_apdu_service"
        android:resource="@xml/apduservice.xml"/>
</service>
```

Two categories exist: **`payment`** (mutually exclusive default handling, tighter rules, generally requires an unlocked device) and **`other`** (loyalty, access, transit — more flexible). Most non-payment features use `other`. The AID is the contract with the reader — it must match what the reader selects.

## Implement the APDU exchange

The service gets a callback per command APDU and returns a response APDU (raw bytes, with a status word at the end):

```kotlin
class CardService : HostApduService() {

    override fun processCommandApdu(commandApdu: ByteArray, extras: Bundle?): ByteArray {
        return when {
            isSelectAid(commandApdu) -> SW_OK            // 0x9000
            isReadRecord(commandApdu) -> buildRecord() + SW_OK
            else -> SW_INS_NOT_SUPPORTED                 // 0x6D00
        }
    }

    override fun onDeactivated(reason: Int) {
        // reason: LINK_LOSS or DESELECTED — reset your per-tap state here
        resetSession()
    }

    companion object {
        val SW_OK = byteArrayOf(0x90.toByte(), 0x00)
        val SW_INS_NOT_SUPPORTED = byteArrayOf(0x6D.toByte(), 0x00)
    }
}
```

The status word convention is ISO 7816: `0x9000` means success, and error codes like `0x6D00` (instruction not supported) or `0x6A82` (file not found) signal specific failures the reader understands. Return the *right* status word — readers make decisions based on it.

## The tap lifecycle is brutally short

A tap lasts a few hundred milliseconds and the field can drop at any instant. This shapes everything:

1. **`processCommandApdu` runs on a tight budget.** It's on a binder thread, and the reader has a timeout. Do *not* do network calls or disk I/O inline — prepare your response data before the tap or you'll miss the window. Anything slow means a failed tap.
2. **`onDeactivated` is your teardown.** The field can vanish (`LINK_LOSS`) or the reader can deselect you. Reset per-session state here so the next tap starts clean.
3. **State machines must be resilient.** A tap can be interrupted mid-exchange and retried. Don't assume the reader completes the full sequence.

The practical rule: have the answer ready before the phone touches the reader. Fetch tokens and build records ahead of time; the tap should be pure, fast byte-shuffling.

## Security: you are not a secure element

This is the part that must shape your architecture. HCE runs in the ordinary app sandbox, not tamper-resistant hardware. A rooted device can inspect your process. So:

- **Never store long-lived secrets on the device.** No durable card keys, no master credentials sitting in the APK or app storage.
- **Use tokenization.** Provision short-lived, single-use tokens from a server, the way real HCE payment systems do. A stolen token is worthless after one use or a few minutes.
- **Attest the device.** Use Play Integrity / hardware attestation before provisioning anything sensitive, so a compromised device doesn't get valid tokens.
- **Require unlock for sensitive AIDs.** `requireDeviceUnlock="true"` ensures a locked, lost phone can't be tapped to a reader and used.

Treat HCE like any [security-sensitive Android surface](https://blog.michaelsam94.com/android-nfc-host-card-emulation/): assume the client is hostile and keep the real trust on the server. Design as if the device is compromised, because eventually one will be.

## Testing without a reader lab

Two readers help enormously during development: a second NFC phone running a reader app that sends known APDUs, and a USB PC/SC reader with a scripting tool to fire crafted command sequences. Log every command/response pair (in debug builds only — never log real tokens) so you can see exactly where a reader's expectations diverge from your state machine. Most HCE bugs are protocol mismatches, and they're invisible until you can watch the raw APDU trace.

## What I'd take away

HCE turns your app into a software smart card: register your AIDs with the right category, implement a fast `processCommandApdu` that returns correct ISO 7816 status words, and reset cleanly in `onDeactivated`. Respect the brutally short tap window — have your response data ready *before* the tap, never inline network or disk work. And architect for the fact that you're not a secure element: no long-lived secrets on device, server-provisioned single-use tokens, device attestation, and unlock requirements for anything sensitive. Get the protocol right and the security model right, and HCE gives you contactless features that used to require dedicated hardware.

## Resources

- [Host-based card emulation overview (Android)](https://developer.android.com/develop/connectivity/nfc/hce)
- [NFC basics](https://developer.android.com/develop/connectivity/nfc/nfc)
- [HostApduService reference](https://developer.android.com/reference/android/nfc/cardemulation/HostApduService)
- [ISO/IEC 7816-4 (smart card APDUs)](https://www.iso.org/standard/77180.html)
- [Play Integrity API](https://developer.android.com/google/play/integrity)
