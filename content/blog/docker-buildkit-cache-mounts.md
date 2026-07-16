---
title: "Faster Builds with BuildKit Cache Mounts"
slug: "docker-buildkit-cache-mounts"
description: "BuildKit cache mounts persist package manager caches across Docker builds. Speed up npm, pip, and apt layers without bloating final images."
datePublished: "2025-10-27"
dateModified: "2025-10-27"
tags: ["DevOps", "Infrastructure"]
keywords: "BuildKit cache mount, Docker build cache, RUN mount cache, faster Docker builds, CI build optimization"
faq:
  - q: "What is a BuildKit cache mount?"
    a: "A cache mount is a persistent directory attached to a RUN instruction during docker build, declared with --mount=type=cache. Package managers (apt, npm, pip, go mod) store downloaded artifacts in the mount across builds without copying them into the final image layer — faster rebuilds, smaller images."
  - q: "How is cache mount different from a regular Docker layer cache?"
    a: "Layer cache invalidates when the RUN instruction or prior layers change — npm ci re-downloads everything. Cache mounts survive instruction changes when the mount ID and paths match, persisting ~/.npm or /var/cache/apt between builds on the same builder node."
  - q: "Do cache mounts work in CI?"
    a: "Yes, when CI builders are persistent or use remote cache backends. Ephemeral single-use runners lose local cache mounts unless you enable BuildKit cache export/import (registry cache, GitHub Actions cache). docker buildx build --cache-to/--cache-from persists mounts across ephemeral agents."
---

Every CI run that starts `npm ci` from a cold cache burns minutes and bandwidth. COPY package.json + RUN npm ci helps layer caching until any prior layer changes — then you're back to downloading the internet. BuildKit **cache mounts** keep package caches on the builder filesystem between builds without shipping them into production images.

## Enable BuildKit

```bash
export DOCKER_BUILDKIT=1
# or docker buildx build ...
```

Docker Desktop and modern CI images enable by default. Syntax requires Dockerfile `# syntax=directive`:

```dockerfile
# syntax=docker/dockerfile:1
FROM node:20-bookworm-slim
WORKDIR /app
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci --prefer-offline
COPY . .
RUN npm run build
```

Second build hits `/root/.npm` cache — `npm ci` skips re-fetching unchanged tarballs.

## Mount types overview

| Type | Purpose |
|---|---|
| `cache` | Persistent across builds (package caches) |
| `bind` | Mount host/build context path during RUN |
| `tmpfs` | Ephemeral RAM disk |
| `secret` | Credentials not stored in layers |
| `ssh` | SSH agent for private git deps |

Cache mounts specifically target **repeatable download steps**.

## Language-specific patterns

**Python pip:**

```dockerfile
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt
```

**Go modules:**

```dockerfile
RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    go build -o /out/app .
```

**Debian apt:**

```dockerfile
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y build-essential
```

`sharing=locked` serializes apt cache access on parallel builds.

**Rust cargo:**

```dockerfile
RUN --mount=type=cache,target=/usr/local/cargo/registry \
    --mount=type=cache,target=/app/target \
    cargo build --release
```

## Cache IDs and scopes

Multiple projects on one builder — isolate caches:

```dockerfile
RUN --mount=type=cache,target=/root/.npm,id=myapp-npm-prod \
    npm ci
```

`id` prevents cross-project pollution. `sharing=shared|private|locked` controls concurrent build access.

## Remote cache for ephemeral CI

Local cache mounts die with runner. **Registry cache**:

```bash
docker buildx build \
  --cache-to type=registry,ref=ghcr.io/org/app:buildcache,mode=max \
  --cache-from type=registry,ref=ghcr.io/org/app:buildcache \
  --push -t ghcr.io/org/app:latest .
```

GitHub Actions:

```yaml
- uses: docker/build-push-action@v6
  with:
    cache-from: type=gha
    cache-to: type=gha,mode=max
```

Combines layer cache + mount persistence across workflow runs.

## What not to cache in mounts

