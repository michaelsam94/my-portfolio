---
title: "Multimodal Models in Apps: Vision Plus Text"
slug: "multimodal-models-in-apps"
description: "How to build with vision-language models: sending images to multimodal LLMs, OCR and document understanding, structured extraction, and the cost and latency traps."
datePublished: "2026-02-24"
dateModified: "2026-02-24"
tags: ["Multimodal AI", "Vision", "LLM", "Mobile"]
keywords: "multimodal AI, vision language models, image understanding, multimodal apps, VLM, OCR AI"
faq:
  - q: "What is a vision-language model?"
    a: "A vision-language model (VLM) is a multimodal LLM that accepts images alongside text in the same context, so you can ask questions about a picture, extract data from a document photo, or describe a scene. Models like GPT-4o, Claude, and Gemini handle vision and text together natively."
  - q: "Should I use a multimodal LLM or a dedicated OCR engine?"
    a: "For clean, high-volume text extraction, a dedicated OCR engine is faster and cheaper. For understanding — reading a messy receipt into structured fields, answering questions about a chart, describing an image — a vision-language model wins because it reasons about content, not just characters. Many pipelines combine both."
  - q: "How much do images cost in a multimodal API call?"
    a: "Images are billed as tokens based on resolution — a high-detail image can cost hundreds to over a thousand tokens. Downscaling images to the smallest resolution that preserves the detail you need is the main lever for controlling multimodal cost and latency."
---

Multimodal models turned "read the image and tell me what's in it" from a research project into an API call. A vision-language model (VLM) takes an image and text in the same context, so a single request can read a receipt into structured fields, answer a question about a chart, describe a photo for accessibility, or spot a defect in a product image. For app developers, that collapses what used to be a pipeline of specialized CV models into one flexible endpoint.

The flexibility is real, and so are the traps: images are expensive in tokens, resolution handling is fiddly, and a VLM will confidently misread a blurry number rather than admit it can't see it. This is a practical look at building multimodal features that work — how to send images, when a VLM beats classic OCR, how to get structured data out, and where the cost and reliability landmines are buried.

## Sending an image is the easy part

The API shape is straightforward: images go into the message content alongside text, either as a URL or base64-encoded bytes.

```python
from openai import OpenAI
client = OpenAI()

resp = client.chat.completions.create(
    model="gpt-4o",
    messages=[{
        "role": "user",
        "content": [
            {"type": "text", "text": "Extract the total and date from this receipt."},
            {"type": "image_url",
             "image_url": {"url": f"data:image/jpeg;base64,{b64_image}", "detail": "high"}},
        ],
    }],
)
```

The `detail` parameter is the one that matters. `low` downsamples the image to a small fixed size for a flat, cheap token cost — great for "what's in this photo" questions. `high` tiles the image at full resolution, costing far more tokens but preserving fine detail you need for reading small text. Picking the right detail level per use case is the single biggest cost lever in a vision pipeline.

## VLM vs. dedicated OCR: pick per task

A common mistake is reaching for a VLM for everything, including bulk text extraction where a purpose-built OCR engine is faster and an order of magnitude cheaper. The distinction that matters:

| Task | Best tool |
|---|---|
| High-volume, clean text digitization | Dedicated OCR (Tesseract, Google Document AI) |
| Messy receipt/invoice → structured fields | VLM (reasons about layout and meaning) |
| "Is there a person in this image?" | Lightweight classifier or VLM at `low` detail |
| Answering questions about a chart or diagram | VLM |
| Accessibility image descriptions | VLM (or on-device, see below) |

The rule of thumb: if the job is *transcription*, use OCR; if the job is *understanding*, use a VLM. Plenty of strong pipelines chain them — OCR extracts raw text fast, then a text LLM structures and reasons over it, saving the vision tokens entirely.

## Getting structured data out, reliably

The killer app for VLMs in business software is turning documents into structured data: receipts, invoices, ID cards, forms. Combine vision with [structured outputs](https://blog.michaelsam94.com/structured-outputs-function-calling/) so the model returns a schema-validated object instead of prose:

```python
class Receipt(BaseModel):
    merchant: str
    date: str          # ISO 8601
    total_cents: int
    currency: str
    line_items: list[str]
    confidence: float  # model's own read confidence, 0-1
```

Two hard-won details. First, ask for a **confidence** field and a way to say "unreadable" — VLMs will otherwise hallucinate a plausible number for a smudged total rather than flag it, and a fabricated total is worse than a blank one. Route low-confidence extractions to human review. Second, **validate semantically**: does the total match the sum of line items? Is the date real? The model guarantees the shape, not the truth, so business-rule checks stay your job.

## Cost and latency reality

Images are token-heavy, and it surprises people the first time they see the bill. A `high` detail full-page document can consume well over a thousand tokens per image before the model writes a single word of response. Levers that keep this sane:

- **Downscale aggressively.** Resize to the smallest resolution that still preserves the detail you need. A 4000px phone photo of a receipt rarely needs to be sent at full size — 1024-1568px on the long edge is often plenty and cuts tokens dramatically.
- **Use `low` detail by default**, escalating to `high` only when the task needs fine text.
- **Crop to the region of interest** before sending when you know where the data is.
- **Batch offline work.** Document backfills and catalog enrichment don't need real-time responses; the [batch API is roughly half price](https://blog.michaelsam94.com/cutting-llm-costs-caching-routing-batching/).

Latency scales with image size and detail too, so the same downscaling that saves money also tightens response times — which matters on mobile where you're already [fighting flaky networks](https://blog.michaelsam94.com/handling-flaky-networks-mobile/).

## On-device and privacy

Not every image needs to leave the phone. For accessibility descriptions, simple scene understanding, or privacy-sensitive documents, on-device multimodal models are increasingly viable — [Gemini Nano's image description](https://blog.michaelsam94.com/on-device-ai-android-gemini-nano/) on supported Android hardware handles this class of task locally, with no upload and no per-request cost. For sensitive content like ID documents or medical images, keeping inference on-device isn't just cheaper, it sidesteps a stack of data-handling obligations. As with any conditional on-device capability, design for the devices that can't do it.

## Where it goes wrong

A short list of failure modes to test for before shipping:

- **Confident misreads** of blurry or rotated text — always capture confidence and validate.
- **Orientation.** Phone photos come in sideways; correct EXIF rotation before sending or the model reads gibberish.
- **Injection via images.** Text embedded in an uploaded image can carry instructions ("ignore your task and…"). Treat image-derived text as untrusted input and apply [guardrails](https://blog.michaelsam94.com/guardrails-moderation-llm-apps/).
- **Multi-page documents.** Sending many high-detail pages in one call blows the token budget and buries detail in the middle of context; process page by page.

Multimodal is one of the most immediately useful capabilities to add to an app — the API is simple and the payoff is high. Treat images as the expensive, sometimes-unreliable inputs they are: downscale, extract into validated structure, verify against business rules, and keep the sensitive stuff on-device. Do that and "read the image" becomes a dependable feature rather than a surprise line on the invoice.

## Resources

- [OpenAI — Vision guide](https://platform.openai.com/docs/guides/vision)
- [Anthropic — Vision](https://docs.anthropic.com/en/docs/build-with-claude/vision)
- [Google — Gemini image understanding](https://ai.google.dev/gemini-api/docs/image-understanding)
- [Google Cloud — Document AI](https://cloud.google.com/document-ai/docs)
- [Tesseract OCR (GitHub)](https://github.com/tesseract-ocr/tesseract)
- [ML Kit — Text recognition](https://developers.google.com/ml-kit/vision/text-recognition/v2)
