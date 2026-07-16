---
title: "Practical Cloud Cost Optimization"
slug: "finops-cloud-cost-optimization"
description: "Cut cloud spend without guessing: rightsizing from utilization data, storage lifecycle rules, reserved capacity math, and the FinOps review cadence that keeps savings from eroding."
datePublished: "2024-09-01"
dateModified: "2024-09-01"
tags: ["DevOps", "FinOps"]
keywords: "cloud cost optimization, FinOps, rightsizing, AWS Cost Explorer, reserved instances, cloud waste"
faq:
  - q: "What is the fastest way to reduce cloud costs?"
    a: "Start with idle and oversized compute: instances below 20% average CPU for two weeks are prime rightsizing candidates. Turn off dev and staging environments outside business hours with scheduled scaling or stop/start automation. Review unattached EBS volumes and old snapshots next—they often account for 5–15% of monthly spend with zero business value."
  - q: "How often should teams review cloud spending?"
    a: "Run a lightweight weekly anomaly check (Cost Anomaly Detection or a simple budget alert) and a deeper monthly FinOps review with engineering owners. Quarterly, revisit commitment strategies—Savings Plans and Reserved Instances—against actual usage curves. Savings erode quickly when teams launch new services without tagging or sizing discipline."
  - q: "Is reserved capacity always worth buying?"
    a: "Only for workloads with stable baseline usage over 6–12 months. Buy coverage for the minimum always-on footprint, not peak. Mix On-Demand and Spot for burst. Over-committing to RIs you outgrow creates lock-in; under-committing leaves 20–40% on the table for steady-state fleets."
---

Last quarter I audited a client's AWS bill and found $14,000/month in compute that averaged 8% CPU utilization. Nobody had maliciously overspent—they'd copied production instance sizes into staging three years ago and never looked back. Cloud cost optimization isn't about turning off lights; it's about matching capacity to actual demand and making spend visible before it compounds.

## Start with visibility, not cuts

You can't optimize what you can't attribute. Before rightsizing anything, enforce a tagging policy: `Environment`, `Team`, `Service`, and `CostCenter` at minimum. AWS Cost Allocation Tags, GCP labels, and Azure cost tags must be activated in the billing console—tags on resources don't appear in reports until you flip that switch.

Export daily cost and usage reports (CUR on AWS) into Athena or BigQuery. A simple query grouping by tag and instance type reveals the top ten offenders within an hour:

```sql
SELECT
  line_item_resource_id,
  product_instance_type,
  SUM(line_item_unblended_cost) AS cost
FROM cur_report
WHERE line_item_product_code = 'AmazonEC2'
  AND line_item_usage_start_date >= DATE '2024-08-01'
GROUP BY 1, 2
ORDER BY cost DESC
LIMIT 20;
```

Pair cost data with utilization. CloudWatch `CPUUtilization`, `NetworkIn`, and memory metrics from the CloudWatch agent tell you whether an `m5.2xlarge` is justified or a `t3.medium` would suffice.

## Rightsizing compute

Rightsizing is the highest-ROI lever for most teams. AWS Compute Optimizer (and third-party tools like Vantage or CloudHealth) recommend instance sizes based on historical metrics. My rule of thumb:

- **Avg CPU < 20% and max < 60%** over 14 days → downsize one or two sizes.
- **Memory pressure** (swap, OOM kills) → upsize or move to a memory-optimized family.
- **Bursty workloads** → `t3`/`t4g` burstable or Spot for batch jobs.

Don't rightsizing production during peak season without change windows. Staging is fair game immediately.

```bash
# AWS CLI: list instances with low average CPU (simplified check)
aws cloudwatch get-metric-statistics \
  --namespace AWS/EC2 \
  --metric-name CPUUtilization \
  --dimensions Name=InstanceId,Value=i-0abc123 \
  --start-time 2024-08-01T00:00:00Z \
  --end-time 2024-08-15T00:00:00Z \
  --period 86400 \
  --statistics Average
```

Document every change. A spreadsheet linking instance ID → old type → new type → monthly savings prevents backsliding when someone "just needs more headroom."

