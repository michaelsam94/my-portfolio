# Part 4: posts 15-20

POSTS_P4 = {}

POSTS_P4["devops-flux-helm-controller"] = (
    {
        "title": "Flux Helm Controller Operations",
        "description": "Flux HelmRelease CRDs reconcile charts from Git or OCI—valuesFrom, drift detection, and rollback semantics differ from CLI helm upgrade in ways that bite during incidents.",
        "datePublished": "2026-05-10",
        "tags": ["DevOps", "GitOps", "Helm"],
        "keywords": "Flux HelmRelease, helm-controller, GitOps Helm, OCI charts",
        "faq": [
            {
                "q": "What is a HelmRelease in Flux?",
                "a": "A Kubernetes CRD declaring desired Helm chart state: chart source (GitRepository, HelmRepository, OCIRepository), version, values, install/upgrade remediation, and target namespace. helm-controller reconciles until cluster matches spec.",
            },
            {
                "q": "How do HelmRelease rollbacks work?",
                "a": "Set spec.rollback.enabled or use `flux suspend/resume`. helm-controller tracks release history like Helm. For GitOps rollback, revert the Git commit changing values/chart version—preferred over helm rollback alone to keep Git source of truth aligned.",
            },
            {
                "q": "How do you pass secrets to HelmRelease values?",
                "a": "Use valuesFrom referencing Secret or ConfigMap keys—never commit plaintext secrets. SOPS-encrypted secrets in Git decrypted by Flux kustomize-controller, or External Secrets Operator syncing to Secret referenced by HelmRelease.",
            },
            {
                "q": "Why does HelmRelease hang on upgrade?",
                "a": "Common causes: pending hooks exceeding timeout, readiness probe failures on new pods, resource conflict, or CRD upgrade ordering. Check HelmRelease status conditions, helm-controller logs, and increase spec.timeout if legitimate slow rollout.",
            },
        ],
    },
    r"""The platform team migrated from `helm upgrade` in CI to Flux HelmRelease. First incident: someone `kubectl edit` patched a Deployment; helm-controller reverted it within three minutes—good. Second incident: a values typo pinned `image.tag: latest`; helm-controller happily reconciled every pull—bad.

Helm controller is Helm with GitOps superpowers and GitOps footguns.

## HelmRelease anatomy

```yaml
apiVersion: helm.toolkit.fluxcd.io/v2
kind: HelmRelease
metadata:
  name: redis
  namespace: cache
spec:
  interval: 5m
  timeout: 10m
  chart:
    spec:
      chart: redis
      version: "18.6.1"
      sourceRef:
        kind: HelmRepository
        name: bitnami
        namespace: flux-system
  values:
    architecture: replication
    auth:
      enabled: true
      existingSecret: redis-auth
  valuesFrom:
    - kind: Secret
      name: redis-overrides
      valuesKey: values.yaml
  install:
    remediation:
      retries: 3
  upgrade:
    remediation:
      retries: 3
      remediateLastFailure: true
  driftDetection:
    mode: enabled
```

Key fields:

- **`interval`** — reconciliation frequency; not just on Git push if using post-render pipelines.
- **`driftDetection`** — surfaces manual kubectl edits; pairs with remediation policy.
- **`valuesFrom`** — merge order matters; later sources override.

## Source types

| Source | Use case |
|--------|----------|
| HelmRepository | Traditional Helm repos (HTTPS index) |
| OCIRepository | OCI artifacts (`oci://registry/chart`) |
| GitRepository | Chart in Git path with `chart: ./charts/app` |

Pin `version` explicitly—never floating ranges in prod.

## Remediation strategies

```yaml
upgrade:
  remediation:
    remediateLastFailure: true  # auto-rollback on failed upgrade
    retries: 3
```

Without remediation, failed upgrades leave release in pending state—monitor `HelmRelease` condition `Ready=False`.

## Secrets pattern with SOPS

```
clusters/prod/cache/redis/
├── kustomization.yaml
├── helmrelease.yaml
└── secrets.enc.yaml   # SOPS encrypted
```

Flux decrypts via `decryption.provider: sops` in Kustomization—HelmRelease references Secret created by kustomize build.

## Observability

Alert on:

```promql
gotk_reconcile_condition{kind="HelmRelease",status="False"} == 1
```

Dashboard: reconciliation duration, upgrade failures, chart fetch errors.

## Git rollback vs helm rollback

Preferred incident flow:

1. `git revert` the values change.
2. Flux reconciles automatically.
3. Verify HelmRelease Ready.

CLI `helm rollback` without Git revert causes drift—next reconciliation may re-apply bad version from Git or fight manual rollback.

## Multi-tenant patterns

One HelmRelease per tenant instance vs shared chart with values overlays—platform teams often use Application-style folder per env:

```
tenants/
  prod/
    cache/redis/helmrelease.yaml
  staging/
    cache/redis/helmrelease.yaml
```

Helm controller scales to hundreds of releases; watch helm-controller memory and shard by fleet if needed.

Flux HelmRelease turns Helm into declarative infrastructure—if values and versions live in Git and remediation policies match your appetite for auto-rollback.
""",
)

