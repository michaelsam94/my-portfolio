---
title: "The Photo Picker and Granular Media Permissions"
slug: "android-photo-picker-media-permissions"
description: "How the Android photo picker and granular media permissions work: selected photos access, READ_MEDIA scopes, and why most apps should stop requesting storage."
datePublished: "2026-03-14"
dateModified: "2026-03-14"
tags: ["Android", "Privacy", "UX"]
keywords: "Android photo picker, selected photos access, granular media permissions, READ_MEDIA, privacy media Android"
faq:
  - q: "What is the Android photo picker?"
    a: "The Android photo picker is a system UI that lets users choose specific photos and videos to share with your app without granting any storage permission at all. Your app launches it, the user picks items, and you receive access only to those items via secure URIs. Because the picker runs outside your process and returns nothing beyond the chosen media, it's both more private and less code than building your own gallery."
  - q: "What's the difference between the photo picker and READ_MEDIA permissions?"
    a: "The photo picker needs no permission and returns only user-selected items — ideal when you just need the user to attach a few photos. READ_MEDIA_IMAGES and READ_MEDIA_VIDEO are runtime permissions that grant broad, ongoing access to the user's whole media library, which you only need if your app must enumerate or continuously index media, like a gallery or backup app."
  - q: "What is 'selected photos access' on Android?"
    a: "Selected photos access is the partial-grant option shown when an app requests media permission on newer Android versions. Instead of all-or-nothing, the user can grant access to only a subset of photos. Your app then sees just those items, and the user can re-open the selection later. It's the middle ground between the picker and full library access."
---

Ask for the whole photo library when you only need one selfie, and you've told the user something about how your app thinks about their data. For years the default was exactly that overreach: request `READ_EXTERNAL_STORAGE`, get the entire gallery, and build a custom grid to show it. The Android photo picker kills that pattern. It's a system-provided, permission-free UI that returns only the specific images and videos the user chose — and for the majority of apps, it's the right answer.

I keep running into codebases that still request broad storage permissions out of habit, then wonder why their permission-grant rates are mediocre and their Play Console flags a data-safety mismatch. Let me lay out the three tiers of media access, when each is appropriate, and why the picker should be your default.

## Three tiers, from least to most access

Think of media access as a ladder. Climb only as high as you actually need:

1. **Photo picker — zero permissions.** Launch the system picker, user selects items, you get URIs to exactly those. No manifest permission, no runtime dialog. This covers "attach a photo to a message," "set a profile picture," "upload a receipt."
2. **Selected photos access — partial grant.** When you *do* request `READ_MEDIA_IMAGES`/`READ_MEDIA_VIDEO`, newer Android versions offer the user a "Select photos" option that grants access to a chosen subset rather than the whole library.
3. **Full media access — broad runtime permission.** The user grants your app ongoing access to all photos or all videos. Reserve this for apps whose core function is the media library itself.

The trap I keep seeing is teams jumping straight to tier three because it's the pattern they already know. That's backwards. Start at tier one and only climb when a concrete feature forces you to.

## Using the photo picker

The picker is exposed through Activity Result contracts, so there's genuinely little code. Single or multiple selection, with an optional media-type filter:

```kotlin
val pickMedia = registerForActivityResult(
    ActivityResultContracts.PickVisualMedia()
) { uri: Uri? ->
    if (uri != null) {
        // Persisted, read-only access to this single item — no permission granted
        imageView.setImageURI(uri)
    }
}

// Launch it, images only
pickMedia.launch(
    PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly)
)
```

For multiple items, swap in `PickMultipleVisualMedia(maxItems)`. On devices where a fully featured picker isn't present, adding the `PhotoPickerGoogleExtras`-style dependency backports a consistent experience, so you don't have to branch on OS version in your UI logic.

What you get back is a URI scoped to that item, valid for reading, with no lingering permission. When the user closes your app, that access is gone. That's the privacy property that makes the picker so clean: there's simply no broad grant to misuse, leak, or forget to revoke — the same "collect only what you need" principle I argue for in [privacy engineering for mobile and GDPR](https://blog.michaelsam94.com/privacy-engineering-mobile-gdpr/).

## When you genuinely need the permission

Some apps really do need to enumerate media — a gallery, an editor that shows recents, a backup tool. For those, request the granular permissions, and understand what the user can grant:

```kotlin
val requestPerms = registerForActivityResult(
    ActivityResultContracts.RequestMultiplePermissions()
) { grants ->
    val full = grants[Manifest.permission.READ_MEDIA_IMAGES] == true
    // On newer Android, the user may grant only selected items instead of full access
    val partial = grants[Manifest.permission.READ_MEDIA_VISUAL_USER_SELECTED] == true
    when {
        full -> loadEntireLibrary()
        partial -> loadOnlyGrantedSelection()
        else -> showPickerFallback()
    }
}
```

Two things to internalize. First, `READ_MEDIA_IMAGES` and `READ_MEDIA_VIDEO` are **separate** — the old single storage permission is gone, so request only the media type you use. Second, the partial grant (`READ_MEDIA_VISUAL_USER_SELECTED`) is now a first-class outcome. Your app must handle "the user gave me twelve photos, not all of them" as a normal state, including a path to let them re-open the selection and add more.

## The decision, in one table

| Need | Use | Permission | User sees |
| --- | --- | --- | --- |
| Attach a few photos | Photo picker | None | System picker, one tap |
| Set profile picture | Photo picker | None | System picker |
| Show recents / edit library | Selected access | READ_MEDIA_* | Grant dialog with "Select photos" |
| Full gallery / backup app | Full media access | READ_MEDIA_* | All-or-selected dialog |

If a row in your app doesn't clearly map to the bottom two, you belong on the picker. I've migrated features from custom galleries to the picker and consistently deleted more code than I wrote, while the data-safety story got simpler to defend.

## Why this is more than a checkbox

There's a real product angle here beyond compliance. Permission dialogs are friction and, increasingly, a trust signal — users notice when an app asks for their whole photo library to send one image. Every prompt you *don't* show is a conversion you don't lose. The picker gets you the media with zero prompts, which is both the private option and, conveniently, the higher-converting one.

It also fits the broader direction of the platform. Between the media changes here and the ad-stack rework I cover in the [Android Privacy Sandbox](https://blog.michaelsam94.com/android-privacy-sandbox/), the trend is unmistakable: broad, device-wide, ongoing grants are being replaced by narrow, purpose-scoped, user-mediated ones. Designing for that now — assume you'll get partial or transient access, never the whole store — means you won't be rewriting these flows every time the permission model tightens another notch.

My rule of thumb after a few of these migrations: if a product manager can't name the specific feature that needs full library enumeration, the answer is the photo picker. Default to the least access that ships the feature, treat partial grants as the normal case, and reserve broad media permissions for the handful of apps that are, genuinely, about the media library itself.

## Resources

- [Android photo picker documentation](https://developer.android.com/training/data-storage/shared/photopicker)
- [Request runtime permissions](https://developer.android.com/training/permissions/requesting)
- [Granular media permissions (Android 13+)](https://developer.android.com/about/versions/13/behavior-changes-13#granular-media-permissions)
- [Selected photos access (Android 14+)](https://developer.android.com/about/versions/14/changes/partial-photo-video-access)
- [Activity Result APIs](https://developer.android.com/training/basics/intents/result)
