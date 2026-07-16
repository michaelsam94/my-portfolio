---
title: "Building Operators with Kubebuilder"
slug: "kubernetes-operators-with-kubebuilder"
description: "Build Kubernetes operators with Kubebuilder: project scaffolding, controllers, reconciliation loops, status conditions, and testing patterns."
datePublished: "2026-02-25"
dateModified: "2026-02-25"
tags: ["Kubernetes", "DevOps"]
keywords: "Kubebuilder, Kubernetes operator, controller-runtime, reconciliation, CRD, golang operator"
faq:
  - q: "When should I build a custom operator instead of using Helm alone?"
    a: "Build an operator when the application needs continuous reconciliation—scaling based on custom metrics, backup schedules, certificate renewal, or complex day-2 operations that Jobs and Helm hooks handle poorly. Helm installs artifacts; operators manage lifecycle state over time."
  - q: "What language does Kubebuilder use?"
    a: "Go, using controller-runtime and client-go. Kubebuilder scaffolds CRDs, RBAC, manager entrypoint, and test harness. Operator Framework and SDK have overlapping tooling; Kubebuilder is the Kubernetes SIG standard scaffold."
  - q: "How do I debug a reconciliation loop that never settles?"
    a: "Check controller logs for requeue errors, compare spec vs status updates causing infinite watch loops, verify RBAC allows status subresource updates, and use controller-runtime log verbosity. Ensure spec mutations in Reconcile do not trigger immediate re-reconcile without generation change."
---

We ran database backups with CronJobs until someone scaled replicas manually and CronJobs targeted the wrong StatefulSet ordinal. A small **Kubebuilder operator** watches `DatabaseBackup` CRs, creates Jobs with correct pod indexes, and records status on the CR—GitOps-friendly and self-healing. That is the operator value proposition: encode operational knowledge in a controller.

**Kubebuilder** scaffolds Go operators: CRD types, reconciliation controllers, RBAC manifests, and envtest integration. It sits on **controller-runtime**, the shared library behind most Kubernetes controllers.

## Initialize a project

```bash
kubebuilder init --domain example.com --repo github.com/org/backup-operator
kubebuilder create api --group storage --version v1alpha1 --kind DatabaseBackup
# Create resource and controller: Y, Y
```

Generates:

```
config/          # CRD, RBAC, manager deployment
internal/controller/
api/v1alpha1/    # Go types + CRD markers
```

## Define the CRD type

```go
// api/v1alpha1/databasebackup_types.go
type DatabaseBackupSpec struct {
    DatabaseRef string `json:"databaseRef"`
    Schedule    string `json:"schedule,omitempty"`
    RetentionDays int  `json:"retentionDays"`
}

type DatabaseBackupStatus struct {
    Conditions []metav1.Condition `json:"conditions,omitempty"`
    LastBackupTime *metav1.Time     `json:"lastBackupTime,omitempty"`
    Phase          string           `json:"phase,omitempty"`
}

// +kubebuilder:object:root=true
// +kubebuilder:subresource:status
type DatabaseBackup struct {
    metav1.TypeMeta   `json:",inline"`
    metav1.ObjectMeta `json:"metadata,omitempty"`
    Spec   DatabaseBackupSpec   `json:"spec,omitempty"`
    Status DatabaseBackupStatus `json:"status,omitempty"`
}
```

Run `make manifests` to regenerate CRD YAML.

## Reconcile loop

```go
func (r *DatabaseBackupReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
    var backup storagev1alpha1.DatabaseBackup
    if err := r.Get(ctx, req.NamespacedName, &backup); err != nil {
        return ctrl.Result{}, client.IgnoreNotFound(err)
    }

    job := r.buildBackupJob(&backup)
    if err := ctrl.SetControllerReference(&backup, job, r.Scheme); err != nil {
        return ctrl.Result{}, err
    }

    found := &batchv1.Job{}
    err := r.Get(ctx, types.NamespacedName{Name: job.Name, Namespace: job.Namespace}, found)
    if apierrors.IsNotFound(err) {
        if err := r.Create(ctx, job); err != nil {
            return ctrl.Result{}, err
        }
        return ctrl.Result{Requeue: true}, nil
    }

    if found.Status.Succeeded > 0 {
        backup.Status.Phase = "Complete"
        backup.Status.LastBackupTime = &metav1.Time{Time: time.Now()}
        meta.SetStatusCondition(&backup.Status.Conditions, metav1.Condition{
            Type:   "Ready",
            Status: metav1.ConditionTrue,
            Reason: "BackupSucceeded",
        })
        return ctrl.Result{}, r.Status().Update(ctx, &backup)
    }

    return ctrl.Result{RequeueAfter: time.Minute}, nil
}
```

Set owner references so garbage collection removes Jobs when CR deletes.