POSTS_P4["devops-flux-image-automation"] = (
    {
        "title": "Flux Image Automation and Policy",
        "description": "Flux ImageRepository scans container registries; ImagePolicy selects semver tags; ImageUpdateAutomation commits digest pins to Git—never let latest tag float in production.",
        "datePublished": "2026-05-11",
        "tags": ["DevOps", "GitOps", "CI/CD"],
        "keywords": "Flux image automation, ImagePolicy, ImageUpdateAutomation, semver tags",
        "faq": [
            {
                "q": "How does Flux image automation work?",
                "a": "ImageRepository polls registry tags/digests. ImagePolicy filters acceptable tags (semver range). ImageUpdateAutomation writes selected digest or tag back to Git (Deployment, HelmRelease, or Kustomize files). Flux reconciles cluster to new image.",
            },
            {
                "q": "Why avoid latest tag in ImagePolicy?",
                "a": "latest is mutable—identical tag points to different digests over time. Reproducible prod requires digest pin or immutable semver tags. ImagePolicy should select highest matching semver, commit digest sha256 to Git.",
            },
            {
                "q": "How do you gate automated image updates?",
                "a": "Use ImageUpdateAutomation with Git branch PR strategy (setters in YAML), CI on automation PRs, and prod-only policies requiring semver patch/minor ranges. Suspend automation during freeze windows via ImageRepository/ImagePolicy suspend.",
            },
            {
                "q": "What permissions does image-reflector-controller need?",
                "a": "Read access to container registry (ECR, GCR, ACR, Docker Hub token). ImageUpdateAutomation needs Git write credentials scoped to manifest repo only—never cluster-admin.",
            },
        ],
    },
    r"""CI built and pushed `app:v2.3.4` at 2 p.m. Production still ran `v2.3.2` at 6 p.m. because nobody updated the Git manifest—until ImageUpdateAutomation opened a PR, CI passed, merge happened, and Flux deployed by 2:15 p.m. the next cycle without a human copying digests.

Image automation closes the loop between registry and GitOps. Misconfigured policy opens the loop to `latest` chaos.

## Component chain

```
Registry ──scan──► ImageRepository
                        │
                        ▼
                   ImagePolicy (semver filter)
                        │
                        ▼
              ImageUpdateAutomation
                        │
                        ▼
                   Git commit (setter)
                        │
                        ▼
              Kustomize/HelmRelease reconcile
```

## ImageRepository

```yaml
apiVersion: image.toolkit.fluxcd.io/v1beta2
kind: ImageRepository
metadata:
  name: checkout-api
  namespace: flux-system
spec:
  image: 123456789.dkr.ecr.us-east-1.amazonaws.com/checkout-api
  interval: 1m
  provider: aws
  exclusionList:
    - ^.*-rc.*
    - ^.*-dev.*
```

Exclude release candidate tags from prod policies.

## ImagePolicy semver

```yaml
apiVersion: image.toolkit.fluxcd.io/v1beta2
kind: ImagePolicy
metadata:
  name: checkout-api-prod
  namespace: flux-system
spec:
  imageRepositoryRef:
    name: checkout-api
  policy:
    semver:
      range: ">=2.3.0 <2.4.0"
```

Patch-only teams use `~2.3.x` equivalent ranges.

## Setters in manifests

```yaml
# deployment.yaml
spec:
  template:
    spec:
      containers:
        - name: api
          image: 123456789.dkr.ecr.us-east-1.amazonaws.com/checkout-api:2.3.2 # {"$imagepolicy": "flux-system:checkout-api-prod"}
```

ImageUpdateAutomation replaces tag with selected version and commits.

## ImageUpdateAutomation

```yaml
apiVersion: image.toolkit.fluxcd.io/v1beta2
kind: ImageUpdateAutomation
metadata:
  name: checkout-api
  namespace: flux-system
spec:
  interval: 5m
  sourceRef:
    kind: GitRepository
    name: fleet-apps
  git:
    checkout:
      branch: main
    commit:
      author:
        name: flux-bot
        email: flux-bot@example.com
      messageTemplate: "chore(images): update {{range .Updated.Images}}{{println .}}{{end}}"
    push:
      branch: main
  update:
    path: ./apps/checkout-api
    strategy: Setters
```

For prod, push to `auto/image-updates` branch and require PR review instead of direct main push.

## Digest pinning

Prefer automation committing `@sha256:...` for immutable deploys:

```yaml
policy:
  semver:
    range: "2.3.x"
  # alternative: alphabetical on tags matching pattern
```

Some teams use ImagePolicy `alphabetical` on git-sha tags from CI.

## Freeze windows

```bash
flux suspend imageupdateautomation checkout-api
flux suspend imagepolicy checkout-api-prod
```

Document in release calendar; unsuspend after verification.

## Failure modes

| Issue | Symptom | Fix |
|-------|---------|-----|
| Registry auth drift | ImageRepository not ready | Refresh ECR token/IRSA |
| Setter comment typo | No Git updates | Validate marker syntax |
| Over-broad semver | Major bump in prod | Tighten range |
| Automation to main | Bad image instant prod | PR branch strategy |

Image automation removes copy-paste digests—it does not remove judgment about semver ranges and review gates.
""",
)

