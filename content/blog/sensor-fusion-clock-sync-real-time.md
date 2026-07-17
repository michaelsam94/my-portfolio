---
title: "Sensor Fusion and Clock Sync in Real-Time Systems"
slug: "sensor-fusion-clock-sync-real-time"
description: "Why clock synchronization decides whether sensor fusion works: PTP vs NTP, timestamping strategy, Kalman filtering, and the alignment bugs that ruin real-time data."
datePublished: "2026-07-15"
dateModified: "2026-07-17"
tags:
  - "Engineering"
keywords: "sensor fusion, clock synchronization, real-time systems, PTP time sync, data fusion, Kalman filter, NTP"
faq:
  - q: "PTP vs NTP?"
    a: "PTP gives sub-ms sync on supported hardware; NTP jitter breaks tight fusion."
  - q: "What to log?"
    a: "Per-sensor offset estimates; alert when drift exceeds filter tolerance."
  - q: "Simulation?"
    a: "Replay with injected clock skew to test fusion robustness before field deploy."
---

The bug that taught me to respect clocks looked like a physics violation: an object appearing to move backward for a single frame before continuing forward. Nothing was wrong with the tracking math. The problem was that two data streams were timestamped by two devices whose clocks drifted a few milliseconds apart, so fusing them by time occasionally interleaved readings out of order. Sensor fusion is only ever as good as the clock that timestamps the inputs — get the time wrong and no amount of clever filtering saves you.

That's the thesis of this post: in real-time systems, **clock synchronization is not an infrastructure detail, it's the precondition for correct fusion.** You combine data from multiple sensors by aligning them in time, and if "the same time" means different things to different sensors, you're fusing readings that never actually coexisted. I've hit this in real-time tracking and robotics-adjacent work, and the debugging always eventually leads back to time.

## Fusion is alignment before it's math

Strip sensor fusion to its core and it's two steps: align measurements onto a common timeline, then combine the aligned measurements. Engineers love talking about the second step — Kalman filters, complementary filters, weighting schemes — but the first step is where systems actually break.

Consider fusing a 30 Hz camera with a 200 Hz IMU to track a moving object. The IMU gives you frequent motion updates; the camera gives you accurate but slow position fixes. To fuse them, you need to know *when* each reading was taken relative to the other. A camera frame stamped 5 ms late gets matched against the wrong IMU sample, and your estimate lurches. The fusion algorithm is blameless; the timeline was a lie.

## Timestamp at the source, as early as possible

The single most important practice: **timestamp a reading as close to the sensor as physically possible, and never re-stamp it downstream.** A timestamp applied when a message arrives at your server is worthless for fusion — it includes queuing, network, and scheduling jitter that has nothing to do with when the phenomenon actually happened.

Concretely:

- Stamp in the sensor hardware or driver, not in application code that runs "eventually."
- Carry that original timestamp through every hop unchanged; add processing timestamps as *separate* fields if you need latency metrics.
- Record which clock a timestamp came from, so you can correct for known offsets.

