---
title: "On-Device OCR with ML Kit Text Recognition"
slug: "android-text-recognition-mlkit-ocr"
description: "Build reliable on-device OCR on Android with ML Kit Text Recognition v2: script models, the Text/Line/Element hierarchy, live scanning, and parsing structured fields."
datePublished: "2024-07-20"
dateModified: "2024-07-20"
tags: ["Android", "Kotlin", "ML Kit", "OCR"]
keywords: "ML Kit text recognition, on-device OCR Android, TextRecognizer, OCR Android Kotlin, ML Kit OCR live"
faq:
  - q: "Does ML Kit text recognition work offline?"
    a: "Yes, the on-device text recognition runs entirely on the device with no network call, and the base recognizer is free. The Latin script model can be bundled in your APK or downloaded via Play Services, and non-Latin scripts (Chinese, Devanagari, Japanese, Korean) are separate model dependencies. All of them run locally once available."
  - q: "How accurate is ML Kit OCR compared to a cloud API?"
    a: "For clear, well-lit printed text — receipts, labels, documents, signs — on-device ML Kit is highly accurate and fast enough for live scanning. Cloud OCR still edges it out on messy handwriting, dense documents, and unusual fonts, but for the common mobile cases the on-device model is close enough that the offline, free, and private tradeoff usually wins."
  - q: "How do I extract a specific field like a total or an ID number from OCR output?"
    a: "Don't rely on the raw blob of text. Walk the Text/TextBlock/Line/Element hierarchy ML Kit returns, which includes bounding boxes, and combine positional heuristics with regex on the recognized strings. For example, find the line containing 'Total' and read the numeric element to its right, or match a known ID format with a regex over elements."
---

If you need to read printed text with a phone camera — receipts, ID cards, serial numbers, labels, menus — ML Kit Text Recognition v2 does it on-device, offline, and free, and it's fast enough to run live in a viewfinder. I've used it for a receipt-capture feature and a serial-number scanner, and the recognizer itself is the easy part. The engineering is in choosing the right script model, understanding the text hierarchy it returns, and turning a blob of recognized words into the *specific field* your product actually needs.

## Pick your script model

Text Recognition v2 splits models by script. You depend only on what you need:

- **Latin** — English and most Western European languages. Can be bundled or unbundled.
- **Chinese**, **Devanagari**, **Japanese**, **Korean** — separate model dependencies.

Each has its own recognizer client:

```kotlin
// Latin
val recognizer = TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS)

// e.g. Japanese
val jaRecognizer = TextRecognition.getClient(JapaneseTextRecognizerOptions.Builder().build())
```

Don't pull every script model "just in case" — each adds size or a download. Match the models to your users' actual content. A receipt scanner for a Latin-script market needs exactly one.

## The recognition call

Wrap the source in an `InputImage` (a bitmap, a file URI, or a live camera frame) and call `process()`:

```kotlin
val image = InputImage.fromBitmap(bitmap, rotationDegrees)
recognizer.process(image)
    .addOnSuccessListener { text -> parse(text) }
    .addOnFailureListener { e -> log(e) }
```

For a live camera feed, feed frames from a [CameraX ImageAnalysis pipeline](https://blog.michaelsam94.com/android-camerax-image-analysis/) with `KEEP_ONLY_LATEST` backpressure and close the `ImageProxy` in the completion listener — the same discipline as any [on-device ML Kit vision](https://blog.michaelsam94.com/android-mlkit-on-device-vision/) feature. OCR is heavier than barcode scanning, so throttle to a few frames a second.

## Understand the hierarchy — it's the whole trick

The biggest mistake is treating the result as one flat string. ML Kit returns a *structure*, and that structure — with bounding boxes at every level — is how you extract fields reliably:

```
Text                    // everything recognized
 └─ TextBlock           // a paragraph-ish region, has a bounding box
     └─ Line            // one line of text, has a bounding box + angle
         └─ Element     // a word/token, has a bounding box
```

```kotlin
for (block in text.textBlocks) {
    for (line in block.lines) {
        val lineText = line.text
        val box = line.boundingBox          // Rect in image coords
        for (element in line.elements) {
            val word = element.text
            val wordBox = element.boundingBox
        }
    }
}
```

Those bounding boxes let you reason spatially, which is what turns OCR into data extraction.

## Extracting structured fields

Raw text is rarely the deliverable — "the total on this receipt" or "the ID number on this card" is. Combine positional logic with pattern matching:

1. **Regex over elements** for known formats. A VIN, an IBAN, a serial number all have shapes you can match: `Regex("[A-Z0-9]{17}")` over element text finds candidate VINs directly.
2. **Anchor + neighbor** for labeled values. Find the line containing "Total," then read the numeric element to its right or on the same line — using bounding-box x-coordinates to know what "to the right" means.
3. **Row grouping by y-coordinate** for tables. Elements with similar `boundingBox.top` belong to the same row; sort within a row by `left` to reconstruct columns.

This positional approach is far more robust than string-splitting the flat text, which falls apart the moment the layout shifts slightly.

## Live scanning that feels good

For scan-and-confirm UX, a few tricks make it feel reliable rather than jittery:

- **Debounce on stability.** OCR results flicker frame to frame. Require the same target string across 2–3 consecutive frames before accepting it — this kills the flicker and reduces misreads.
- **Region of interest.** Ask the user to frame the text in a rectangle and only run OCR on that crop. Less to process, fewer distractions, higher accuracy.
- **Confidence and sanity checks.** Validate the extracted field (checksum on an ID, currency format on a total) before showing success. A green checkmark on garbage is worse than asking again.
- **Guide the user.** Poor lighting and motion blur are the top accuracy killers. A hint to hold steady or move to better light does more than any model tweak.

## When on-device isn't enough

On-device OCR is excellent on clear printed text. Where it struggles: dense multi-column documents, handwriting, exotic fonts, and low-contrast or damaged sources. If that's your core use case, a cloud OCR service will read better — but you pay in latency, cost, connectivity, and sending user documents off-device. For the overwhelming majority of mobile OCR (receipts, labels, cards, signs), on-device wins on the whole package.

## What I'd take away

ML Kit Text Recognition gives you free, offline, live-capable OCR — but the accuracy of your *feature* comes from what you do with the result, not the recognizer. Depend only on the script models you need, and instead of flattening the output, walk the Text/Block/Line/Element hierarchy and use the bounding boxes to extract fields by position and pattern. Debounce live results on stability, constrain scanning to a region of interest, validate extracted fields before celebrating, and guide the user toward good lighting. Do that and a phone camera becomes a genuinely reliable data-entry tool.

## Resources

- [ML Kit Text Recognition v2 (Android)](https://developers.google.com/ml-kit/vision/text-recognition/v2/android)
- [Text Recognition overview](https://developers.google.com/ml-kit/vision/text-recognition/v2)
- [Text reference (TextBlock, Line, Element)](https://developers.google.com/ml-kit/reference/android/com/google/mlkit/vision/text/Text)
- [ML Kit vision APIs](https://developers.google.com/ml-kit/vision)
- [InputImage reference](https://developers.google.com/ml-kit/reference/android/com/google/mlkit/vision/common/InputImage)
