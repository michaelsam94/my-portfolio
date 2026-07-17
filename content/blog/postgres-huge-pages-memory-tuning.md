---
title: "Postgres Huge Pages Memory Tuning"
slug: "postgres-huge-pages-memory-tuning"
description: "Configure Linux huge pages for Postgres shared_buffers — reduce TLB misses, calculate vm.nr_hugepages, and diagnose allocation failures."
datePublished: "2026-02-23"
dateModified: "2026-07-17"
tags:
  - "PostgreSQL"
  - "Backend"
  - "Database"
keywords: "huge pages postgres, shared_buffers tuning, TLB, vm.nr_hugepages, hugetlbfs"
faq:
  - q: "How much performance improvement do huge pages typically provide?"
    a: "On large shared_buffers configurations (8 GB+), huge pages reduce TLB miss overhead by 5–15% on memory-intensive workloads — bulk scans, large hash joins, buffer-heavy OLTP. On small instances with 1–2 GB shared_buffers, the benefit is negligible and setup overhead may not justify the effort."
  - q: "Why does Postgres log 'huge pages disabled' even when I configured them?"
    a: "The kernel did not reserve enough huge pages at boot, or postgres user lacks memlock permission. Check vm.nr_hugepages versus required count, verify HugePages_Total in /proc/meminfo is non-zero, and ensure ulimit -l allows locking (often requires memlock unlimited in systemd or /etc/security/limits.conf)."
  - q: "Should I use transparent huge pages instead of explicit huge pages?"
    a: "Disable transparent huge pages (THP) for Postgres — they cause latency spikes due to kernel defragmentation and compaction. Use explicit hugetlbfs huge pages with huge_pages=try or huge_pages=on in postgresql.conf instead."
---

Postgres relies heavily on shared memory for `shared_buffers`, the buffer pool caching data pages across backend processes. On Linux, the default 4 KB page size means a 16 GB buffer pool maps through thousands of Translation Lookaside Buffer (TLB) entries. TLB misses force page table walks — invisible in query plans but measurable in CPU profiles. **Huge pages** (typically 2 MB on x86) reduce TLB pressure by mapping the same memory with far fewer entries.

This article covers when huge pages matter, how to calculate and reserve them, Postgres configuration, and the troubleshooting path when allocation silently fails.

## Memory layout and TLB pressure

Normal pages:

```
16 GB shared_buffers ÷ 4 KB/page = 4,194,304 page mappings
Each TLB miss → page table walk → latency
```

Huge pages (2 MB):

```
16 GB ÷ 2 MB = 8,192 mappings (512× reduction)
Fewer TLB entries cover the same memory
```

Benefit scales with `shared_buffers` size and workload memory access patterns. CPU-bound queries scanning large portions of shared_buffers see the most improvement.

## Transparent vs explicit huge pages

Linux offers two mechanisms:

| Type | Control | Postgres recommendation |
| --- | --- | --- |
| **Transparent Huge Pages (THP)** | Kernel auto-promotes 4KB → 2MB | **Disable** — causes latency jitter |
| **Explicit (hugetlbfs)** | Admin pre-reserves at boot | **Use** — predictable, no compaction stalls |

Disable THP:

```bash
# Immediate
echo never | sudo tee /sys/kernel/mm/transparent_hugepage/enabled
echo never | sudo tee /sys/kernel/mm/transparent_hugepage/defrag

# Persistent via grub or tuned profile
```

Postgres documentation explicitly recommends disabling THP.

## Calculating vm.nr_hugepages

Huge page size on x86 Linux is typically 2 MB:

```bash
grep Hugepagesize /proc/meminfo
# Hugepagesize:       2048 kB
```

Formula:

```
nr_hugepages = ceil(shared_buffers / Hugepagesize) + overhead

Example: shared_buffers = 8 GB = 8192 MB
8192 / 2 = 4096 huge pages
Add ~10% overhead: ~4500
```

Postgres uses huge pages only for `shared_buffers` — not for work_mem, maintenance_work_mem, or per-backend private memory.

Calculate from Postgres perspective:

```sql
SHOW shared_buffers;  -- e.g. 8GB
```

```bash
# Convert to pages (2MB each) + small overhead
echo $(( 8192 / 2 + 64 ))  # = 4160
```

Set at runtime (lost on reboot):

```bash
sudo sysctl -w vm.nr_hugepages=4160
```

Persistent (`/etc/sysctl.d/99-postgres-hugepages.conf`):

```
vm.nr_hugepages = 4160
```

Verify reservation:

```bash
grep -E 'HugePages_Total|HugePages_Free|Hugepagesize' /proc/meminfo
# HugePages_Total should equal configured nr_hugepages
# HugePages_Free decreases when Postgres starts
```

## Postgres configuration

postgresql.conf:

```
shared_buffers = 8GB
huge_pages = try    # use if available, start anyway if not (PG 13+ default try)
# huge_pages = on   # fail to start if huge pages unavailable — strict
# huge_pages = off  # disable explicitly
```

Startup log confirmation:

```
LOG:  using shared memory segment of size 8589934592 bytes with 4160 pages of size 2097152 bytes
```

Failure log:

```
LOG:  could not map shared memory segment: Cannot allocate memory
LOG:  shared memory segment will not use huge pages
```

With `huge_pages = on`, startup fails entirely if allocation fails. Use `try` during initial setup, switch to `on` once confirmed stable.

## memlock limits

Postgres must lock huge page memory. Default ulimit for locked memory is often 64 KB — insufficient.