POSTS_P4["devops-game-day-planning"] = (
    {
        "title": "Game Day Planning and Steady-State Hypotheses",
        "description": "Effective game days need written hypotheses, named observers, rollback criteria, and executive comms—otherwise chaos engineering becomes an unplanned outage with better snacks.",
        "datePublished": "2026-06-21",
        "tags": ["DevOps", "Chaos Engineering", "SRE"],
        "keywords": "game day, steady state hypothesis, chaos engineering, resilience testing",
        "faq": [
            {
                "q": "What is a steady-state hypothesis in chaos engineering?",
                "a": "A measurable claim about normal system behavior during an experiment—e.g., checkout success rate above 99.5% while one AZ pod is unavailable. If steady state breaks, the experiment stops and you learn resilience gaps.",
            },
            {
                "q": "Who should participate in a game day?",
                "a": "Service owner (runs experiment), observer (watches metrics/customer impact), communications lead (status page/internal updates), executive sponsor (escalation authority), and optionally customer support liaison. Not everyone presses the chaos button.",
            },
            {
                "q": "How is a game day different from fault injection in CI?",
                "a": "Game days are coordinated human exercises with broad scenarios, cross-team learning, and explicit rollback criteria—often production with controls. CI fault injection is automated, narrower, and runs continuously in staging or prod at low amplitude.",
            },
            {
                "q": "When should you abort a game day experiment?",
                "a": "Abort when steady-state metrics violate predefined thresholds, error budget burn exceeds agreed limit, unexpected customer impact appears, or executive/comms lead calls halt. Pre-written abort criteria prevent heroics.",
            },
        ],
    },
    r"""The first "game day" killed checkout for eleven minutes because nobody defined steady state, the engineer injecting DNS failure forgot staging shared CoreDNS with prod ingress lab, and customer support learned about the test from Twitter.

Game days teach organizations—not just systems. Planning is the difference between curriculum and casualty.

## Game day document template

One page, stored in repo `docs/game-days/2026-Q3-checkout.md`:

```markdown
# Game Day: Checkout AZ failure
Date: 2026-09-15 14:00 UTC
Owner: @alice (payments SRE)
Observer: @bob (metrics)
Comms: @carol (status page)

## Hypothesis
When 50% of checkout pods in us-east-1a are unavailable for 10 minutes,
checkout success rate remains >= 99.5% (global) and p99 latency < 1.2s.

## Steady-state metrics
- checkout_success_rate (5m window)
- checkout_p99_latency
- payment_gateway_error_rate

## Abort criteria
- success_rate < 99.0% for 2 consecutive minutes
- any SEV1 customer report via support hotline
- executive abort verbal from @sponsor

## Experiment steps
1. T-15m: confirm dashboards, notify support
2. T-0: Litmus pod-delete 50% checkout in us-east-1a
3. T+10m: restore, begin recovery validation
4. T+30m: retrospective notes

## Rollback
flux suspend helmrelease checkout && kubectl scale ...
```

## Roles in practice

**Owner** executes chaos tooling, watches service logs.

**Observer** independent from owner—only watches SLI dashboards and customer-facing probes. Calls abort without debating.

**Comms** drafts internal Slack message and status page template before T-0. Updates if abort triggers.

**Executive sponsor** pre-approves blast radius; resolves disputes when abort is ambiguous.

## Environment choice

| Tier | When |
|------|------|
| Staging game day | New service, first chaos experience |
| Prod limited blast | Validated staging, unique prod-only paths |
| Prod full path | Mature org, error budget headroom |

Production game days need customer comms plan—even "no user impact expected" prewrites status page stub.

## Steady state before chaos

Capture 30-minute baseline:

```promql
avg_over_time(checkout_success_rate[30m])
```

Tools like Litmus can wire abort hooks to Prometheus queries.

## After action review

Within 48 hours:

- Did hypothesis hold?
- What broke (technical and process)?
- Action items with owners—max 5, ranked
- Update runbooks with one concrete lesson

Avoid blame; document "observer hesitated to abort" same as "timeout misconfigured."

## Quarterly calendar

Platform schedules game days so teams prepare:

- Q1: dependency latency
- Q2: AZ pod failure
- Q3: database failover
- Q4: combined scenario (payment + inventory)

Rotate service ownership—every tier-1 service every 12 months minimum.

Game days fail when treated as engineering stunts. Hypotheses, observers, abort criteria, and comms turn them into controlled learning—with snacks optional, casualties not.
""",
)

