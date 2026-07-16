---
title: "Writing a Kubernetes Operator with CRDs"
slug: "kubernetes-operators-crd"
description: "How to write a Kubernetes operator with CRDs: the reconcile loop, kubebuilder scaffolding, status conditions, and the failure modes that break controllers."
datePublished: "2026-04-12"
dateModified: "2026-04-12"
tags: ["Kubernetes", "DevOps", "Architecture"]
keywords: "Kubernetes operator, CRD, custom resource, controller runtime, reconcile loop, kubebuilder, operator pattern"
faq:
  - q: "What is a Kubernetes operator?"
    a: "A Kubernetes operator is a controller that extends the cluster's API with a Custom Resource Definition (CRD) and encodes operational knowledge about a specific application into software. It watches custom resources and continuously drives the real world toward the state declared in them, automating tasks a human operator would otherwise perform by hand."
  - q: "Do I need a CRD to write an operator?"
    a: "Practically, yes. The operator pattern is defined by the pairing of a custom resource (your desired-state API) and a controller that reconciles it. You can write controllers for built-in resources, but a CRD is what lets you model your own domain object like a database cluster or a certificate."
  - q: "Should I use Kubebuilder or the Operator SDK?"
    a: "Both sit on top of controller-runtime and produce very similar code, so the choice rarely matters long-term. Kubebuilder is the leaner, more Go-native option; Operator SDK adds Helm and Ansible-based operators plus OLM packaging. Start with Kubebuilder unless you specifically need those extras."
---

The first operator I shipped replaced a 40-line runbook that on-call engineers ran at 3 a.m. to rotate a stateful service's leader. A Kubernetes operator is a custom controller that teaches the cluster how to run a specific application: you define a Custom Resource Definition (CRD) to describe the desired state, and a control loop that continuously makes reality match it. The payoff is that operational knowledge stops living in wikis and starts living in code the cluster runs for you, on every change, forever.

That framing matters because operators get oversold. Not everything needs one. But when you have a stateful system with real day-2 operations — backups, failover, version upgrades, scaling with data movement — an operator is the right abstraction, and the mechanics are more approachable than the reputation suggests.

## The reconcile loop is the whole idea

Every operator is a loop. It receives an event ("a custom resource changed"), reads the current state of the world, compares it to the desired state in the resource's spec, and takes actions to close the gap. Then it does it again. The critical property is that reconciliation is *level-based*, not edge-based: you don't react to "the deployment was deleted," you react to "the observed state doesn't match spec, so make it match."

This is why the golden rule of controller code is **idempotency**. Your `Reconcile` function will be called with the same object many times — on resync, on unrelated updates, after a crash. It must be safe to run repeatedly and it must not assume it's seeing every event exactly once. If your logic is "on create, do X," you've already got a bug. The correct logic is "ensure X exists; if not, create it."

## Modeling the CRD

The CRD is your API, so design it like one. Split it into `spec` (what the user wants) and `status` (what the controller observes). Users write spec; controllers own status. Blurring that line is the most common design mistake I see.

```yaml
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: cacheclusters.data.example.com
spec:
  group: data.example.com
  names:
    kind: CacheCluster
    plural: cacheclusters
    shortNames: ["cc"]
  scope: Namespaced
  versions:
    - name: v1alpha1
      served: true
      storage: true
      schema:
        openAPIV3Schema:
          type: object
          properties:
            spec:
              type: object
              properties:
                replicas: { type: integer, minimum: 1, maximum: 9 }
                version: { type: string }
              required: ["replicas", "version"]
            status:
              type: object
              properties:
                readyReplicas: { type: integer }
```

Put validation in the OpenAPI schema (`minimum`, `maximum`, `enum`, `required`). Every constraint you encode there is a constraint you don't have to check — and error on — inside your controller. Start with a `v1alpha1` version so you're free to break the API before anyone depends on it.

## Scaffolding with kubebuilder

You don't hand-write the plumbing. Kubebuilder generates the project layout, the CRD manifests from Go structs, and the controller skeleton on top of controller-runtime.

```bash
kubebuilder init --domain example.com --repo github.com/acme/cache-operator
kubebuilder create api --group data --version v1alpha1 --kind CacheCluster
```