Application source compiled into binaries — belongs in layers or multi-stage copy. Don't mount cache into final runtime stage unless read-only tooling needed — **cache mounts don't appear in exported image** by default (BuildKit excludes them from layer tarball).

Multi-stage pattern:

```dockerfile
FROM node:20 AS builder
RUN --mount=type=cache,target=/root/.npm npm ci
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
```

Final image stays slim.

## Secrets vs cache

Don't put credentials in cache mounts — use `--mount=type=secret` for `.npmrc` tokens:

```dockerfile
RUN --mount=type=secret,id=npmrc,target=/root/.npmrc \
    --mount=type=cache,target=/root/.npm \
    npm ci
```

Secrets never commit to layers.

## Measuring impact

Log build times before/after on CI median (not first cold build). Typical wins: 30–70% on dependency-heavy Node/Python projects. Diminishing returns once layers fully cached — mounts shine when Dockerfile changes invalidate early layers but lockfiles stable.

## Pitfalls

- Builder disk fills — prune BuildKit cache: `docker builder prune`
- Stale cache serves wrong packages — bust with lockfile hash in cache id: `id=npm-${hashFiles('package-lock.json')}`
- Docker Compose without BuildKit — enable explicitly
- Assuming mount in runtime container — build-time only

## CI/CD integration patterns

Cache mounts shine in CI when configured correctly:

**GitHub Actions with docker/build-push-action:**

```yaml
- uses: docker/build-push-action@v6
  with:
    cache-from: type=gha
    cache-to: type=gha,mode=max
    build-args: BUILDKIT_INLINE_CACHE=1
```

**GitLab CI:** Use `docker buildx build --cache-to type=registry` pushing cache layers to your container registry.

Separate concerns:
- **GHA cache / registry cache** — persists Docker layers between CI runs
- **Cache mounts** — persists npm/pip/apt contents *inside* build steps even when layers invalidate

Both together: lockfile unchanged → mount hits → build finishes in 30 seconds instead of 8 minutes.

## Language-specific mount paths

| Ecosystem | Mount target | Notes |
|-----------|--------------|-------|
| npm | `/root/.npm` | Also consider `node_modules/.cache` |
| pip | `/root/.cache/pip` | `--mount=type=cache,target=/root/.cache/pip` |
| Go | `/go/pkg/mod` | Module download cache |
| Rust | `/usr/local/cargo/registry` | Registry + git checkouts |
| apt (Debian) | `/var/cache/apt` | Pair with `--mount=type=cache,target=/var/lib/apt` |

Use `sharing=locked` when parallel builds might write the same mount concurrently.

## Debugging stale cache issues

Symptoms: builds pass locally, fail in CI with "package not found" or wrong version.

1. Check cache key includes lockfile hash
2. Run `docker buildx du` to inspect cache size
3. Bust cache intentionally: `docker builder prune --filter type=exec.cachemount`
4. Verify BuildKit enabled: `DOCKER_BUILDKIT=1`

When dependency resolution changes behavior (npm peer dependency updates), stale mounts cause non-reproducible builds — treat cache busting as part of the lockfile update PR.

Pair with [Docker multi-stage builds](https://blog.michaelsam94.com/docker-multi-stage-builds/) to keep runtime images slim while mounts optimize builder stages.

## Production checklist

- [ ] Cache mount IDs include lockfile hash
- [ ] `DOCKER_BUILDKIT=1` enabled in CI and locally
- [ ] GHA/registry cache combined with mount caches
- [ ] Build times tracked in CI metrics dashboard
- [ ] `docker builder prune` scheduled on self-hosted runners

## Resources

- [Docker docs — BuildKit cache mounts](https://docs.docker.com/build/guide/mounts/)
- [Dockerfile reference — RUN --mount](https://docs.docker.com/reference/dockerfile/#run---mount)
- [docker buildx cache](https://docs.docker.com/build/cache/backends/)
- [GitHub Actions — Docker layer caching](https://docs.docker.com/build/ci/github-actions/cache/)
- [Moby BuildKit repository](https://github.com/moby/buildkit)