This is exactly the discipline behind reliable [real-time analytics for player and ball tracking](https://blog.michaelsam94.com/world-cup-real-time-analytics-player-ball-tracking/) — the moment of capture is the truth, and everything after is transport you must not conflate with it.

## NTP is fine until it isn't

For most systems, NTP synchronizes clocks to within a few milliseconds, which is plenty for logs, dashboards, and low-rate fusion. But high-rate fusion exposes NTP's limits. At 200 Hz, samples are 5 ms apart — so a 3 ms clock error is more than half a sample period, enough to misorder readings.

That's where **PTP (IEEE 1588)** comes in. PTP uses hardware timestamping at the network interface to achieve sub-microsecond synchronization, because it removes the software-stack jitter that limits NTP.

| Aspect | NTP | PTP (IEEE 1588) |
| --- | --- | --- |
| Typical accuracy | ~1–10 ms | sub-microsecond |
| Timestamping | Software | Hardware (NIC/PHY) |
| Network needs | Any | PTP-aware switches for best results |
| Use for | Logs, most apps | High-rate fusion, robotics, control |

The practical rule I use: if your sample interval is within an order of magnitude of your clock error, you need better sync. At 30 Hz with millisecond NTP you're usually fine; at 1 kHz you need PTP.

## Handling latency and out-of-order data

Even with synchronized clocks, data arrives late and out of order over real networks. Robust fusion assumes this rather than hoping otherwise:

```python
# Buffer readings and fuse on event-time, not arrival-time.
# A short watermark delay lets late samples land before we commit.
def on_reading(reading, buffer, watermark_ms=20):
    buffer.insort(reading, key=lambda r: r.event_time)
    cutoff = now() - watermark_ms
    ready = buffer.pop_until(event_time <= cutoff)
    return fuse(sorted(ready, key=lambda r: r.event_time))
```

The watermark is a deliberate trade: a small buffering delay in exchange for correctly ordered fusion. Too short and you drop late samples; too long and you add latency. Tuning it is application-specific, but the pattern — buffer, order by event time, release behind a watermark — is what keeps out-of-order arrivals from corrupting the fused output. It's the same event-time-versus-arrival-time distinction that stream processing systems formalize.

## When to reach for a Kalman filter

Once your data is aligned, the combination step depends on the problem. A Kalman filter shines when you're estimating the state of a dynamic system from noisy, continuous measurements — fusing GPS (accurate, slow, noisy) with IMU (fast, drifting) into a smooth position and velocity estimate. It maintains a model of the system and optimally weights each new measurement against its prediction.

But reach for it deliberately, not reflexively. A Kalman filter is hard to tune (the noise covariance matrices are where projects stall) and hard to debug. For fusing redundant sensors, or picking the freshest trustworthy reading, a transparent heuristic is easier to reason about and often accurate enough. The engineering skill is matching the tool to the problem: use the filter where the dynamics justify it, and a simpler rule everywhere else.

## The order that matters

If I were setting up a real-time fusion pipeline from scratch, the priority order is deliberate:

1. **Get time right first** — synchronized clocks (PTP if high-rate), source timestamps, no re-stamping.
2. **Align by event time** with buffering and watermarks for late data.
3. **Combine** with the simplest method that meets accuracy requirements.
4. **Only then** optimize the filter math.

Almost everyone does this in reverse — they tune the filter first and fight mysterious glitches for weeks before discovering a clock offset. Respect the clock, and the rest of sensor fusion becomes tractable engineering rather than chasing ghosts.

## Operational notes for sensor fusion clock sync real time

Calibrate sensors in factory or lab before field deploy; log temperature-driven clock drift on outdoor units. Fusion filters should degrade gracefully when one sensor drops — never extrapolate positions without explicit uncertainty growth. Replay recorded sensor bags in CI when fusion algorithm changes.

## Notes on sensor fusion clock sync real time

Calibrate sensors in factory or lab before field deploy; log temperature-driven clock drift on outdoor units. Fusion filters should degrade gracefully when one sensor drops — never extrapolate positions without explicit uncertainty growth. Replay recorded sensor bags in CI when fusion algorithm changes.

## Resources

- [IEEE 1588 — Precision Time Protocol (PTP)](https://standards.ieee.org/ieee/1588/6825/)
- [NTP — Network Time Protocol project](https://www.ntp.org/)
- [Linux PTP project (linuxptp)](https://linuxptp.sourceforge.net/)
- [NIST — Time and Frequency Division](https://www.nist.gov/pml/time-and-frequency-division)
- [An Introduction to the Kalman Filter (Welch & Bishop, UNC)](https://www.cs.unc.edu/~welch/kalman/)
- [ROS 2 — time and clock concepts](https://docs.ros.org/en/rolling/Concepts/About-Time.html)

Log per-sensor clock offset in fusion metrics; alert when drift exceeds Kalman filter tolerance.

Review sensor fusion clock sync real time metrics after the next release train on mid-tier mobile devices — regressions that pass lab Lighthouse often fail CrUX field data.

## PTP vs NTP for fusion

Sensor fusion with sub-millisecond alignment needs PTP on supported hardware; NTP jitter breaks lidar-camera calibration. Log per-sensor offset estimates and alert when drift exceeds fusion filter tolerance.