POSTS_P4["devops-gateway-api-httproute-canary"] = (
    {
        "title": "Gateway API HTTPRoute Canary Traffic Splitting",
        "description": "Gateway API HTTPRoute backend weights split canary traffic without Ingress annotation hacks—if your GAMMA-compatible controller implements TrafficSplitting correctly.",
        "datePublished": "2026-11-01",
        "tags": ["DevOps", "Kubernetes", "Networking"],
        "keywords": "Gateway API, HTTPRoute, canary, traffic splitting, GAMMA",
        "faq": [
            {
                "q": "How do HTTPRoute weights work for canary releases?",
                "a": "HTTPRoute rules reference multiple backendRefs with weight fields. Weights are relative—30 and 70 split 30%/70% traffic. Sum need not be 100 on all controllers but normalize proportionally; verify your implementation docs.",
            },
            {
                "q": "What is GAMMA in Gateway API?",
                "a": "Gateway API Mesh Management and Administration (GAMMA) extends Gateway API resources for service mesh and east-west traffic. For ingress canary, use an implementation that supports HTTPRoute attached to Gateway with weighted backendRefs (Cilium, Istio, Contour, etc.).",
            },
            {
                "q": "How is Gateway API canary different from Ingress canary annotations?",
                "a": "Ingress canary relies on vendor-specific annotations (nginx.ingress.kubernetes.io/canary-weight). Gateway API expresses weights in portable HTTPRoute spec—same manifest across compatible controllers, fewer annotation typos.",
            },
            {
                "q": "What happens if backend weights sum incorrectly?",
                "a": "Some controllers reject routes where weights are invalid or reference missing Services; others normalize silently. CI should validate HTTPRoute with gateway-api admission webhook and dry-run apply before prod.",
            },
        ],
    },
    r"""NGINX Ingress canary annotations worked until they did not—a typo in `canary-weight: "10` rejected the entire Ingress, and rollback meant DNS plus annotation revert. Gateway API expresses traffic split in structured `backendRefs`—portable, diffable, reviewable in PR.

Canary with HTTPRoute is declarative weighted routing—not a separate controller hack.

## Minimal canary HTTPRoute

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: checkout-canary
  namespace: storefront
spec:
  parentRefs:
    - name: public-gateway
      namespace: gateway-system
  hostnames:
    - "checkout.example.com"
  rules:
    - matches:
        - path:
            type: PathPrefix
            value: /
      backendRefs:
        - name: checkout-v2
          port: 8080
          weight: 10
        - name: checkout-v1
          port: 8080
          weight: 90
```

Controller translates to Envoy/NGINX/Contour config with weighted clusters.

## Progressive rollout workflow

```
1. Deploy v2 Service (0 weight)
2. Set weights 5/95 — monitor golden signals 30m
3. 25/75 — error budget check
4. 50/50 — load test validation
5. 100/0 on v2 — decommission v1 HTTPRoute backendRef
```

Automate weight changes via GitOps commits or Flagger Gateway API provider.

## Flagger integration

```yaml
apiVersion: flagger.app/v1beta1
kind: Canary
metadata:
  name: checkout
spec:
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: checkout
  service:
    port: 8080
  analysis:
    interval: 1m
    threshold: 5
    metrics:
      - name: request-success-rate
        threshold: 99
  provider:
    type: gatewayapi
    gatewayRef:
      name: public-gateway
```

Flagger adjusts HTTPRoute weights from analysis metrics—rollback on SLO violation.

## Header-based canary (optional)

Some implementations support matches on headers for internal dogfooding before weight-based external traffic:

```yaml
rules:
  - matches:
      - headers:
          - name: x-canary
            value: "true"
    backendRefs:
      - name: checkout-v2
        port: 8080
  - backendRefs:
      - name: checkout-v1
        port: 8080
```

Order matters—first match wins.

## Validation in CI

```bash
kubectl apply --dry-run=server -f httproute.yaml
gateway-api-standard --version v1.0.0 --resources httproute.yaml
```

Reject PR if backend Service does not exist in namespace.

## Observability

Split metrics by service version label:

```promql
sum(rate(http_requests_total{service="checkout-v2"}[5m]))
/
sum(rate(http_requests_total{service=~"checkout-v.*"}[5m]))
```

Compare error rates v1 vs v2 before increasing weight.

## Controller compatibility matrix

Maintain internal doc listing:

| Controller | Weight support | Notes |
|------------|----------------|-------|
| Cilium | Yes | GAMMA |
| Istio | Yes | attach to Gateway |
| Contour | Yes | verify v1 HTTPRoute |

Do not assume Ingress controller behavior transfers—test in staging.

HTTPRoute canary replaces annotation archaeology with spec-first traffic engineering—weights visible in Git, reviewable like code.
""",
)

