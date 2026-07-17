---
title: "Anomaly Detection Metrics That Actually Reflect Production Quality"
slug: "rag-anomaly-detection-metrics"
description: "Precision-recall on rare events, point-adjusted F1 pitfalls, and SLO-friendly alerting for time-series and log anomalies."
datePublished: "2025-10-19"
dateModified: "2026-07-17"
tags:
  - "Observability"
  - "SRE"
  - "Machine Learning"
keywords: "anomaly detection, metrics, precision recall, time series"
faq:
  - q: "Why is accuracy misleading for anomaly detection?"
    a: "With 99.9% normal data, a always-normal classifier hits 99.9% accuracy while catching zero incidents — use precision, recall, and detection delay instead."
  - q: "What is point adjustment and why avoid it?"
    a: "Point adjustment gives credit for detecting any point in an incident window — it inflates F1 versus operational need to detect early within SLO minutes."
  - q: "How should alert fatigue be measured?"
    a: "Track alerts per on-call shift, mute rate, and percentage leading to incidents — high mute rate means metric threshold or model is miscalibrated."
---
Anomaly detection demos love clean synthetic spikes; production metrics are messy, seasonal, and expensive to label. Choosing the wrong evaluation metric ships models that look brilliant offline and page engineers every Sunday. This article covers labeling strategies, detection delay, cost-weighted scoring, and how to tie anomaly quality to incident outcomes — not just ROC curves on balanced datasets.

## Labeling incidents versus anomalies

Define ground truth from incident tickets with start/end timestamps — not every metric blip is an incident. Align labels with user-visible pain to avoid optimizing irrelevant spikes.

Export alert outcomes to warehouse weekly; join to incident IDs for labeled precision recall that reflects operational truth, not analyst memory in spreadsheets.

## Detection delay as first-class metric

An anomaly found twenty minutes after customer impact failed operationally even if point-adjusted F1 looks perfect. Report median and p95 delay from incident start to first alert.

## Precision-recall at operational alert rates

Fix alert budget: max N pages per week per service. Tune threshold to maximize recall at that precision floor — not maximize F1 on balanced holdout.

## Seasonality and changepoint blind spots

Models ignoring holidays misfire predictably — bake calendars or use robust seasonal decomposition. After deploys, suppress alerts until new baseline stabilizes or use change-aware training windows.

## Multivariate versus univariate tradeoffs

Univariate per metric is interpretable; multivariate catches correlated failures but harder to explain. Hybrid: multivariate score with dimensional attribution for runbooks.

## Closing the loop with incident review

Post-incident tag alerts true/false positive; feed weekly into threshold reviews. Metrics without feedback rot within a quarter.

## Bridging ML metrics to on-call trust

Survey on-call quarterly: percent of anomaly alerts actioned versus muted. If mute rate exceeds 40%, threshold or model needs recalibration regardless of offline F1. Trust metrics matter as much as statistical metrics for long-lived detection systems.

## Seasonality in metric baselines

Weekly seasonality breaks naive z-score — use STL decomposition or Prophet baseline band. Black Friday requires pre-adjusted bounds or alert suppression windows documented with fraud ops approval.

## Cardinality and metric explosion

Anomaly per unique tag combination explodes alert volume — aggregate to service level first, drill down on anomaly confirmation. High cardinality labels belong in traces not metric keys.

Evaluate anomaly systems on detection delay, alert budget, and incident-linked labels — not accuracy on imbalanced toy data. Models earn trust when on-call agrees alerts were worth waking up for.

Reconcile anomaly alert timestamps with incident commander timeline in postmortem — detection delay metric only improves when measured honestly.

Design review checklist item 1 for anomaly detection metrics: validate failure modes, owner, and rollback before merge to main.

Observability gap 1 in anomaly detection metrics often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 1 for anomaly detection metrics should assert behavior under duplicate requests and slow dependencies.

Runbook section 1 for anomaly detection metrics documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 2 for anomaly detection metrics: validate failure modes, owner, and rollback before merge to main.

Observability gap 2 in anomaly detection metrics often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 2 for anomaly detection metrics should assert behavior under duplicate requests and slow dependencies.

Runbook section 2 for anomaly detection metrics documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 3 for anomaly detection metrics: validate failure modes, owner, and rollback before merge to main.

Observability gap 3 in anomaly detection metrics often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 3 for anomaly detection metrics should assert behavior under duplicate requests and slow dependencies.

Runbook section 3 for anomaly detection metrics documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 4 for anomaly detection metrics: validate failure modes, owner, and rollback before merge to main.

Observability gap 4 in anomaly detection metrics often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 4 for anomaly detection metrics should assert behavior under duplicate requests and slow dependencies.

Runbook section 4 for anomaly detection metrics documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 5 for anomaly detection metrics: validate failure modes, owner, and rollback before merge to main.

Observability gap 5 in anomaly detection metrics often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 5 for anomaly detection metrics should assert behavior under duplicate requests and slow dependencies.

Runbook section 5 for anomaly detection metrics documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 6 for anomaly detection metrics: validate failure modes, owner, and rollback before merge to main.

Observability gap 6 in anomaly detection metrics often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 6 for anomaly detection metrics should assert behavior under duplicate requests and slow dependencies.

Runbook section 6 for anomaly detection metrics documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 7 for anomaly detection metrics: validate failure modes, owner, and rollback before merge to main.

Observability gap 7 in anomaly detection metrics often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 7 for anomaly detection metrics should assert behavior under duplicate requests and slow dependencies.

Runbook section 7 for anomaly detection metrics documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 8 for anomaly detection metrics: validate failure modes, owner, and rollback before merge to main.

Observability gap 8 in anomaly detection metrics often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 8 for anomaly detection metrics should assert behavior under duplicate requests and slow dependencies.

Runbook section 8 for anomaly detection metrics documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 9 for anomaly detection metrics: validate failure modes, owner, and rollback before merge to main.

Observability gap 9 in anomaly detection metrics often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 9 for anomaly detection metrics should assert behavior under duplicate requests and slow dependencies.

Runbook section 9 for anomaly detection metrics documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 10 for anomaly detection metrics: validate failure modes, owner, and rollback before merge to main.

Observability gap 10 in anomaly detection metrics often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 10 for anomaly detection metrics should assert behavior under duplicate requests and slow dependencies.

Runbook section 10 for anomaly detection metrics documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 11 for anomaly detection metrics: validate failure modes, owner, and rollback before merge to main.

Observability gap 11 in anomaly detection metrics often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 11 for anomaly detection metrics should assert behavior under duplicate requests and slow dependencies.

Runbook section 11 for anomaly detection metrics documents escalation when primary and secondary on-call roles are unreachable.

## Field checklist for anomaly detection metrics

Before calling this done in production, confirm you can measure success and failure independently: a positive metric (throughput, conversion, recall) and a negative one (abuse rate, false accepts, lag). Add one alert that pages on the negative metric and one dashboard panel for the positive. Run a staging drill that forces the failure mode — timeout, poison input, or partial outage — and capture the exact commands in the runbook next to the config. If the drill takes longer than fifteen minutes to execute, simplify the recovery path before you need it at 2am.
