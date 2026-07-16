---
title: "Integrating Image Generation APIs"
slug: "multimodal-image-generation-apis"
description: "Integrate DALL·E, Stable Diffusion, and Flux image APIs into applications: prompt design, safety filters, storage, caching, and cost control."
datePublished: "2025-08-10"
dateModified: "2025-08-10"
tags: ["AI", "API", "Backend", "Design"]
keywords: "image generation API, DALL-E integration, Stable Diffusion API, AI image generation, prompt engineering images, Flux model API"
faq:
  - q: "How do I prevent users from generating inappropriate images?"
    a: "Layer defenses: provider safety filters, blocklists on prompts, output classifiers (NSFW detection), rate limits per user, and human review queues for flagged generations. Log prompt hashes, not raw prompts, if privacy matters."
  - q: "Should I store generated images or regenerate on demand?"
    a: "Store images in object storage (S3, GCS) with the prompt and seed in metadata. Regeneration with the same seed is not guaranteed across API versions. Storage costs pennies per image; regeneration costs API credits and adds latency."
  - q: "What resolution should I request from image APIs?"
    a: "1024×1024 is the sweet spot for most providers—good quality, moderate cost. Generate at target size rather than upscaling when possible. Offer 512×512 previews before full-resolution generation to cut spend."
---

Your app lets users generate product mockups from text descriptions. The first integration attempt pipes raw user input to an API and displays whatever returns—including occasional policy violations and $0.08 images that users regenerate five times before accepting one. Production image generation needs prompt templating, safety gates, async job handling, and storage that survives API version changes.

## Provider comparison

| Provider | Model | Strengths | Typical cost |
|----------|-------|-----------|--------------|
| OpenAI | DALL·E 3 | Prompt adherence, safety | ~$0.04–0.12/image |
| Stability AI | SDXL, SD3 | Style control, self-host option | ~$0.002–0.03/image |
| Black Forest Labs | Flux | Photorealism, text in images | Varies by host |
| Replicate / Fal.ai | Many | Pay-per-second GPU, no infra | Usage-based |

Abstract behind an internal interface so you can swap providers without rewriting UI code.

## Async job pattern

Image generation takes 3–30 seconds. Don't block HTTP requests.

```python
# POST /api/images/generate
async def create_generation(request: GenerateRequest):
    job_id = str(uuid4())
    await redis.set(f"job:{job_id}", json.dumps({"status": "pending"}))
    await queue.enqueue("generate_image", job_id, request.dict())
    return {"job_id": job_id}

# Worker
async def generate_image(job_id: str, params: dict):
    await redis.set(f"job:{job_id}", json.dumps({"status": "processing"}))
    try:
        result = await openai_client.images.generate(
            model="dall-e-3",
            prompt=build_prompt(params),
            size="1024x1024",
            quality="standard",
            n=1,
        )
        url = result.data[0].url
        stored = await upload_to_s3(await fetch_bytes(url))
        await redis.set(f"job:{job_id}", json.dumps({
            "status": "complete",
            "url": stored,
        }))
    except Exception as e:
        await redis.set(f"job:{job_id}", json.dumps({
            "status": "failed",
            "error": str(e),
        }))
```

Poll `GET /api/images/jobs/{job_id}` or push via WebSocket when complete.

## Prompt templating

Never pass raw user text directly. Wrap it:

```python
TEMPLATE = """Product photography of {user_description}.
Style: clean white background, soft studio lighting, 45-degree angle.
No text, no watermarks, no people unless specified."""

def build_prompt(params: dict) -> str:
    cleaned = sanitize(params["description"])  # strip injection attempts
    return TEMPLATE.format(user_description=cleaned[:500])
```

Negative prompts (for Stable Diffusion) suppress common artifacts:

```
blurry, distorted, low quality, watermark, text overlay, cropped
```

## Safety and abuse prevention

```python
BLOCKED_TERMS = load_blocklist("blocked_terms.txt")

def sanitize(text: str) -> str:
    lower = text.lower()
    for term in BLOCKED_TERMS:
        if term in lower:
            raise PromptRejected(f"blocked content")
    return text.strip()
```

Add per-user quotas: 10 generations/day free, paid tiers above. Track spend per `user_id` and alert when daily cost exceeds threshold.

## Storage and CDN

```python
async def upload_to_s3(image_bytes: bytes, job_id: str) -> str:
    key = f"generations/{job_id}.webp"
    s3.put_object(
        Bucket="assets",
        Key=key,
        Body=image_bytes,
        ContentType="image/webp",
        Metadata={"job_id": job_id},
    )
    return f"https://cdn.example.com/{key}"
```

