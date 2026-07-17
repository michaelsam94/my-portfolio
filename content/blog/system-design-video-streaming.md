---
title: "System Design: Video Streaming"
slug: "system-design-video-streaming"
description: "Designing video streaming like Netflix or YouTube: upload pipeline, transcoding, adaptive bitrate, CDN delivery, DRM, and live vs VOD architecture."
datePublished: "2025-11-29"
dateModified: "2026-07-17"
tags: ["System Design", "Media", "CDN", "Architecture"]
keywords: "video streaming system design, HLS DASH, adaptive bitrate, transcoding pipeline, CDN video delivery, Netflix architecture"
faq:
  - q: "What is adaptive bitrate streaming?"
    a: "Adaptive bitrate (ABR) delivers video in multiple quality levels (1080p, 720p, 480p, etc.) split into small segments. The player monitors bandwidth and buffer, switching quality up or down per segment. Protocols like HLS and DASH define manifest files listing segments; the client chooses which bitrate to fetch for each chunk."
  - q: "Why transcode video into multiple formats?"
    a: "Source uploads are one resolution and codec; clients vary in screen size, bandwidth, and supported codecs. Transcoding produces encoded ladders (multiple bitrates/resolutions) and often multiple container formats (HLS for Apple, DASH for others). Without transcoding, mobile users on 3G cannot play 4K source files smoothly."
  - q: "How do CDNs fit into video streaming architecture?"
    a: "Video segments are cacheable static objects ideal for CDN edge delivery. Origin stores segments in object storage (S3); CDN caches popular content near users. For live streams, short segment TTL and origin shielding reduce load. CDN reduces latency, origin bandwidth cost, and improves playback start time."
faqAnswers:
  - question: "When is system design video streaming the wrong approach?"
    answer: "When a simpler control already covers the risk, or when the operational cost exceeds the benefit for your threat and traffic model."
  - question: "What should we measure for system design video streaming?"
    answer: "Pair a leading operational signal with a lagging user or risk outcome, reviewed on a fixed cadence with a named owner."
  - question: "How do we roll back system design video streaming safely?"
    answer: "Keep the prior artifact or config warm, rehearse the revert once in staging, and document the one-command rollback for on-call."
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

## Adaptive bitrate ladder design

ABR players switch quality based on buffer health and throughput estimates. Encode each title in a ladder (240p through 4K) with segment duration 2–6 seconds. CDN caches segments by URL; origin shield reduces origin load during viral content. Live streaming adds DVR window complexity — segment availability TTL must exceed rewind duration. Monitor rebuffer ratio per quality rung; if 1080p rebuffer spikes on mobile networks, adjust ladder to promote 720p sooner.

## CDN cache key design for segments

HLS segment URLs must be cache-friendly: include bitrate rung and sequence number, avoid session IDs in path. Origin shield in front of packager reduces thundering herd when popular live event starts. Monitor origin egress — viral VOD can exceed origin capacity if CDN cache hit ratio drops below 95%.

## Resources

- [Apple HLS specification](https://developer.apple.com/documentation/http-live-streaming)
- [MPEG-DASH overview](https://dashif.org/about/)
- [Netflix tech blog](https://netflixtechblog.com/)
- [AWS Elemental MediaConvert](https://aws.amazon.com/mediaconvert/)
- [Web.dev — adaptive streaming](https://web.dev/articles/media-mse-basics)

## system design video streaming rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## system design video streaming rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## system design video streaming rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## system design video streaming rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## system design video streaming rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## Field notes on system design video streaming

System design interviews and production systems diverge: system design video streaming in production needs SLOs, abuse controls, and multi-region failure stories. Sketch the data model and consistency requirements before drawing boxes.

For system design video streaming:
- Separate read and write scaling paths early if fan-out or search is involved
- Idempotency keys on payments, bookings, and message delivery
- Backpressure at every queue; unbounded buffers are delayed outages
- Hot-key and thundering-herd mitigations (jitter, singleflight, cache stampedes)

Write the load-test plan that would disprove your capacity claims — QPS, payload sizes, and regional failover RTO.

| Signal | Target | Alarm |
|--------|--------|-------|
| Latency p99 | Team-defined SLO | Page on burn rate |
| Error rate | Baseline − noise | Ticket if sustained |
| Cost per 1k ops | Budget cap | Weekly review |

## Ownership and on-call for system design video streaming

Reviewers should challenge assumptions encoded in system design video streaming: defaults copied from tutorials, timeouts that exceed upstream SLAs, and authz checks applied only on the primary UI path. Require a short threat or failure note in the PR when the change touches a trust boundary.

Concrete probes:
1. Scenario A for system design video streaming: partial dependency outage — prove clients degrade gracefully and retries do not amplify load.
2. Scenario B for system design video streaming: bad config shipped — prove rollback within the declared RTO without data corruption.
3. Scenario C for system design video streaming: traffic 3× baseline — prove autoscaling or shedding keeps the golden journey healthy.

## Capacity planning with system design video streaming in mind

Roll out system design video streaming behind a flag or weighted route when possible. Start with internal users or a low-risk geography. Watch the signals in the table for at least one full business cycle before calling the migration done. Keep the previous path warm until error budgets stabilize.

Document the owner, the dashboard, and the single command that reverts the change. If that sentence is hard to write, the design is not ready for production traffic.

## Caching interactions with system design video streaming

Detail 1 (547): for system design video streaming, define the contract between producers and consumers explicitly — payload shape, timeout, and idempotency key. When caching interactions with system design video streaming becomes painful, it is usually because that contract was implicit.

I keep a short matrix: who can break system design video streaming, how we detect it within five minutes, and who is paged. Update the matrix when ownership moves. Add one synthetic check that exercises the failure path, not only the happy path. Prefer checks that run continuously over quarterly manual reviews that everyone skips under deadline pressure.

If you only remember one thing about system design video streaming: optimize for reversible decisions. Reversibility beats cleverness when the incident channel is busy and the blast radius is unclear.

## Multi-tenant concerns in system design video streaming

Detail 2 (375): for system design video streaming, define the contract between producers and consumers explicitly — payload shape, timeout, and idempotency key. When multi-tenant concerns in system design video streaming becomes painful, it is usually because that contract was implicit.

I keep a short matrix: who can break system design video streaming, how we detect it within five minutes, and who is paged. Update the matrix when ownership moves. Add one synthetic check that exercises the failure path, not only the happy path. Prefer checks that run continuously over quarterly manual reviews that everyone skips under deadline pressure.

If you only remember one thing about system design video streaming: optimize for reversible decisions. Reversibility beats cleverness when the incident channel is busy and the blast radius is unclear.