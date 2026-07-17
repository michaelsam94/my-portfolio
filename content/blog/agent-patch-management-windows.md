---
title: "AI Agents: Patch Management Windows"
slug: "agent-patch-management-windows"
description: "Design Windows patch maintenance windows with ring deployments, reboot orchestration, WSUS/Intune integration, and exception workflows that survive Patch Tuesday and audit."
datePublished: "2025-11-08"
dateModified: "2025-11-08"
tags: ["AI", "Agent", "Patch"]
keywords: "Windows patch management, maintenance windows, WSUS, Intune, Patch Tuesday, ring deployment, reboot orchestration"
faq:
  - q: "How long should a standard Windows maintenance window be?"
    a: "Four to six hours for servers with staged reboots; two to three hours for workstations if updates pre-download during business hours. Budget extra time on Patch Tuesday months with cumulative updates exceeding 500 MB or when .NET or SQL co-reboots are bundled."
  - q: "Should critical out-of-band patches bypass the window?"
    a: "Yes, but through a documented emergency lane: 24-hour change advisory, isolated ring install first, automated rollback snapshot for VMs, and post-install verification script—not ad-hoc manual installs on production without evidence."
  - q: "WSUS vs Intune for hybrid fleets?"
    a: "Use WSUS or Configuration Manager for on-prem domain-joined servers and legacy apps; Intune/WUfB for cloud-first laptops. Hybrid orgs sync approval metadata from one source of truth to avoid double-patching or conflicting deferrals."
  - q: "How do you handle servers that must never reboot unplanned?"
    a: "Cluster rolling updates, maintenance orchestration with pre/post hooks, and explicit reboot budgets per service tier. Machines without a defined reboot owner should not receive automatic forced restarts—treat that as a configuration defect."
---
Patch Tuesday arrives whether your change board is ready or not. The difference between teams that sleep through it and teams that page at 2 a.m. is not faster WSUS sync—it is maintenance windows engineered around reboot physics, application warm-up time, and the reality that a SQL cluster cannot tolerate three nodes rebooting because someone checked "auto approve critical."

This article focuses on Windows patch management windows: how to schedule them, how to deploy in rings, how to automate compliance evidence, and where exceptions belong.

## The anatomy of a maintenance window

A maintenance window is four coordinated intervals, not a single calendar invite:

1. **Pre-stage** — updates download, disk space verified, snapshot or backup confirmed, dependency owners notified.
2. **Install** — packages apply; services may continue running until reboot.
3. **Reboot** — OS and sometimes application restarts; this is where SLAs break.
4. **Validate** — smoke tests, health checks, synthetic transactions, manual sign-off for tier-0 systems.

Skipping validation turns "patched" into "we hope patched." Compliance scanners report KB present; users report checkout down.

Document each interval with owner, max duration, and rollback trigger. Example for a payment adjacency app server:

| Interval | Duration | Owner | Rollback trigger |
|----------|----------|-------|------------------|
| Pre-stage | T-24h to T-2h | Platform | Snapshot failure |
| Install | 30 min | Automation | Install error >5% |
| Reboot | 15 min / node | Orchestrator | Health check fail 3x |
| Validate | 45 min | App on-call | Error rate > baseline +2σ |

## Ring-based deployment model

Rings contain risk, not just delay. A typical five-ring model:

- **Ring 0 — Patch lab** — VMs mirroring production roles; install everything first; run automated and manual test suites.
- **Ring 1 — IT workstations** — diverse hardware; catches driver and VPN issues.
- **Ring 2 — Non-critical servers** — internal tools, CI runners, staging mirrors.
- **Ring 3 — Production cohort A** — 10–20% of each role, geographically spread.
- **Ring 4 — Production cohort B** — remainder after 24–48h bake time with clean metrics.

Membership is dynamic via AD security groups or Intune device filters—never hard-code hostnames in scripts without a group backing them.

```powershell
# Example: trigger install for Ring 2 during window; defer reboot until orchestrator
$ringGroup = "Patch-Ring-2-Servers"
$deadline  = (Get-Date).AddHours(4)

Invoke-WUJob -ComputerName (Get-ADGroupMember $ringGroup | Select -Expand Name) `
  -Download `
  -Install `
  -IgnoreReboot `
  -Deadline $deadline `
  -Verbose