POSTS_P4["devops-gateway-api-migration"] = (
    {
        "title": "Migrating from Ingress to Gateway API",
        "description": "Gateway API migration succeeds with dual-stack hostnames, shared Gateway resources, and HTTPRoute-by-service cutover—not big-bang DNS flips.",
        "datePublished": "2026-10-12",
        "tags": ["DevOps", "Networking", "Kubernetes"],
        "keywords": "Gateway API migration, Ingress migration, HTTPRoute, shared Gateway",
        "faq": [
            {
                "q": "Should you migrate Ingress to Gateway API all at once?",
                "a": "No—run dual stack: same hostname on Ingress and HTTPRoute through different load balancers or weighted DNS during validation. Migrate service-by-service HTTPRoutes, then decommission Ingress objects per hostname.",
            },
            {
                "q": "What replaces IngressClass in Gateway API?",
                "a": "GatewayClass selects controller implementation (like IngressClass). Gateway resource binds listeners (80/443) to GatewayClass. HTTPRoute attaches to Gateway via parentRefs—separating infra (Gateway) from app routing (HTTPRoute).",
            },
            {
                "q": "How do TLS certificates work with Gateway API?",
                "a": "Gateway listeners reference certRefs (Secret or future ACME integration). Centralize TLS at Gateway for shared certs; or use per-listener certs. cert-manager supports Gateway-shim for HTTP-01 via attached HTTPRoutes.",
            },
            {
                "q": "What tooling converts Ingress manifests to HTTPRoute?",
                "a": "ingress2gateway (Kubernetes SIG tool) generates starter HTTPRoutes—manual review required for annotations, canary rules, and custom snippets. Treat output as draft, not drop-in.",
            },
        ],
    },
    r"""The platform mandate: "Migrate to Gateway API Q4." The failed approach: convert all Ingress YAML Friday, flip DNS, spend weekend reverting because gRPC routes, custom timeout annotations, and cert-manager shim differences were not mapped.

Gateway API migration is a routing refactor across teams—phase it like a data migration, not a flag day.

## Target architecture

```
GatewayClass: cilium
    └── Gateway: public-gateway (LB IP, TLS certs)
            ├── HTTPRoute: checkout (team A)
            ├── HTTPRoute: accounts (team B)
            └── HTTPRoute: api (team C)
```

Apps own HTTPRoutes in their namespaces; platform owns Gateway and GatewayClass.

## Phase 0: inventory

Script existing Ingress:

```bash
kubectl get ingress -A -o json | jq -r '
  .items[] |
  [.metadata.namespace, .metadata.name, (.spec.rules[].host // "none")] | @tsv'
```

Catalog annotations: canary, auth, timeouts, body size—many lack Gateway API equivalents yet.

## Phase 1: platform Gateway

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: public-gateway
  namespace: gateway-system
spec:
  gatewayClassName: cilium
  listeners:
    - name: https
      protocol: HTTPS
      port: 443
      hostname: "*.example.com"
      tls:
        mode: Terminate
        certificateRefs:
          - name: wildcard-example-com
            kind: Secret
```

Deploy parallel LB—do not reuse Ingress LB IP until validated.

## Phase 2: pilot HTTPRoute

Pick low-risk service. Create HTTPRoute matching Ingress paths. Test via `/etc/hosts` or internal DNS before public cutover:

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: ping
  namespace: demo
spec:
  parentRefs:
    - name: public-gateway
      namespace: gateway-system
  hostnames:
    - "ping.example.com"
  rules:
    - backendRefs:
        - name: ping
          port: 8080
```

## Phase 3: DNS weighted migration

Route53 weighted records:

- 90% → old Ingress LB
- 10% → Gateway LB

Monitor error rates; shift weight over days.

## Phase 4: annotation mapping

| Ingress annotation | Gateway API approach |
|--------------------|----------------------|
| canary-weight | HTTPRoute backendRef weights |
| ssl-redirect | HTTPRoute redirect filter |
| proxy-body-size | Policy CRD or GatewayClass parameters |
| custom timeouts | BackendTrafficPolicy (implementation-specific) |

Document gaps requiring mesh or controller-specific CRDs.

## Phase 5: decommission Ingress

Per hostname checklist:

- [ ] HTTPRoute serves prod traffic 7+ days
- [ ] TLS cert valid on Gateway listener
- [ ] ExternalDNS points to Gateway LB
- [ ] Monitoring and alerts updated
- [ ] Ingress deleted (keep Git history)

## ingress2gateway usage

```bash
go install github.com/kubernetes-sigs/ingress2gateway@latest
ingress2gateway convert -f ingress/checkout.yaml -o httproute-draft.yaml
```

Review all generated parentRefs and hostnames manually.

## Rollback plan

Keep Ingress manifest in Git until Gateway proven. Rollback = DNS weight to Ingress LB—no emergency chart revert.

Gateway API migration rewards patience: shared Gateway first, one HTTPRoute at a time, DNS as the throttle—not the first lever pulled.
""",
)