Convert PNG to WebP on ingest—60% smaller with no visible loss. Set `Cache-Control: immutable, max-age=31536000` since generation IDs are unique.

## Self-hosted Stable Diffusion

When API costs exceed ~$500/month at your volume, a single A10G GPU on RunPod handles 15–20 images/minute with SDXL:

```python
import requests

response = requests.post("http://gpu-worker:7860/sdapi/v1/txt2img", json={
    "prompt": prompt,
    "negative_prompt": negative,
    "steps": 25,
    "width": 1024,
    "height": 1024,
    "cfg_scale": 7,
    "seed": seed,
})
image_b64 = response.json()["images"][0]
```

Pin model versions in your worker container. Upgrading checkpoints changes output style—communicate that to users.

## Caching identical requests

Hash `(prompt, size, model, seed)` and return cached URL if exists. Users re-clicking "generate" with unchanged inputs shouldn't burn credits.

## API selection guide

| Provider | Model | Best for | Cost/image |
|---|---|---|---|
| OpenAI | DALL·E 3 | High quality, prompt adherence | ~$0.04–0.12 |
| Stability AI | SDXL/SD3 | Customization, ControlNet | ~$0.002–0.01 |
| Replicate | Various | Experimentation, fine-tunes | ~$0.001–0.005 |
| Self-hosted | SDXL | High volume (>10k/day) | GPU cost only |

```python
# OpenAI DALL·E 3
response = client.images.generate(
    model="dall-e-3",
    prompt=prompt,
    size="1024x1024",
    quality="standard",  # or "hd" for 2× cost
    n=1,
)

# Stability AI SDXL
response = requests.post(
    "https://api.stability.ai/v2beta/stable-image/generate/sd3",
    headers={"Authorization": f"Bearer {STABILITY_KEY}"},
    files={"prompt": (None, prompt), "output_format": (None, "webp")},
)
```

OpenAI for quality-critical generation. Stability/Replicate for volume and customization. Self-hosted when API costs exceed ~$500/month.

## Content moderation pipeline

Filter generated images before delivery:

```python
async def generate_and_moderate(prompt: str, user_id: str) -> str:
    # Pre-generation: filter prompt
    if await moderation_api.check(prompt).flagged:
        raise ContentPolicyViolation("Prompt violates content policy")

    image_url = await generate_image(prompt)

    # Post-generation: scan image
    if await vision_moderation.check(image_url).nsfw_score > 0.8:
        await audit_log.record(user_id, prompt, "blocked_nsfw")
        raise ContentPolicyViolation("Generated image blocked")

    return image_url
```

Moderate both prompt and output. Log blocked generations for policy review and user appeal process.

## Generation metadata for audit

Store full generation context for compliance and debugging:

```json
{
  "generation_id": "gen_abc123",
  "user_id": "user_xyz",
  "prompt": "A modern office building at sunset",
  "negative_prompt": "blurry, watermark",
  "model": "stabilityai/sdxl-base-1.0",
  "model_version": "1.0.0",
  "seed": 42,
  "steps": 25,
  "guidance_scale": 7.5,
  "width": 1024,
  "height": 1024,
  "generated_at": "2024-12-27T10:00:00Z",
  "cdn_url": "https://cdn.example.com/gen_abc123.webp"
}
```

Required for copyright disputes, content moderation appeals, and reproducing specific outputs.

## Failure modes

- **No prompt moderation** — policy-violating prompts reach generation API
- **Unpinned model version** — output style changes on provider model update
- **No request caching** — identical re-generations burn credits unnecessarily
- **NSFW content reaches CDN** — no post-generation scan
- **No generation metadata** — can't reproduce or audit specific outputs

## Production checklist

- Pre-generation prompt moderation before API call
- Post-generation image scan before CDN upload
- Model version pinned in production configuration
- Request cache keyed on (prompt, seed, model, size) hash
- Generation metadata stored for audit and reproduction
- Provider selected by use case: quality (OpenAI) vs volume (Stability/self-hosted)

## Resources

- [OpenAI Images API](https://platform.openai.com/docs/guides/images) — DALL·E 3 parameters and limits
- [Stability AI API docs](https://platform.stability.ai/docs/api-reference) — SDXL and SD3 endpoints
- [Replicate image models](https://replicate.com/collections/text-to-image) — hosted open-source models
- [Automatic1111 API wiki](https://github.com/AUTOMATIC1111/stable-diffusion-webui/wiki/API) — self-hosted SD WebUI reference
- [AWS S3 object metadata](https://docs.aws.amazon.com/AmazonS3/latest/userguide/UsingMetadata.html) — storing generation metadata
