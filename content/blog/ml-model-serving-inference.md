---
title: "Model Serving and Inference Patterns"
slug: "ml-model-serving-inference"
description: "Deploy ML models for production inference: REST APIs, batch prediction, model servers (Triton, TorchServe), A/B testing, and monitoring model drift."
datePublished: "2025-06-25"
dateModified: "2025-06-25"
tags: ["DATA", "ML", "Inference", "MLOps"]
keywords: "ML model serving, model inference production, Triton inference server, TorchServe deployment, model A/B testing, model drift monitoring"
faq:
  - q: "Should I serve models via REST API or batch inference?"
    a: "REST API (online inference) for real-time predictions where latency matters — fraud detection, recommendation clicks, search ranking. Batch inference for bulk predictions on a schedule — nightly churn scoring, weekly product categorization. Many systems use both: batch for baseline scores, online for real-time features."
  - q: "When do I need a dedicated model server like Triton instead of embedding the model in my app?"
    a: "Use a model server when you serve multiple models, need GPU sharing across models, require dynamic batching for throughput, or want model hot-swapping without redeploying the application. Embed the model directly for single-model, CPU-only deployments with low traffic."
  - q: "How do I detect model drift in production?"
    a: "Monitor input feature distributions (PSI — Population Stability Index), prediction distribution shifts, and downstream business metrics (click-through rate, conversion). Alert when PSI exceeds 0.2 or business metrics drop below baseline. Log all inputs and predictions for offline analysis."
---

Your data science team trained a fraud detection model with 97% accuracy on the test set. In production, it catches 60% of fraud and flags 15% of legitimate transactions. The model was trained on last year's data. Customer behavior shifted. Feature distributions drifted. Nobody monitored it.

Model serving is where ML meets production engineering. The model file is 5% of the work — the other 95% is building a reliable inference pipeline with proper latency, scaling, monitoring, and rollback capability.

## Online inference: REST API pattern

Wrap the model in an API endpoint:

```python
from fastapi import FastAPI
import joblib
import numpy as np

app = FastAPI()
model = joblib.load("models/fraud_detector_v3.pkl")
scaler = joblib.load("models/scaler_v3.pkl")

@app.post("/predict")
async def predict(features: TransactionFeatures):
    X = scaler.transform([features.to_array()])
    probability = model.predict_proba(X)[0][1]
    return {
        "fraud_probability": float(probability),
        "is_fraud": probability > 0.85,
        "model_version": "v3",
    }
```

Production additions:
- Input validation (Pydantic models catch malformed requests).
- Model version in response (debugging which model scored a transaction).
- Prediction logging (for drift monitoring).
- Timeout and circuit breaker on the endpoint.

## Model servers: Triton and TorchServe

Dedicated model servers handle GPU sharing, dynamic batching, and multi-model serving:

```python
# Triton model repository structure
# models/fraud_detector/
#   config.pbtxt
#   1/model.pt

# config.pbtxt
name: "fraud_detector"
platform: "pytorch_libtorch"
max_batch_size: 64
dynamic_batching {
  preferred_batch_size: [8, 16, 32]
  max_queue_delay_microseconds: 100000
}
instance_group [{ count: 2, kind: KIND_GPU }]
```

```python
import tritonclient.http as triton

client = triton.InferenceServerClient(url="triton:8000")

result = client.infer(
    model_name="fraud_detector",
    inputs=[triton.InferInput("input", [1, 20], "FP32")],
    outputs=[triton.InferRequestedOutput("output")],
)
```

Triton's dynamic batching collects individual requests and processes them as a batch — 3–5× throughput improvement on GPU without client-side batching logic.

## Batch inference pipeline

For scheduled bulk predictions:

```python
import pandas as pd

def batch_predict(input_path: str, output_path: str, model_version: str):
    df = pd.read_parquet(input_path)
    features = preprocess(df)

    predictions = model.predict_proba(features)

    results = df[["customer_id"]].copy()
    results["churn_probability"] = predictions[:, 1]
    results["model_version"] = model_version
    results["scored_at"] = datetime.utcnow()

    results.to_parquet(output_path)
    log_prediction_stats(results)
```