Check:

```bash
ulimit -l
```

Configure unlimited for postgres user:

`/etc/security/limits.conf`:

```
postgres soft memlock unlimited
postgres hard memlock unlimited
```

systemd override (`/etc/systemd/system/postgresql.service.d/hugepages.conf`):

```ini
[Service]
LimitMEMLOCK=infinity
```

Reload and restart:

```bash
sudo systemctl daemon-reload
sudo systemctl restart postgresql
```

## Container and cloud considerations

**Docker/Kubernetes**: Huge pages require node-level hugetlbfs mounts and resource limits:

```yaml
resources:
  limits:
    hugepages-2Mi: 8Gi
  requests:
    hugepages-2Mi: 8Gi
```

Mount hugetlbfs in pod spec or use node pre-configuration. Managed Kubernetes (EKS, GKE) requires node pool configuration for huge pages — not available on all instance types.

**RDS / Cloud SQL**: Huge pages are managed by the provider — not user-configurable. Benefit is internal to the platform.

**Bare metal / self-managed VMs**: Full control — best candidate for huge page tuning.

## Sizing shared_buffers with huge pages in mind

Huge pages are reserved at kernel level — wasted if Postgres does not use them:

```
Reserved: 4160 × 2 MB = 8.3 GB locked in huge pages
Actual shared_buffers: 4 GB
Waste: ~4 GB of locked memory unavailable to OS
```

Match `shared_buffers` to reserved huge pages. Increasing shared_buffers solely for huge page efficiency is valid if workload benefits from larger cache — not if working set fits in 2 GB.

Conservative shared_buffers sizing:

```
Dedicated DB server: 25% RAM (up to 8-16 GB typical)
Mixed use server: 15% RAM
```

Then calculate huge pages from actual shared_buffers, not total RAM.

## Measuring impact

Before/after comparison:

```bash
# TLB misses via perf
sudo perf stat -e dTLB-loads,dTLB-load-misses,iTLB-load-misses \
  -p $(pgrep -o postgres) sleep 60
```

Benchmark representative workload with pgbench:

```bash
pgbench -c 32 -j 4 -T 300 -S mydb  # read-heavy
pgbench -c 32 -j 4 -T 300 mydb     # read-write
```

Compare transactions/sec and p95 latency with `huge_pages=off` vs `on`. Improvement below 3% on your workload may not justify operational complexity.

## Troubleshooting allocation failures

**HugePages_Free = 0 after start, but Postgres running**:

Partial allocation — check log for actual pages used. Increase nr_hugepages.

**Postgres starts without huge pages despite config**:

1. `huge_pages = try` silently falls back — check log
2. nr_hugepages = 0 — not reserved
3. memlock limit too low — check ulimit
4. SHMMAX/SHMALL limits (rare on modern kernels)

**OOM after reserving huge pages**:

Huge page memory is subtracted from available RAM. Reserve only what Postgres needs — do not set nr_hugepages to 90% of total RAM.

**Multiple Postgres instances**:

Each instance competing for the same huge page pool. Size nr_hugepages for sum of all instances' shared_buffers, or isolate instances on separate nodes.

## Alternative memory optimizations

If huge pages are impractical:

- Right-size `shared_buffers` — avoid oversized cache with diminishing returns
- `effective_cache_size` tuning for planner (does not allocate memory)
- OS page cache leverages remaining RAM for Postgres data files
- `shared_memory_type = mmap` (default on Linux) — standard pages

## Checklist for production rollout

1. Disable transparent huge pages in kernel
2. Set shared_buffers based on RAM sizing guidelines
3. Calculate and reserve vm.nr_hugepages with 5–10% overhead
4. Configure memlock unlimited for postgres user
5. Set `huge_pages = try`, restart, verify log message
6. Benchmark workload before switching to `huge_pages = on`
7. Add nr_hugepages to sysctl for persistence across reboots
8. Monitor HugePages_Free in monitoring system — should be stable after startup

## Kernel boot persistence gotcha

Setting vm.nr_hugepages via sysctl persists across reboots, but verify boot order: if Postgres starts before sysctl applies (rare with systemd ordering issues), the first start may fall back to normal pages. Use systemd drop-in to ensure postgres starts after sysctl:

```ini
[Unit]
After=sysctl.service
Requires=sysctl.service
```

After kernel upgrades, huge page size is unchanged on x86 but ARM platforms may differ — re-read `/proc/meminfo` Hugepagesize after major OS upgrades and recalculate nr_hugepages if shared_buffers changed in the same maintenance window.

Include huge page configuration in your database provisioning and terraform modules so new nodes arrive pre-configured rather than requiring manual sysctl tuning during incident recovery.

## Summary

Explicit huge pages reduce TLB miss overhead for large Postgres shared_buffers allocations by mapping memory in 2 MB pages instead of 4 KB. Disable transparent huge pages to avoid latency jitter, calculate vm.nr_hugepages from shared_buffers size, grant memlock limits to the postgres user, and verify allocation in startup logs. The benefit matters most on dedicated database servers with 8 GB+ shared_buffers — on smaller instances or managed cloud databases, focus tuning effort elsewhere unless profiling shows TLB pressure.


After resizing shared_buffers, recompute vm.nr_hugepages and verify HugePages_Free drops on start — try-mode fallback silently undoes the tuning.

Prefer huge_pages=on in production after validation so silent try-mode fallback cannot hide a missing reservation after an instance resize.