```

Use `-IgnoreReboot` during install phase so you control restart order. For clusters, orchestrate one node at a time with quorum checks between reboots.

## WSUS, Intune, and not both fighting

**WSUS / Configuration Manager** excels at server approval workflows, third-party update catalogs, and air-gapped networks. Sync schedule should complete 48 hours before your window so approvals propagate to downstream replicas.

**Windows Update for Business / Intune** excels at cloud-managed devices, delivery optimization, and user experience controls (active hours, restart grace).

Hybrid pitfalls:

- Same machine receiving policy from SCCM and Intune with conflicting deferrals
- Dual reboot prompts on laptops enrolled in both MDM and domain GPO
- Server Core missing UI feedback—rely on event logs (`Microsoft-Windows-WindowsUpdateClient/Operational`)

Pick one authority per device class. Document it in CMDB. Auditors ask.

## Automating compliance and evidence

Scanning tools report CVE exposure; patch windows prove remediation in time. Collect:

- `Get-HotFix` output or `systeminfo` before/after
- Windows Update agent logs for error codes (`0x80240020` = still downloading)
- Orchestrator run ID tied to change ticket

```powershell
function Export-PatchComplianceReport {
  param([string[]]$ComputerNames, [string]$ChangeTicket)

  $results = foreach ($cn in $ComputerNames) {
    $session = New-CimSession -ComputerName $cn -ErrorAction SilentlyContinue
    if (-not $session) {
      [pscustomobject]@{ Computer = $cn; Status = "Unreachable"; Ticket = $ChangeTicket }
      continue
    }
    $hotfixes = Get-CimInstance -CimSession $session -ClassName Win32_QuickFixEngineering
    [pscustomobject]@{
      Computer     = $cn
      Status       = "Reachable"
      LatestKB     = ($hotfixes | Sort-Object InstalledOn -Descending | Select -First 1).HotFixID
      InstalledOn  = ($hotfixes | Sort-Object InstalledOn -Descending | Select -First 1).InstalledOn
      Ticket       = $ChangeTicket
    }
  }
  $results | Export-Csv -Path "\\fileserver\patch-reports\$ChangeTicket.csv" -NoTypeInformation
}
```

Attach CSV and dashboard screenshots to the change record. "We ran Windows Update" is not evidence.

## Reboot orchestration and warm-up

Applications lie about readiness. IIS may accept connections while app pools still spin up; SQL AG role may not be primary yet. Standardize post-reboot scripts per role:

```powershell
# Post-reboot validation hook — register as Scheduled Task run once at startup
$checks = @(
  { (Get-Service W3SVC).Status -eq 'Running' },
  { (Invoke-WebRequest http://localhost/health -UseBasicParsing).StatusCode -eq 200 }
)

foreach ($check in $checks) {
  $ok = $false
  for ($i = 0; $i -lt 12; $i++) {
    if (& $check) { $ok = $true; break }
    Start-Sleep -Seconds 10
  }
  if (-not $ok) {
    Write-EventLog -LogName Application -Source PatchValidation -EventId 5001 -EntryType Error `
      -Message "Post-reboot validation failed"
    exit 1
  }
}
```

Failed validation should alert the orchestrator to halt the ring expansion—not proceed to the next node.

## Exception workflows that prevent shadow IT

Some servers cannot patch on schedule: legacy app vendor certification lag, regulatory freeze, hardware too old for current kernel. Exceptions require:

- Named business owner and expiry date (max 90 days)
- Compensating controls (network segmentation, increased monitoring)
- Entry in CMDB `patch_exception` field visible to scanners

Expired exceptions auto-page; no silent renewals. Teams that skip this accumulate "permanent temporary" servers—the ones ransomware operators love.

## Patch Tuesday game day

Two weeks before: review Microsoft's preview notes and CVE priority. One week before: Ring 0 install dry run. Day of: change bridge with representatives from network, storage, DBA, and app teams—even if most months are quiet.

Bridge runbook one-pager:

1. Confirm Ring 0 success in last 7 days
2. Start Ring 3 install at window open; monitor error rate dashboard
3. Halt expansion if install failures >2% or critical synthetic fails
4. Complete validation before closing change ticket
5. Publish internal summary: KBs deployed, issues hit, carry-forward items

Quiet months build the habit for loud months—when a zero-day drops on a Friday.

## Workstation-specific UX

Users tolerate restarts when updates finished downloading before they clicked "Restart now." Configure:

- Automatic download during business hours
- Active hours enforced via GPO/Intune
- Restart grace period with clear deadline
- BitLocker PIN prompts documented for FileVault-equivalent BitLocker scenarios

VDI pools patch at logout or nightly refresh—never during peak login surge.

## Coordinating with application owners

Database patches are not OS patches, but reboots affect both. Maintain a **dependency calendar** shared with DBAs and app owners: SQL Server CU installs, .NET runtime updates, and kernel patches may each require different reboot ordering. A window that reboots OS before SQL failover completes leaves AG listeners offline.

Send pre-window notifications with: expected reboot count, whether services will bounce without OS restart, and validation endpoints owners should watch. Silence breeds pages from teams who were not informed.

For containers on Windows nodes, distinguish **node patching** from **image updates**. Patching the host still drains pods; coordinate with Kubernetes cordon/drain scripts:

```powershell
kubectl cordon $node
kubectl drain $node --ignore-daemonsets --delete-emptydir-data --timeout=30m
# Apply OS updates + reboot
kubectl uncordon $node
```

Skipping cordon produces the classic failure mode: two replicas on the same node reboot simultaneously.

## Measuring window success

Track mean time to patch (MTTP) from Microsoft release to Ring 4 completion, percentage of fleet compliant at window close, and unplanned reboot rate outside windows. MTTP creeping upward usually means approval bottlenecks or fear after a bad month—not technical sync issues.

Windows patch management is change management with binaries: rings contain blast radius, windows bound reboot chaos, automation produces evidence, and exceptions expire. Build those four pillars and Patch Tuesday becomes routine instead of ritual panic.

## Resources

- [Microsoft Learn: Windows Update for Business deployment guide](https://learn.microsoft.com/en-us/windows/deployment/update/waas-manage-updates-wufb)
- [Microsoft Learn: WSUS and Configuration Manager software updates](https://learn.microsoft.com/en-us/mem/configmgr/sum/)
- [CIS Microsoft Windows Server Benchmark](https://www.cisecurity.org/benchmark/microsoft_windows_server)
- [Microsoft Security Update Guide](https://msrc.microsoft.com/update-guide)
- [NIST SP 800-40 Rev. 4: Guide to Enterprise Patch Management](https://csrc.nist.gov/publications/detail/sp/800-40/rev-4/final)
