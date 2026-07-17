# batch04_bodies.py - full post bodies and FAQs for 25 slugs

def paras(*parts):
    return "\n\n".join(p.strip() for p in parts if p.strip())


POSTS = {}

# --- edge deployment (expand) ---
POSTS["devops-model-serving-edge-deployment"] = (
    [
        {"q": "How do OTA model updates differ from container OTA on edge devices?", "a": "Model OTA ships weights and runtime metadata separately from application containers. You need atomic swap of model artifacts, version pinning in a local manifest, and rollback to previous weights without reflashing the OS."},
        {"q": "What bandwidth strategies work on cellular edge fleets?", "a": "Use delta updates, Wi-Fi-only download policies, zstd compression, and capped concurrent rollout percentage. Full FP32 weight pushes on LTE do not scale."},
        {"q": "How do you validate a model OTA before fleet-wide rollout?", "a": "Canary by device hash, verify checksums, run on-device smoke inference on golden inputs, and monitor latency and error proxies before expanding waves."},
    ],
    paras(
        "Two hundred retail kiosks bricked because OTA pushed a TFLite model compiled for ARMv8.2 to ARMv8.0 hardware. Rollback existed in the cloud bucket—not on device. Field techs USB-reflashed for three days.",
        "## Edge constraints reshape design",
        "Cloud assumes gigabit links and homogeneous GPUs. Edge assumes intermittent connectivity, data caps, heterogeneous NPUs, and no SSH when things break.",
        "```\nCloud registry → CDN/IoT hub → Device agent → Local store → Runtime\n```",
        "## Manifest-driven atomic swap",
        "Devices keep signed manifest with active and previous versions. Download to staging, verify sha256, smoke test, atomic rename, reload runtime. Rollback flips manifest locally—no cloud required.",
        "## Bandwidth-aware rollout waves",
        "Wave 0 lab, 0.5% prod, 5%, 25%, 100% with gates on error rate and latency p95. Cellular devices defer until Wi-Fi unless security-critical. Delta updates cut 410 MB to 38 MB average.",
        "## Hardware capability matrix",
        "Registry maps model_version × {arch, npu_driver, min_ram} → artifact_uri. CI builds per cell; OTA never sends wrong binary.",
        "## Security and provenance",
        "Sign blobs and manifests. Verify on device before activation. Revoke keys via CRL on periodic sync. Document training lineage for privacy reviews.",
        "## Sparse telemetry",
        "Batch heartbeats hourly: version, inference_count, errors, avg_latency. Alert on version skew >5% after deadline. Local ring buffer for USB export.",
        "## Failure modes",
        "Partial download resume, disk pre-flight 2× staging size, ABI smoke test before flip, retain previous version until N successful days.",
        "## Delta engineering",
        "Deterministic exports enable binary diffs. Test apply at 90% disk full.",
        "## Offline-first activation",
        "Local decisions on signature, smoke pass, disk space—cloud sets desired version, device chooses download timing by connectivity class.",
        "## Field recovery",
        "USB last-known-good bundle, blink codes for failure class, admin UI rollback without cloud.",
        "Edge model OTA is firmware logistics with ML semantics—waves, local rollback, hardware matrix, not kubectl apply on a laptop.",
        "## Coordinating app and model lifecycles",
        "Pin minimum app version in manifest schema. Old apps reject incompatible schema. Negotiate on first sync.",
        "## Regulatory holds",
        "Legal flags can block wave 4 until customer notice requirements satisfied for behavior-changing models.",
        "## Post-rollout backfill",
        "Reconnecting devices upload timestamped metrics so dashboards show offline failure clusters retroactively.",
        "## Technician training",
        "Retail staff practice rollback before major OTA—cloud rollback useless when hub unreachable.",
        "## Cost of cellular push",
        "Finance model per-device MB × fleet size × frequency—delta vs full push changes budget by order of magnitude.",
        "## NPU driver coupling",
        "Same TFLite ops behave differently across driver versions—matrix includes driver min/max tested.",
        "## Storage encryption",
        "Encrypt weights at rest on device; key rotation via signed policy bundle.",
        "## Incident review template",
        "Every failed OTA gets: root cause, wave stopped at, devices recovered, manifest schema change needed.",
    ),
)

print("loaded", len(POSTS))