Run on a schedule (Airflow, cron) or triggered by data arrival (S3 event → Lambda → batch job).

## A/B testing models

Route traffic between model versions:

```python
def predict_with_ab_test(features: TransactionFeatures, user_id: str) -> dict:
    variant = ab_test.get_variant("fraud_model_test", user_id)

    if variant == "control":
        result = model_v3.predict(features)
        model_version = "v3"
    else:
        result = model_v4.predict(features)
        model_version = "v4"

    log_prediction(user_id, model_version, result, variant)
    return {**result, "model_version": model_version, "ab_variant": variant}
```

Compare variants on business metrics, not just ML metrics:
- Fraud catch rate (recall on confirmed fraud)
- False positive rate (legitimate transactions flagged)
- Manual review queue size
- Customer complaint rate

## Monitoring model health

Track these in production:

```python
def log_prediction_stats(features, prediction, model_version):
    metrics.record("prediction.latency_ms", elapsed_ms)
    metrics.record("prediction.score", prediction["fraud_probability"])
    metrics.record(f"prediction.count", 1, tags={"model": model_version})

    # Feature drift detection
    for feature_name, value in features.dict().items():
        metrics.record(f"feature.{feature_name}", value)

    # Log for offline analysis
    prediction_log.write({
        "timestamp": datetime.utcnow().isoformat(),
        "model_version": model_version,
        "features": features.dict(),
        "prediction": prediction,
    })
```

Alert conditions:
- **Latency p99 > SLA** — model or infrastructure degradation.
- **Prediction distribution shift** — PSI > 0.2 on key features.
- **Error rate spike** — input validation failures or model exceptions.
- **Business metric drop** — catch rate or conversion declining.

## Model deployment pipeline

```yaml
# CI/CD for model deployment
stages:
  - validate:
      - schema_validation  # input/output schema matches
      - unit_tests         # prediction on known inputs
      - performance_test   # latency benchmark
  - staging:
      - deploy_to_staging
      - integration_test   # end-to-end with feature pipeline
      - shadow_test        # run alongside production, compare outputs
  - production:
      - canary_deploy      # 5% traffic
      - monitor_24h
      - full_rollout OR rollback
```

Never deploy a model directly to 100% traffic. Shadow testing (run new model in parallel, log outputs, do not serve) catches issues before they affect users.

## Batching and dynamic batching

GPU utilization improves dramatically with batching:

```python
# Triton dynamic batching config
dynamic_batching {
  preferred_batch_size: [8, 16, 32]
  max_queue_delay_microseconds: 5000
}
```

Trade 5ms queue delay for 3× throughput on recommendation models. Real-time fraud detection may need batch size 1 — profile per use case.

## Feature store integration

Serving models need consistent features between training and inference:

```python
features = feature_store.get_online_features(
    entity_ids=[user_id],
    features=["purchase_count_30d", "avg_order_value", "last_login_days"],
)
prediction = model.predict(features.to_dict())
```

Training-serving skew is the #1 silent model degradation cause. Log feature values with predictions for drift detection.

## Autoscaling inference

Scale on GPU utilization and queue depth, not CPU:

```yaml
# Kubernetes HPA custom metric
- type: Pods
  pods:
    metric:
      name: inference_queue_depth
    target:
      type: AverageValue
      averageValue: "10"
```

Cold start latency on scale-up matters — keep minimum replicas > 0 for latency-sensitive paths. Pre-warm models on pod startup.

Pair with [feature stores for ML](https://blog.michaelsam94.com/feature-stores-ml/) for online/offline feature consistency.

## Common production mistakes

Teams get ml model serving inference wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of ml model serving inference fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Debugging and triage workflow

When ml model serving inference misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [NVIDIA Triton Inference Server](https://developer.nvidia.com/triton-inference-server)
- [PyTorch TorchServe](https://pytorch.org/serve/)
- [Google ML Model Monitoring guide](https://cloud.google.com/architecture/mlops-continuous-delivery-and-automation-pipelines-in-machine-learning)
- [Evidently AI: model monitoring](https://docs.evidentlyai.com/)
- [AWS SageMaker model deployment patterns](https://docs.aws.amazon.com/sagemaker/latest/dg/model-deploy.html)