## Storage and data transfer

EBS volumes attached to terminated instances, old AMIs, and S3 buckets without lifecycle policies are silent budget killers. Run monthly:

1. **Unattached volumes** — snapshot if needed, then delete.
2. **S3 lifecycle** — transition logs to Glacier after 30 days, expire after 90.
3. **Cross-AZ traffic** — co-locate tightly coupled services or use VPC endpoints for S3/DynamoDB to avoid NAT gateway charges.

Data transfer out to the internet is often the second-largest line item after compute. CloudFront or a CDN in front of static assets reduces origin egress. For multi-region setups, ask whether you need active-active or if read replicas in one region suffice.

## Commitment strategies

On-Demand is the most expensive price tier. Once baseline usage is stable:

| Strategy | Best for | Typical savings |
|----------|----------|-----------------|
| Compute Savings Plans (AWS) | Flexible instance family/family changes | 30–50% |
| Reserved Instances | Fixed instance type, 1–3 year term | 40–60% |
| CUDs (GCP) / RIs (Azure) | Same, per cloud | Similar |

Buy commitments for the **floor** of your usage graph, not the ceiling. Keep 20–30% of peak capacity On-Demand or Spot. Revisit quarterly—containerization and Graviton migrations can invalidate old RI purchases.

## Automation and guardrails

Manual optimization doesn't scale. Implement:

- **Budget alerts** at 80% and 100% of monthly forecast per team tag.
- **SCPs or org policies** blocking `*.2xlarge` launches in dev accounts without approval.
- **Scheduled scaling** for non-prod (EventBridge → Lambda → stop RDS/Aurora dev clusters at 7 PM).
- **Instance scheduling tools** (AWS Instance Scheduler, homegrown Terraform).

FinOps succeeds when engineers see cost in the same dashboards they use for latency and errors. Export billing data to Grafana or Datadog and put a weekly cost-per-request metric next to p99 latency.

## The monthly review ritual

Block 60 minutes monthly with service owners. Agenda:

1. Top 5 cost deltas vs. prior month (what changed?).
2. Untagged spend percentage (target < 5%).
3. Rightsizing recommendations still open.
4. Commitment coverage vs. actual On-Demand hours.
5. One experiment for next month (Graviton trial, Spot for CI runners, etc.).

Savings stick when ownership is clear. Tagging without accountability is theater.

### Graviton and architecture migrations

AWS Graviton (arm64) instances cost 20% less than comparable x86 with equal or better performance for many workloads. Before migrating production, benchmark your stack—some native dependencies lack arm builds. I run parallel staging fleets for two weeks comparing p99 latency and error rates. Containerized services migrate easiest; legacy AMIs with compiled binaries need more validation.

Use AWS Compute Optimizer's Graviton recommendation flag. Mixed-arch Auto Scaling Groups let you roll back instantly if arm instances underperform on specific jobs. Document savings separately in FinOps reports—Graviton migrations often deliver 15–25% compute reduction without behavioral changes from engineering teams.

Review RDS and ElastiCache idle instances separately from EC2—databases left running in dev accounts overnight often exceed compute waste. Enable Performance Insights, right-size instance class, and consider Aurora Serverless v2 for variable workloads. Snapshot before downsizing; storage auto-scaling can inflate bills even after instance class drops.

Tag every resource at creation with team and environment — retroactive tagging projects fail because orphaned resources outnumber tagged ones 3:1.

## Resources

- [AWS Cost Optimization Hub](https://docs.aws.amazon.com/cost-management/latest/userguide/cost-optimization-hub.html)
- [AWS Well-Architected Cost Optimization Pillar](https://docs.aws.amazon.com/wellarchitected/latest/cost-optimization-pillar/welcome.html)
- [FinOps Foundation Framework](https://www.finops.org/framework/)
- [Google Cloud Cost Optimization Best Practices](https://cloud.google.com/architecture/framework/cost-optimization)
- [Azure Cost Management Documentation](https://learn.microsoft.com/en-us/azure/cost-management-billing/)