POSTS_P4["devops-github-actions-reusable-workflows"] = (
    {
        "title": "GitHub Actions Reusable Workflows for Platform CI",
        "description": "Callable workflows deduplicate build-test-deploy across repos—version pinning, input contracts, and secrets inheritance determine whether platform CI helps or breaks fifty teams at once.",
        "datePublished": "2026-04-30",
        "tags": ["DevOps", "CI/CD", "Platform"],
        "keywords": "GitHub Actions reusable workflows, workflow_call, platform CI",
        "faq": [
            {
                "q": "What is a reusable workflow in GitHub Actions?",
                "a": "A workflow triggered by workflow_call that other repositories invoke with uses: org/repo/.github/workflows/ci.yml@ref. Inputs and secrets pass explicitly—centralizing CI logic while consumer repos keep thin wrapper workflows.",
            },
            {
                "q": "Should reusable workflows pin to @main or semver tags?",
                "a": "Never @main in prod consumer repos—pin to semver tag or SHA. Platform publishes v1, v2 tags; patch updates are opt-in. Breaking changes require major version bump and migration guide.",
            },
            {
                "q": "How do secrets work with reusable workflows?",
                "a": "Consumer workflow passes secrets: inherit or maps each secret explicitly. Reusable workflows cannot access caller secrets unless passed—design inputs for non-secret config, secrets for credentials only.",
            },
            {
                "q": "How many reusable workflows should a platform team publish?",
                "a": "Start with 3–5: language build/test, container publish, deploy-to-env, security scan. Avoid nano-workflows per step—composition overhead exceeds duplication savings below ~10 lines.",
            },
        ],
    },
    r"""Forty repos copied the same 200-line GitHub Actions YAML. Platform updated Node version in one repo; thirty-nine still ran Node 18 with known CVEs. Reusable workflows fixed duplication—and broke twelve repos overnight when someone pushed `@main` without semver because a input renamed silently.

Platform CI is a product. Version it like one.

## Caller and reusable pattern

**Platform repo** `.github/workflows/nodejs-ci.yml`:

```yaml
on:
  workflow_call:
    inputs:
      node-version:
        required: false
        type: string
        default: "20"
      run-e2e:
        required: false
        type: boolean
        default: false
    secrets:
      NPM_TOKEN:
        required: true
    outputs:
      image-tag:
        description: "Built image tag"
        value: ${{ jobs.build.outputs.image-tag }}

jobs:
  build:
    runs-on: ubuntu-latest
    outputs:
      image-tag: ${{ steps.meta.outputs.tag }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: ${{ inputs.node-version }}
      - run: npm ci && npm test
      - id: meta
        run: echo "tag=${GITHUB_SHA::7}" >> "$GITHUB_OUTPUT"
```

**Consumer repo** `.github/workflows/ci.yml`:

```yaml
on:
  push:
    branches: [main]
  pull_request:

jobs:
  ci:
    uses: myorg/platform-workflows/.github/workflows/nodejs-ci.yml@v2
    with:
      node-version: "20"
      run-e2e: true
    secrets:
      NPM_TOKEN: ${{ secrets.NPM_TOKEN }}
```

Pin `@v2`, not `@main`.

## Versioning policy

| Tag | Meaning |
|-----|---------|
| v1 | Breaking changes from v0 |
| v1.1 | Backward-compatible inputs added |
| v1.1.1 | Patch—bug fix only |

Document in platform README; consumers subscribe to releases.

## Input contract testing

Platform repo CI validates reusable workflow with fixture consumer:

```yaml
# platform repo self-test
jobs:
  test-contract:
    uses: ./.github/workflows/nodejs-ci.yml
    with:
      node-version: "20"
    secrets:
      NPM_TOKEN: ${{ secrets.NPM_TOKEN }}
```

Breaking input rename fails platform merge before consumers break.

## Secrets inheritance

```yaml
jobs:
  deploy:
    uses: myorg/platform-workflows/.github/workflows/deploy.yml@v1
    secrets: inherit  # GitHub Enterprise / org settings permitting
```

Prefer explicit secret mapping for least exposure:

```yaml
secrets:
  AWS_ROLE_ARN: ${{ secrets.PROD_DEPLOY_ROLE }}
```

## Composition limits

Reusable workflows cannot call another reusable workflow nested beyond one level in older GHES—verify version. Matrix at caller level:

```yaml
strategy:
  matrix:
    service: [api, worker, web]
jobs:
  ci:
    uses: myorg/platform-workflows/.github/workflows/nodejs-ci.yml@v2
    with:
      working-directory: services/${{ matrix.service }}
```

## Observability

Track consumer count via GitHub API; deprecate workflows with open issues in consumer repos before deletion.

Reusable workflows scale platform engineering—when pinned, documented, and tested like any shared library—not when `@main` is the default ref.
""",
)