## Manager and RBAC

```go
func main() {
    mgr, _ := ctrl.NewManager(ctrl.GetConfigOrDie(), ctrl.Options{Scheme: scheme})
    _ = (&DatabaseBackupReconciler{
        Client: mgr.GetClient(),
        Scheme: mgr.GetScheme(),
    }).SetupWithManager(mgr)
    mgr.Start(ctrl.SetupSignalHandler())
}
```

Kubebuilder generates RBAC markers:

```go
// +kubebuilder:rbac:groups=storage.example.com,resources=databasebackups,verbs=get;list;watch;create;update;patch;delete
// +kubebuilder:rbac:groups=storage.example.com,resources=databasebackups/status,verbs=get;update;patch
// +kubebuilder:rbac:groups=batch,resources=jobs,verbs=get;list;watch;create;update;patch;delete
```

`make install` applies CRD; `make deploy IMG=...` runs manager in cluster.

## Testing with envtest

```go
var _ = Describe("DatabaseBackup controller", func() {
    It("creates backup job", func() {
        backup := &storagev1alpha1.DatabaseBackup{ /* ... */ }
        Expect(k8sClient.Create(ctx, backup)).To(Succeed())
        Eventually(func() bool {
            job := &batchv1.Job{}
            err := k8sClient.Get(ctx, jobKey, job)
            return err == nil
        }).Should(BeTrue())
    })
})
```

`make test` runs envtest with etcd/apiserver.

## Production practices

- Use **finalizers** for external resource cleanup
- Patch status with `Status().Update`, not spec
- Rate-limit requeues on external API errors
- Expose Prometheus metrics from controller-runtime
- Run single active manager with leader election for HA:

```go
LeaderElection: true,
LeaderElectionID: "backup-operator.example.com",
```

## When not to build an operator

One-time migrations, simple Deployments, and stateless apps need Deployments and Helm—not controllers.

## Webhooks for validation

Validating admission webhooks on CRD prevent bad spec at create time—cheaper than reconcile error loops. Kubebuilder scaffolds webhook with `kubebuilder create webhook`.

## Version migration

When bumping CRD `v1alpha1` to `v1beta1`, run both versions served with conversion webhook—clients upgrade gradually.


## What to measure after rollout

Track error rates, tail latency, and resource utilization for two weeks after changes land—most regressions appear under real traffic mixes, not in staging smoke tests. Keep a rollback path documented: feature flags, Helm revision, or Git revert with known good digest. Review on-call pages tied to the topic quarterly; delete alerts that never fire and add thresholds that would have caught your last incident.

Run a short blameless postmortem if production surprised you, even for minor issues. The goal is updating this runbook section with one concrete lesson per quarter so the next engineer inherits context, not just configuration snippets.


## Documentation your team should maintain

Maintain a one-page runbook link from your main service README: prerequisites, owner rotation, last drill date, and known sharp edges. Link to vendor docs in the Resources section below but capture org-specific decisions (CIDR ranges, cluster names, approval gates) in internal docs that stay current. New hires should deploy a safe canary within a week using only that runbook—if they cannot, the doc is incomplete.


## Pre-production checklist

Before promoting to production, walk through this list with someone who was not the primary author—fresh eyes catch assumptions.

- **Staging parity**: The staging environment exercises the same code paths as production, including failure modes you expect to handle (timeouts, retries, partial outages).
- **Observability**: Dashboards and alerts exist for the metrics and log patterns discussed above; on-call knows where to look first.
- **Rollback**: You can revert to the previous known-good state in one documented step without improvising.
- **Access control**: Only the principals that need access have it; audit logs are enabled where the topic touches secrets or infrastructure APIs.
- **Load test**: You have evidence—not intuition—about behavior at expected peak plus headroom.

If any item is "we will do that later," treat it as a release blocker for tier-1 services.


## Common questions from reviewers

Reviewers and auditors often ask whether this approach scales with team growth and whether it fails safely. Answer explicitly in your design doc: what happens when dependencies are down, when credentials expire, and when traffic doubles overnight. Prefer defaults that deny or degrade gracefully over defaults that fail open. Document known limits (throughput ceilings, supported versions, regions) in the same place operators look during incidents—avoid scattering critical constraints across Slack threads.


## Resources

- [Kubebuilder book](https://book.kubebuilder.io/) — tutorial and patterns
- [controller-runtime documentation](https://pkg.go.dev/sigs.k8s.io/controller-runtime) — APIs and packages
- [Kubernetes CRD documentation](https://kubernetes.io/docs/concepts/extend-kubernetes/api-extension/custom-resources/) — CRD concepts
- [Operator pattern — CNCF](https://kubernetes.io/docs/concepts/extend-kubernetes/operator/) — official overview