That gives you a typed `CacheCluster` struct and a `Reconcile` stub. You fill in the loop:

```go
func (r *CacheClusterReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
    var cc datav1alpha1.CacheCluster
    if err := r.Get(ctx, req.NamespacedName, &cc); err != nil {
        // Object gone — owned resources are garbage-collected via owner refs.
        return ctrl.Result{}, client.IgnoreNotFound(err)
    }

    desired := buildStatefulSet(&cc)
    if err := ctrl.SetControllerReference(&cc, desired, r.Scheme); err != nil {
        return ctrl.Result{}, err
    }

    var current appsv1.StatefulSet
    err := r.Get(ctx, client.ObjectKeyFromObject(desired), &current)
    switch {
    case apierrors.IsNotFound(err):
        if err := r.Create(ctx, desired); err != nil {
            return ctrl.Result{}, err
        }
    case err != nil:
        return ctrl.Result{}, err
    default:
        current.Spec.Replicas = desired.Spec.Replicas
        if err := r.Update(ctx, &current); err != nil {
            return ctrl.Result{}, err
        }
    }

    cc.Status.ReadyReplicas = current.Status.ReadyReplicas
    return ctrl.Result{}, r.Status().Update(ctx, &cc)
}
```

Two things earn their keep here. `SetControllerReference` establishes an owner reference so Kubernetes garbage-collects the StatefulSet when the `CacheCluster` is deleted — you get cascading cleanup for free. And `client.IgnoreNotFound` handles the delete case cleanly instead of treating a missing object as an error.

## Status, conditions, and telling the truth

A controller that silently does the right thing is still a bad controller if a user can't tell *whether* it's done. Populate `status`, and use the standard `Conditions` pattern — `Ready`, `Progressing`, `Degraded` — with reasons and timestamps. This is how `kubectl get` and downstream tooling learn the health of your resource. I treat rich status as non-negotiable; it's the difference between an operator people trust and one they `kubectl describe` in a panic.

Emit Kubernetes Events for meaningful transitions too. When failover happens, an event that says why beats grepping controller logs. This is the same instinct behind [designing for observability with SLOs](https://blog.michaelsam94.com/designing-for-observability-slos/) — the system should explain itself.

## The failure modes nobody warns you about

Here's what actually breaks operators in production:

- **Non-idempotent reconciles.** Creating a resource without first checking it exists gives you duplicate-object errors and hot loops. Always read-then-reconcile.
- **Hot-looping on error.** Returning an error requeues with backoff, which is usually right. But returning `Requeue: true` with no delay on a permanent failure will peg a CPU. Distinguish transient from terminal errors.
- **Fighting another controller.** If two controllers both own a field, they'll flap forever. Use owner references and server-side apply field ownership to draw clear boundaries.
- **Blocking the loop.** `Reconcile` should be fast and non-blocking. Don't `sleep` waiting for a database to come up — requeue and check again next pass.
- **Ignoring finalizers for external state.** If your operator provisions something outside the cluster (a cloud bucket, a DNS record), add a finalizer so deletion runs your cleanup before the object vanishes.

## When not to write one

Operators are code you now maintain, upgrade, and secure with cluster-wide permissions. If a Helm chart plus a CronJob covers your needs, use that. The operator pattern earns its complexity when there's genuine stateful lifecycle logic — the kind of automation that also belongs in a broader [internal developer platform](https://blog.michaelsam94.com/platform-engineering-internal-developer-platform/) so teams consume it as a paved road rather than a bespoke tool. Reach for an operator when the alternative is a human following a runbook under pressure. That's the bar.

## Resources

- [Kubernetes — Operator pattern](https://kubernetes.io/docs/concepts/extend-kubernetes/operator/)
- [Kubebuilder Book](https://book.kubebuilder.io/)
- [controller-runtime (GitHub)](https://github.com/kubernetes-sigs/controller-runtime)
- [Extend the Kubernetes API with CustomResourceDefinitions](https://kubernetes.io/docs/tasks/extend-kubernetes/custom-resources/custom-resource-definitions/)
- [Operator SDK documentation](https://sdk.operatorframework.io/docs/)
- [Kubernetes API conventions (conditions)](https://github.com/kubernetes/community/blob/master/contributors/devel/sig-architecture/api-conventions.md)
