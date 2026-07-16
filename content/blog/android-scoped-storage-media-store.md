---
title: "Scoped Storage and MediaStore in 2026"
slug: "android-scoped-storage-media-store"
description: "How scoped storage and MediaStore actually work now: granular media permissions, the Photo Picker, MediaStore inserts, and why you rarely need storage permissions."
datePublished: "2024-09-19"
dateModified: "2024-09-19"
tags: ["Android", "Storage", "Security", "MediaStore"]
keywords: "scoped storage, MediaStore, Photo Picker, READ_MEDIA_IMAGES, granular media permissions, Android file access"
faq:
  - q: "Do I still need storage permissions with scoped storage?"
    a: "Usually no. To let a user pick photos or videos, use the Android Photo Picker, which needs no permission at all. To save files into shared collections you use MediaStore without a permission on modern versions. You only need READ_MEDIA_IMAGES or READ_MEDIA_VIDEO when your app must query the full media library itself, and READ_MEDIA_VISUAL_USER_SELECTED for partial access."
  - q: "What replaced READ_EXTERNAL_STORAGE on Android 13 and above?"
    a: "READ_EXTERNAL_STORAGE was split into granular media permissions: READ_MEDIA_IMAGES, READ_MEDIA_VIDEO, and READ_MEDIA_AUDIO. On Android 14 and above there is also READ_MEDIA_VISUAL_USER_SELECTED for the partial-access case where the user grants only specific photos rather than the whole library. Requesting the old permission has no effect on these versions."
  - q: "When should I use the Photo Picker versus MediaStore queries?"
    a: "Use the Photo Picker when the user is choosing specific items to import — it needs no permission, shows a trusted system UI, and returns durable URIs. Use MediaStore queries when your app genuinely needs to enumerate or manage the whole media library, such as a gallery or backup app, which requires the granular read permissions."
---

The mental shift scoped storage demands is simple: your app no longer roams a shared filesystem, it works within its own sandbox plus *mediated* access to shared media. In 2026 the practical consequences are that you rarely need a storage permission at all — the Photo Picker handles "let the user choose photos" with zero permissions, `MediaStore` handles saving into shared collections without a permission, and the granular media permissions (`READ_MEDIA_IMAGES` and friends) are reserved for apps that genuinely must enumerate the whole library. If your app still requests `READ_EXTERNAL_STORAGE`, it's living in the past, and on modern Android that request does nothing.

I've migrated a couple of media-heavy apps through this transition, and the biggest win is realizing how much you can *delete*. Let me lay out what to use when.

## The default answer: Photo Picker, no permission

If all you need is for the user to pick some images or videos to import — a profile photo, attachments, a post — the answer is the Android Photo Picker. It's a system UI, so the user trusts it, it needs **no permission whatsoever**, and it returns durable URIs you can read.

```kotlin
val pickMedia = registerForActivityResult(
    ActivityResultContracts.PickVisualMedia()
) { uri ->
    if (uri != null) {
        contentResolver.openInputStream(uri)?.use { /* read it */ }
    }
}

// Launch — images only
pickMedia.launch(
    PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly)
)
```

Because the user explicitly selected these items, you get access to exactly those and nothing else — which is both more private and less code than requesting a broad permission and building your own grid. For multiple selection use `PickMultipleVisualMedia`. The picker is backported via `androidx.activity`, so it works on a wide range of versions with the system providing the modern UI where available. This should be your reflex for import flows.

## Saving files: MediaStore inserts, still no permission

To *write* a file into a shared collection — save a downloaded image to the gallery, export a document — insert into the appropriate `MediaStore` collection. On modern Android you don't need a permission to create your own entries:

```kotlin
val values = ContentValues().apply {
    put(MediaStore.Images.Media.DISPLAY_NAME, "export_${System.currentTimeMillis()}.jpg")
    put(MediaStore.Images.Media.MIME_TYPE, "image/jpeg")
    put(MediaStore.Images.Media.RELATIVE_PATH, "Pictures/MyApp")
    put(MediaStore.Images.Media.IS_PENDING, 1)
}

val resolver = contentResolver
val uri = resolver.insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, values)!!
resolver.openOutputStream(uri)?.use { out -> /* write bytes */ }

// Publish once writing is done
values.clear()
values.put(MediaStore.Images.Media.IS_PENDING, 0)
resolver.update(uri, values, null, null)
```

The `IS_PENDING` flag is the important detail: set it to 1 while writing so the file isn't visible half-written to other apps, then clear it to publish. `RELATIVE_PATH` puts your file in a sensible subfolder without you constructing absolute paths. This pattern works without asking the user for anything, because you're creating content you own.

