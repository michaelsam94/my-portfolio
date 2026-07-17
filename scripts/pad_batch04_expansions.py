#!/usr/bin/env python3
"""Ensure batch-04 posts meet MIN_WC by appending topic-specific sections."""
import re, yaml
from pathlib import Path

BLOG = Path("/Users/michael/Desktop/my-portfolio/content/blog")
MIN_WC = 1250
TODAY = "2026-07-17"

SLUGS = [
    "devops-model-serving-batching","devops-model-serving-circuit-breakers","devops-model-serving-edge-deployment",
    "devops-model-serving-ensemble","devops-model-serving-fallback-models","devops-model-serving-kserve",
    "devops-model-serving-multi-model","devops-model-serving-quantization","devops-model-serving-triton",
    "devops-model-serving-warm-pools","devops-monorepo-path-filters","devops-multi-cloud-cost-benchmark",
    "devops-multi-region-capacity","devops-network-partition-simulation","devops-network-policies-default-deny",
    "devops-network-policy-audit","devops-node-pool-rightsizing","devops-observability-cost-control",
    "devops-oncall-runbook-automation","devops-opentelemetry-logs-bridge","devops-otel-auto-instrumentation",
    "devops-otel-collector-pipelines","devops-overcommit-ratio-tuning","devops-pci-dss-scope-reduction",
    "devops-pipeline-cost-allocation",
]

def wc(t):
    return len(re.sub(r'```.*?```','',t,flags=re.S).split())

ADDONS = {
"devops-model-serving-ensemble": """
## Chaos and voter failure injection

Quarterly chaos tests disable one voter at random during load—verify aggregator honors minimum voter policy and latency stays within budget when fastest voter carries load alone. Document unexpected behavior when zero voters respond: fail closed vs cached last-good ensemble output policy differs by product—write it down.

## Heterogeneous hardware voters

When voter A runs GPU and voter B runs CPU, parallel wall-clock latency is max(GPU, CPU) but cost accounting must attribute GPU hours separately—FinOps dashboards split ensemble cost by voter resource class to avoid hiding CPU savings behind GPU spend.

## Feature store consistency

Ensemble voters reading different feature store snapshots produce logically inconsistent scores—pin feature retrieval timestamp or version across voters in single request context propagated via baggage header. Debugging "voter disagreement" often traces to one voter on stale features.
""",
"devops-model-serving-fallback-models": """
## Dual-write metrics during migration

When introducing fallback routing, dual-emit business KPIs tagged by tier for 30 days—executives need side-by-side CSAT not blended average hiding fallback pain.

## Contract tests for timeout budget

CI asserts primary timeout + fallback inference + overhead fits client deadline with 10% margin—prevents deploying fallback path that always loses race against client cancel.

## Primary recovery thundering herd

When primary returns healthy, slow ramp from fallback to primary—instant 100% shift may cold-start primary pool. Use weighted routing over 5 minutes unless primary maintained minReplicas throughout outage.
""",
"devops-model-serving-kserve": """
## RawDeployment vs Serverless mode tradeoffs

Serverless gives scale-to-zero; RawDeployment gives predictable pod identity for GPU locality and simpler debugging. Document which models use which mode in catalog—hybrid cluster needs both patterns without team guessing.

## ClusterLocalGateway vs external ingress

Internal batch jobs should hit cluster-local gateway to avoid hairpin NAT and reduce TLS overhead—separate DNS and rate limits from public predict endpoints sharing same InferenceService backend.

## Model mesh and multi-tenancy

Multiple teams sharing cluster benefit from namespace isolation plus Istio RequestAuthentication on predict paths—prevents one team's load test hitting another's InferenceService name collision in shared staging.
""",
"devops-model-serving-multi-model": """
## License and compliance on shared GPU

Regulated model on shared GPU with marketing model may violate data isolation policy—MIG or dedicated node required despite low utilization. Security review gates colocation proposals not only SRE capacity math.

## Driver and CUDA version skew across node pool

Multiplex pool pinned to driver version—cluster upgrade rolling GPU nodes must drain multiplex pods gracefully with PodDisruptionBudget minAvailable 1 per critical model group.
""",
"devops-model-serving-quantization": """
## Dynamic shapes vs static engines

Dynamic shape ONNX complicates INT8 engine build—may require explicit profile dimensions per bucket. Document supported shape ranges in API docs; reject out-of-range inputs at gateway before wasting GPU on rebuild path.

## A/B FP32 sentinel in production

Permanent 1% FP32 shadow traffic detects quantization drift from data shift—alert when FP32 vs INT8 score KL divergence exceeds weekly baseline band.
""",
"devops-model-serving-triton": """
## GRPC vs HTTP/2 client tuning

High-QPS gRPC clients need channel pooling and appropriate concurrency—one channel per request exhausts file descriptors before GPU saturates. Document client connection guidelines alongside server tuning.

## Model control API access

Model load/unload API powerful—restrict to admin ServiceAccount from CI pipeline only; audit every call. Manual unload during debug caused production outage when automation concurrently promoted version.
""",
"devops-model-serving-warm-pools": """
## Warm pool for serverless activator path

Knative activator buffers requests while pods scale—warm pool reduces activator queue depth during scale-from-zero. Monitor activator request queue metric alongside pod ready time.

## Cost cap on warm standby

Finance sets max warm GPU hours per month—alert when warm pool exceeds cap mid-month unless incident override ticket open.
""",
}

def main():
    results = {}
    for slug in SLUGS:
        path = BLOG / f"{slug}.md"
        text = path.read_text()
        m = re.match(r'^(---\n.*?\n---\n)(.*)$', text, re.DOTALL)
        body = m.group(2)
        for addon in ADDONS.get(slug, []):
            if addon.strip() not in body:
                body = body.rstrip() + "\n" + addon.strip() + "\n"
        while wc(body) < MIN_WC and slug in ADDONS:
            # cycle addons if still short (shouldn't happen often)
            break
        fm = yaml.safe_load(m.group(1)[4:-4])
        fm['dateModified'] = TODAY
        h = yaml.dump(fm, sort_keys=False, allow_unicode=True, default_flow_style=False)
        path.write_text(f"---\n{h}---\n\n{body.strip()}\n")
        results[slug] = wc(body)
    for s, w in results.items():
        flag = "OK" if w >= MIN_WC else "LOW"
        print(f"{w:4d} {flag} {s}")

if __name__ == '__main__':
    main()
