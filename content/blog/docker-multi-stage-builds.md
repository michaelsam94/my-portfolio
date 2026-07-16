---
title: "Multi-Stage Docker Builds"
slug: "docker-multi-stage-builds"
description: "Structure multi-stage Dockerfiles to separate build tools from runtime, shrink images, and keep CI fast with named stages, BuildKit targets, and cross-compilation."
datePublished: "2025-11-07"
dateModified: "2025-11-07"
tags: ["DevOps", "Docker", "CI/CD", "Build"]
keywords: "multi-stage Docker build, Dockerfile AS builder, separate build runtime, Docker BuildKit target, minimal production image, cross-compile Docker multi-stage"
faq:
  - q: "How many stages should a multi-stage Dockerfile have?"
    a: "Use as many as you need to separate concerns — typically two to four. A common pattern is deps, build, and runtime. Add a test stage only if CI builds that target explicitly. Extra stages that nobody builds add maintenance cost without benefit."
  - q: "Can I build only one stage for local development?"
    a: "Yes. With BuildKit, run docker build --target builder -t myapp:dev . to stop at the builder stage with compilers and dev tools intact. Production pipelines build --target runtime or the final unnamed stage."
  - q: "How do I pass secrets during a multi-stage build without leaving them in layers?"
    a: "Use BuildKit secret mounts: RUN --mount=type=secret,id=npmrc npm ci reads the secret at build time without persisting it in any layer. Never use ARG for tokens that end up in ENV or RUN echo commands."
---

Shipping a Go compiler, Maven, and four gigabytes of `node_modules` devDependencies to production because they all live in one Dockerfile stage is a solvable problem. Multi-stage builds let you use a fat builder image with every toolchain you need, then copy only the compiled binary or bundled assets into a slim runtime image. The production container never contained `gcc`, source code, or test fixtures — because those layers belong to earlier stages that never get tagged or deployed.

## The basic pattern

Name stages with `AS` and copy artifacts forward:

```dockerfile
# syntax=docker/dockerfile:1

FROM rust:1.83-bookworm AS builder
WORKDIR /app
COPY Cargo.toml Cargo.lock ./
COPY src ./src
RUN cargo build --release

FROM debian:bookworm-slim AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates && rm -rf /var/lib/apt/lists/*
COPY --from=builder /app/target/release/my-server /usr/local/bin/my-server
USER 65532:65532
ENTRYPOINT ["/usr/local/bin/my-server"]
```

Only the release binary crosses the stage boundary. Target directory debug symbols, registry cache, and Rust toolchain stay in the builder stage — discarded unless you tag that stage.

## Named stages and selective builds

Explicit names clarify CI targets:

```dockerfile
FROM node:20 AS deps
...

FROM deps AS build
...

FROM node:20-slim AS runtime
...
```

Build a specific stage:

```bash
docker build --target deps -t myapp:deps .
docker build --target runtime -t myapp:prod .
```

In docker-compose or CI matrices, the test stage can run unit tests inside the build graph:

```dockerfile
FROM build AS test
RUN npm test

FROM runtime AS production
COPY --from=build /app/dist ./dist
```

CI: `docker build --target test .` fails the pipeline if tests fail, without publishing the runtime image.

## Cross-compilation in builder stages

Build for `linux/arm64` from an `amd64` CI runner using buildx platforms:

```bash
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t myorg/myapp:1.2.0 \
  --push .
```

Inside the Dockerfile, set build args for cross targets:

```dockerfile
FROM --platform=$BUILDPLATFORM golang:1.23 AS builder
ARG TARGETOS TARGETARCH
RUN CGO_ENABLED=0 GOOS=$TARGETOS GOARCH=$TARGETARCH go build -o /out/app .
```

The builder runs on the native CI architecture; the output binary matches the deployment platform.

## Secrets and credentials in build stages

Never bake API keys into layers:

```dockerfile
RUN --mount=type=secret,id=GITHUB_TOKEN \
    export GITHUB_TOKEN=$(cat /run/secrets/GITHUB_TOKEN) && \
    go mod download
```

Pass at build time: `docker build --secret id=GITHUB_TOKEN,src=$HOME/.github_token .`

Secrets mounted this way never appear in `docker history` or intermediate layer filesystems.

## Common mistakes

**Copying the entire builder filesystem.** `COPY --from=builder / /` brings toolchain debris. Copy explicit paths.

**Forgetting to align libc versions.** A binary built against glibc in `ubuntu:22.04` may not run on `alpine` (musl). Match builder and runtime libc or compile statically.

**Running as root in runtime because the builder did.** Set `USER` in the final stage explicitly.

**One stage doing install and compile and test.** Splitting deps into its own stage improves cache hit rate when only source changes.

## Distroless and scratch final stages

For statically linked Go or Rust binaries, the final stage can be `FROM scratch` or distroless:

```dockerfile
FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=builder /out/app /app
ENTRYPOINT ["/app"]
```

Multi-stage is the mechanism; distroless or scratch is the destination.

## Complete multi-stage Dockerfile examples

**Go application (static binary → scratch):**

```dockerfile
FROM golang:1.22-alpine AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o /out/app ./cmd/server

FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=builder /out/app /app
USER nonroot:nonroot
ENTRYPOINT ["/app"]
```

Final image: ~5MB. No shell, no package manager, minimal attack surface.

**Node.js application (deps → production):**

```dockerfile
FROM node:20-alpine AS deps
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production

FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:20-alpine AS runtime
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY --from=builder /app/dist ./dist
USER node
CMD ["node", "dist/index.js"]
```

Dev dependencies never reach production image. Source code not in final stage.

## BuildKit cache mounts for faster rebuilds

Persist dependency caches across builds:

```dockerfile
FROM golang:1.22 AS builder
RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    go build -o /out/app ./cmd/server

FROM node:20 AS builder
RUN --mount=type=cache,target=/root/.npm \
    npm ci
```

Cache mounts survive between builds — dependency download skipped when lockfile unchanged. Requires BuildKit (`DOCKER_BUILDKIT=1`).

## Image size audit

Track image size in CI — alert on unexpected growth:

```bash
# Build and measure
docker build -t myapp:${{ github.sha }} .
SIZE=$(docker inspect myapp:${{ github.sha }} --format='{{.Size}}')
echo "Image size: $(( SIZE / 1024 / 1024 ))MB"

# Fail if size exceeds threshold
if [ $SIZE -gt 524288000 ]; then  # 500MB
  echo "Image size exceeds 500MB threshold"
  exit 1
fi
```

Layer analysis with `dive myapp:tag` — identify layers adding unexpected size.

## Failure modes

- **COPY --from=builder / /** — entire builder filesystem in production image
- **glibc binary on musl base** — runtime crash; match libc or compile statically
- **Root user in final stage** — security risk; set USER explicitly
- **Secrets in ENV or COPY** — visible in docker history; use BuildKit secrets
- **No .dockerignore** — node_modules and .git copied into build context

## Production checklist

- Final stage copies only required artifacts (binary, dist/, node_modules prod)
- Non-root USER set in final stage
- Distroless or alpine final stage (not full OS)
- BuildKit cache mounts for dependency layers
- .dockerignore excludes node_modules, .git, tests
- Image size tracked in CI with threshold alert

## Resources

- [Multi-stage builds (Docker documentation)](https://docs.docker.com/build/building/multi-stage/)
- [BuildKit secret mounts](https://docs.docker.com/build/building/buildkit/secrets/)
- [docker buildx multi-platform images](https://docs.docker.com/build/building/multi-platform/)
- [Google distroless images](https://github.com/GoogleContainerTools/distroless)
- [OCI image spec — layer structure](https://github.com/opencontainers/image-spec/blob/main/spec.md)