## When you actually need permissions

The granular permissions exist for apps that must *query the whole library* — a gallery, an editor, a backup tool. `READ_EXTERNAL_STORAGE` was split into:

| Permission | Grants access to |
| --- | --- |
| `READ_MEDIA_IMAGES` | All images |
| `READ_MEDIA_VIDEO` | All videos |
| `READ_MEDIA_AUDIO` | All audio |
| `READ_MEDIA_VISUAL_USER_SELECTED` | Only user-picked photos/videos (partial access) |

Request only the media types you need. And handle **partial access**: on Android 14+ the user can grant access to *some* photos instead of all, in which case you'll hold `READ_MEDIA_VISUAL_USER_SELECTED` but not the full `READ_MEDIA_IMAGES`. Your gallery must handle "I can see these 12 photos the user chose" gracefully, and offer a way to let them select more:

```kotlin
val hasFull = checkSelfPermission(READ_MEDIA_IMAGES) == PERMISSION_GRANTED
val hasPartial = checkSelfPermission(READ_MEDIA_VISUAL_USER_SELECTED) == PERMISSION_GRANTED
when {
    hasFull -> showFullLibrary()
    hasPartial -> showSelectedPlusReselectButton()
    else -> requestPermission()
}
```

Treating partial access as a failure state — greying out the screen because you didn't get full access — is a rejection risk and a bad experience. The whole point is that users can share less.

## Deleting and editing others' media

You can freely modify media *your app created*. To modify or delete media another app owns, you can't just do it — you request the user's consent via `MediaStore.createWriteRequest()` / `createDeleteRequest()`, which shows a system confirmation dialog:

```kotlin
val pendingIntent = MediaStore.createDeleteRequest(contentResolver, listOf(uri))
deleteLauncher.launch(IntentSenderRequest.Builder(pendingIntent).build())
```

The user confirms, and the system performs the operation. This is scoped storage's core bargain: your app doesn't get ambient write power over the shared store; each cross-owner mutation is a consented action.

## The `MANAGE_EXTERNAL_STORAGE` trap

There's a broad "all files access" permission (`MANAGE_EXTERNAL_STORAGE`) that some developers grab to make the old model work. Don't, unless you're building a genuine file manager, backup, or antivirus app — Google Play restricts it and will reject apps that request it without a qualifying use case. Ninety-nine percent of apps that think they need it actually need the Photo Picker or `MediaStore` and are trying to avoid learning the new APIs. Requesting it is a review risk with no upside for a typical app.

## Migration checklist

If you're modernizing an older app:

1. Replace custom image pickers with the **Photo Picker** — delete the permission and the grid.
2. Replace file writes to shared dirs with **`MediaStore` inserts** using `RELATIVE_PATH` and `IS_PENDING`.
3. Swap `READ_EXTERNAL_STORAGE` for **granular** `READ_MEDIA_*` only where you truly enumerate the library.
4. Handle **partial visual access** as a first-class state.
5. Route cross-owner deletes/edits through **`create*Request`** consent flows.
6. Drop any `MANAGE_EXTERNAL_STORAGE` request unless you're a file manager.

Minimizing what you request is also a security posture — the fewer broad permissions your app holds, the smaller its blast radius if compromised, which is the same least-privilege thinking that runs through serious [platform architecture](https://blog.michaelsam94.com/how-i-architected-an-ev-charging-platform/) work.

## What I'd take away

Scoped storage rewards apps that ask for less. Reach for the Photo Picker first — no permission, trusted UI, durable URIs — for anything where the user chooses items. Use `MediaStore` inserts with `IS_PENDING` and `RELATIVE_PATH` to save files without a permission. Only request the granular `READ_MEDIA_*` permissions when you genuinely enumerate the library, and design for partial access rather than treating it as a failure. Route cross-owner edits through the system consent requests, and stay away from `MANAGE_EXTERNAL_STORAGE`. Modernizing usually means deleting code, not adding it — which is exactly the sign you're doing it right.

## Resources

- [Photo Picker (Android developers)](https://developer.android.com/training/data-storage/shared/photopicker)
- [Access media files with MediaStore](https://developer.android.com/training/data-storage/shared/media)
- [Storage updates in Android 13+ (granular media permissions)](https://developer.android.com/about/versions/13/behavior-changes-13#granular-media-permissions)
- [Partial access to photos and videos (Android 14)](https://developer.android.com/about/versions/14/changes/partial-photo-video-access)
- [Data and file storage overview](https://developer.android.com/training/data-storage)
