---
title: "System Design: Video Streaming"
slug: "system-design-video-streaming"
description: "Designing video streaming like Netflix or YouTube: upload pipeline, transcoding, adaptive bitrate, CDN delivery, DRM, and live vs VOD architecture."
datePublished: "2025-11-29"
dateModified: "2025-11-29"
tags: ["System Design", "Media", "CDN", "Architecture"]
keywords: "video streaming system design, HLS DASH, adaptive bitrate, transcoding pipeline, CDN video delivery, Netflix architecture"
faq:
  - q: "What is adaptive bitrate streaming?"
    a: "Adaptive bitrate (ABR) delivers video in multiple quality levels (1080p, 720p, 480p, etc.) split into small segments. The player monitors bandwidth and buffer, switching quality up or down per segment. Protocols like HLS and DASH define manifest files listing segments; the client chooses which bitrate to fetch for each chunk."
  - q: "Why transcode video into multiple formats?"
    a: "Source uploads are one resolution and codec; clients vary in screen size, bandwidth, and supported codecs. Transcoding produces encoded ladders (multiple bitrates/resolutions) and often multiple container formats (HLS for Apple, DASH for others). Without transcoding, mobile users on 3G cannot play 4K source files smoothly."
  - q: "How do CDNs fit into video streaming architecture?"
    a: "Video segments are cacheable static objects ideal for CDN edge delivery. Origin stores segments in object storage (S3); CDN caches popular content near users. For live streams, short segment TTL and origin shielding reduce load. CDN reduces latency, origin bandwidth cost, and improves playback start time."
---

Video streaming looks like magic — press play, watch — but the pipeline behind it spans upload ingestion, hours of transcoding, petabytes on object storage, CDN edge caches, and a client player making dozens of decisions per minute about which four-second chunk to fetch next. Netflix's architecture is the reference; a startup's MVP is the same shape with managed services instead of custom Open Connect appliances.

## VOD vs live — architectural split

**Video on Demand (VOD):** upload → transcode → store → serve. Latency tolerance: minutes to hours. Quality of encoding matters most.

**Live streaming:** ingest RTMP/SRT → transcode in real time → segment → CDN → players. Latency tolerance: seconds to 30 seconds (LL-HLS pushes lower). Failover and redundancy dominate.

This post focuses on VOD fundamentals that also underpin live.

## Upload and ingestion

```
Client → presigned S3 URL (multipart upload)
       → POST /videos { object_key, title }
       → enqueue transcode job
```

Direct-to-storage upload keeps API servers out of the data path. Multipart for large files. Virus scan and format validation on completion callback.

## Transcoding pipeline

```
Source (4K ProRes / MP4)
  → MediaConvert / FFmpeg workers
  → Output ladder:
      1080p @ 5 Mbps
      720p  @ 2.5 Mbps
      480p  @ 1 Mbps
      360p  @ 600 Kbps
  → HLS (.m3u8 + .ts or .m4s segments)
  → S3 output bucket
```

Job queue (SQS, Celery) with GPU workers. Status webhook updates `videos.status = ready`.

**Packaging:** HLS master playlist references variant playlists per bitrate:

```
#EXTM3U
#EXT-X-STREAM-INF:BANDWIDTH=5000000,RESOLUTION=1920x1080
1080p/playlist.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=2500000,RESOLUTION=1280x720
720p/playlist.m3u8
```

Player reads master, picks variant, fetches 2–6 second segments.

## Playback path

```
Player → GET manifest from CDN
       → buffer segments adaptively
       → decode and render
```

API returns signed CDN URL (time-limited) for manifest and segments — prevents hotlinking.

```json
{
  "playback_url": "https://cdn.example.com/v/id/master.m3u8?token=...",
  "expires_at": "2026-02-02T15:00:00Z"
}
```

## Adaptive bitrate logic (client)

Player monitors:

- Download throughput (EWMA of segment fetch times)
- Buffer occupancy (seconds buffered ahead)

Switch up if bandwidth comfortably exceeds current bitrate and buffer healthy. Switch down before buffer underrun. Abrupt switches cause visible quality jumps — hysteresis and capped switch frequency smooth experience.

## DRM and encryption (premium content)

Widevine (Chrome/Android), FairPlay (Safari/iOS), PlayReady (Edge). License server validates entitlement; segments encrypted (AES-128 or SAMPLE-AES). Adds key rotation, device attestation, offline download complexity.

User-generated content platforms often skip DRM; studio content requires it.

## Metadata and recommendations (adjacent systems)

Separate service: title, thumbnails (sprite sheets from transcoder), watch history, continue watching position. Thumbnails generated during transcode — one frame per N seconds for scrub bar preview.

## Scale and cost drivers

- **Storage:** raw + ladder ≈ 1.5–2x source size per ladder rung combined
- **Transcoding:** GPU-minute billing — biggest processing cost
- **CDN egress:** dominates at scale — per-GB pricing drives business model

Cold content: Glacier/archive tier; re-transcode on first replay if needed (rare).

## Live streaming additions

- Ingest redundancy (dual encoders)
- Low-latency HLS (partial segments)
- DVR window (keep last N hours as seekable buffer)
- Chat/presence sidecar (WebSocket, separate from video path)

## Failure modes

| Issue | Mitigation |
| --- | --- |
| Buffer stall | Lower initial bitrate; CDN prefetch |
| Transcode backlog | Auto-scale workers; priority queue |
| CDN miss storm | Origin shield; pre-warm popular releases |
| Token leak | Short TTL; bind to session |

## CDN and origin cost management

Egress dominates video COGS. Negotiate CDN committed use discounts; use origin shield POPs to collapse cache misses. Pre-warm popular assets before scheduled releases. For long-tail VOD, tier cold storage and accept higher start-time latency on first view. Monitor bytes-delivered per title to inform licensing negotiations.

## ABR ladder design

Adaptive bitrate requires careful ladder construction:

| Rung | Resolution | Bitrate | Use case |
|------|------------|---------|----------|
| 1 | 426×240 | 400 kbps | 2G, congested WiFi |
| 2 | 854×480 | 1200 kbps | Mobile default |
| 3 | 1280×720 | 2500 kbps | WiFi, tablet |
| 4 | 1920×1080 | 5000 kbps | Desktop, TV |

Encode with aligned GOP boundaries across rungs — player switches segments without visual pops. Target 2-second segments for VOD, 1-second for low-latency live.

## Player analytics

Track QoE metrics client-side:

- **Startup time** — play button to first frame
- **Rebuffer ratio** — rebuffer seconds / watch seconds
- **Bitrate switches** — count and direction (up vs down)
- **Exit before start** — CDN or encode problem signal

Correlate with CDN POP and ISP — rebuffer spikes in one region indicate edge capacity, not global encode issues.

## Production checklist

- [ ] Multi-CDN failover tested (Route 53 latency routing or player SDK switch)
- [ ] Signed URLs with TTL < video duration for premium content
- [ ] Transcode job queue depth alert before release day traffic
- [ ] Origin shield enabled; direct origin access blocked
- [ ] Watch history and continue-watching separate from video delivery path

## Common production mistakes

Teams get video streaming wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

System design for video streaming breaks at scale when hot keys, thundering herds, and cache stampedes are discovered during launch week instead of load test week.

## Debugging and triage workflow

When video streaming misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [Apple HLS specification](https://developer.apple.com/documentation/http-live-streaming)
- [MPEG-DASH overview](https://dashif.org/about/)
- [Netflix tech blog](https://netflixtechblog.com/)
- [AWS Elemental MediaConvert](https://aws.amazon.com/mediaconvert/)
- [Web.dev — adaptive streaming](https://web.dev/articles/media-mse-basics)
