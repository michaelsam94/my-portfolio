---
title: "On-Call Runbook Automation"
slug: "observability-oncall-runbook-automation"
description: "Attach runbooks to alerts automatically and execute safe remediation scripts from PagerDuty or Grafana OnCall."
datePublished: "2026-01-20"
dateModified: "2026-07-17"
tags:
  - "DevOps"
  - "Observability"
  - "SRE"
  - "Operations"
keywords: "runbook automation, pagerduty runbook, automated remediation, on-call runbooks, sre runbook as code"
faq:
  - q: "What should be automated vs manual?"
    a: "Automate read-only diagnostics and safe remediations (scale +1). Manual: database failover, irreversible actions."
  - q: "How do I prevent automation making incidents worse?"
    a: "Idempotent actions, rate limits, dry-run in staging, human approval for destructive steps."
  - q: "Where should runbooks live?"
    a: "Executable runbooks in git with CI validation—not rot-prone wikis."
---

Alert linked to Confluence draft from 2019. On-call bounced Redis cluster-wide and doubled the outage. Runbook automation attaches current executable guidance and automates boring verification steps panic skips.

## Runbook structure

Impact, auto-diagnose script, optional auto-remediate with approval, manual steps, escalation—with stable `runbook_id` in alert annotations.

## Webhooks

PagerDuty incident → GitHub Actions diagnose script → Slack post with output attached to incident.

## ChatOps

`:rollback:` reaction runs kubectl rollout undo with audit log.

## Maturity

Level 0 static URL → Level 1 diagnose webhook → Level 2 approved remediate. Level 1 alone cuts MTTR measurably.


## Runbook metrics in incident review

Post-incident: was `runbook_id` attached to alert? Did diagnose script run? Track `% pages with automated diagnosis completed in 5 min` as operational KPI.

## Security of remediation scripts

Remediate scripts run with production credentials—store in locked repo, require CODEOWNERS approval, audit every execution to SIEM with incident id.

## Staged automation maturity

Level 0: static URL
Level 1: diagnose webhook
Level 2: ChatOps approval remediate
Level 3: auto-remediate with rollback on error rate increase

Most teams stall at Level 1 for years— that alone cuts MTTR measurably.

## Runbook localization

Global on-call may need runbook sections in multiple languages for follow-the-sun—automate diagnose script output in English with machine translation disclaimer for internal tiers, not customer-facing text.

## Integration with status page

Auto-update status page component when synthetic check fails AND runbook confirms user impact—semi-automated with human ack prevents premature public incident declaration on flaky synthetic.

## Measuring automation ROI

Track mean time from page to first automated diagnose output completion—target under 60 seconds. If diagnose scripts exist but nobody triggers them, problem is discoverability not automation—embed script output in default PagerDuty incident note via webhook rather than requiring manual script invocation.

Version runbook scripts with git tags matching service releases so postmortems reference exact diagnose logic used during incident, not moving main branch head.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.

## Production review cadence

Revisit dashboards and alert thresholds after every deploy affecting this observability surface. Weekly on-call review should include one exemplar trace or log linked from a metric spike—paper metrics without exemplars train teams to ignore charts.
