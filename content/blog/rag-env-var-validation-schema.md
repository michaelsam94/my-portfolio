---
title: "RAG: Env Var Validation Schema"
slug: "rag-env-var-validation-schema"
description: "Validating environment variables at RAG service startup — Zod and envalid schemas, fail-fast config, and preventing silent misconfiguration in production."
datePublished: "2025-10-27"
dateModified: "2026-07-17"
tags: ["AI", "Rag", "Env"]
keywords: "rag, env, var, validation, schema, ai, production, engineering, architecture"
faq:
  - q: "Why validate environment variables at startup for RAG services?"
    a: "RAG pipelines depend on dozens of config values—embedding model names, API endpoints, index namespaces, chunk sizes, feature flags. A typo in PINECONE_INDEX or empty OPENAI_API_KEY often fails silently until first user query, wasting deploy cycles and mixing partial behavior across pods with inconsistent env from copy-paste errors."
  - q: "Which env vars should RAG config schemas treat as required versus optional?"
    a: "Required: credentials for embedding provider, vector store connection, corpus namespace, log level in prod. Optional with defaults: retry counts, cache TTLs, reranker enable flag. Forbidden in prod schemas: wildcard CORS origins, DISABLE_AUTH=true, empty redaction rule paths."
  - q: "Should validation run only at startup or on every request?"
    a: "Parse and validate once at process boot into an immutable config object. Reject boot if invalid. Hot reload of env without restart is rare in k8s—if supported, re-validate atomically before swapping config pointer. Never read raw process.env scattered through handlers."
---
Production pods booted green. Health checks passed. The first real retrieval request returned 500 because `EMBEDDING_MODEL` was unset and code fell back to a deprecated default not deployed in the index. Another pod in the same deployment had the correct env—load balancer luck sent 30% of users to broken instances. Helm values typo'd `PINECONE_INDEX` as `PINECOE_INDEX` in one overlay; CI never validated rendered manifests against a schema.

Environment variables are the configuration API of cloud-native RAG services. Without **schema validation at startup**, misconfiguration becomes a runtime lottery. **Zod**, **envalid**, **pydantic-settings**, and **envconfig** turn `.env` chaos into fail-fast errors during deploy—not during demo calls.

## Failure modes env validation prevents

| Misconfig | Without validation | With validation |
|-----------|-------------------|-----------------|
| Missing API key | 401 at first embed | Pod CrashLoopBackOff, alert |
| Wrong index name | Empty search results | Boot error: unknown namespace |
| `CHUNK_SIZE=abc` | NaN, weird chunks | Boot error: not a number |
| `LOG_LEVEL=debug` in prod | PII in logs for weeks | Boot error in prod profile |
| Conflicting flags | Reranker on, no model path | Boot error: dependency missing |

CrashLoopBackOff is desirable—it blocks bad deploys before traffic shifts.

## Schema design for RAG services

Group config by domain:

```typescript
// config.schema.ts
import { z } from "zod";

const embeddingSchema = z.object({
  EMBEDDING_PROVIDER: z.enum(["openai", "azure", "cohere", "local"]),
  EMBEDDING_MODEL: z.string().min(1),
  EMBEDDING_DIMENSIONS: z.coerce.number().int().positive(),
  OPENAI_API_KEY: z.string().min(1).optional(),
  AZURE_OPENAI_ENDPOINT: z.string().url().optional(),
}).refine(
  (data) => {
    if (data.EMBEDDING_PROVIDER === "openai") return !!data.OPENAI_API_KEY;
    if (data.EMBEDDING_PROVIDER === "azure") return !!data.AZURE_OPENAI_ENDPOINT;
    return true;
  },
  { message: "Provider-specific credentials required" }
);

const vectorStoreSchema = z.object({
  VECTOR_BACKEND: z.enum(["pinecone", "pgvector", "weaviate"]),
  PINECONE_INDEX: z.string().optional(),
  PINECONE_NAMESPACE: z.string().default("prod"),
  PGVECTOR_DSN: z.string().url().optional(),
});

const ragPipelineSchema = z.object({
  CHUNK_SIZE_TOKENS: z.coerce.number().int().min(64).max(8192).default(512),
  CHUNK_OVERLAP_TOKENS: z.coerce.number().int().min(0).default(64),
  RERANKER_ENABLED: z.coerce.boolean().default(false),
  RERANKER_MODEL_PATH: z.string().optional(),
  CORPUS_VERSION: z.string().regex(/^\d{4}-\d{2}-\d{2}$/),
});

export const envSchema = embeddingSchema
  .merge(vectorStoreSchema)
  .merge(ragPipelineSchema)
  .merge(z.object({
    NODE_ENV: z.enum(["development", "test", "production"]),
    LOG_LEVEL: z.enum(["debug", "info", "warn", "error"]),
  }))
  .refine(
    (e) => e.NODE_ENV !== "production" || e.LOG_LEVEL !== "debug",
    { message: "debug logging forbidden in production" }
  )
  .refine(
    (e) => !e.RERANKER_ENABLED || e.RERANKER_MODEL_PATH,
    { message: "RERANKER_MODEL_PATH required when reranker enabled" }
  );
```

Cross-field refinements catch logic errors single-field types miss.

## Boot-time loading pattern

```typescript
// config.ts
import { envSchema } from "./config.schema";

function loadConfig() {
  const parsed = envSchema.safeParse(process.env);
  if (!parsed.success) {
    console.error("Invalid configuration:", parsed.error.flatten());
    process.exit(1);
  }
  return Object.freeze(parsed.data);
}

export const config = loadConfig();
```

Import `config` everywhere—**never** `process.env.EMBEDDING_MODEL` in handlers. ESLint rule ban raw env access outside config module.

Python equivalent with pydantic-settings:

```python
from pydantic_settings import BaseSettings
from pydantic import Field, model_validator

class RagSettings(BaseSettings):
    embedding_model: str = Field(min_length=1)
    chunk_size_tokens: int = Field(ge=64, le=8192, default=512)
    corpus_version: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")

    @model_validator(mode="after")
    def reranker_requires_path(self):
        if self.reranker_enabled and not self.reranker_model_path:
            raise ValueError("reranker_model_path required")
        return self

settings = RagSettings()  # raises on import if invalid
```

## Environment profiles

Different strictness per `NODE_ENV`:

```typescript
const base = envSchema.parse(process.env);

const prodSchema = envSchema.extend({
  DISABLE_AUTH: z.literal("false").or(z.undefined()),
  CORS_ORIGINS: z.string().refine((s) => s !== "*", "wildcard CORS blocked in prod"),
});

export const config = (process.env.NODE_ENV === "production"
  ? prodSchema
  : envSchema
).parse(process.env);
```

Staging mirrors prod constraints—catch config errors before production.

## CI validation of rendered manifests

Helm/Kustomize output should validate before deploy:

```bash
helm template rag-api ./chart -f values-prod.yaml | \
  yq '.data | .[]' | \
  # extract ConfigMap env to JSON and validate against schema via node script
  node scripts/validate-env-json.js
```

Or **kubeconform** + custom JSON schema on ConfigMap keys. Typos in `PINECOE_INDEX` fail CI.

## Secrets versus config

Secrets (API keys) validate presence and format prefix (`sk-`) but load from secret stores—not committed `.env.example` values.

```typescript
OPENAI_API_KEY: z.string().startsWith("sk-").optional(),
```

Separate `config` (ConfigMap) from `secrets` (External Secrets Operator)—schema validates both at boot from merged env injection order documented in k8s manifest.

## Testing config schema

Unit tests feed invalid env objects:

```typescript
it("rejects chunk overlap >= chunk size", () => {
  expect(() => envSchema.parse({
    CHUNK_SIZE_TOKENS: "256",
    CHUNK_OVERLAP_TOKENS: "300",
    ...
  })).toThrow();
});
```

Snapshot valid minimal prod config—review when schema adds fields.

## Developer experience

Provide `.env.example` generated from schema descriptions (zod-to-json-schema + script). `pnpm config:check` validates local `.env` before `docker compose up`.

Document every variable in schema `.describe()` strings—feeds auto-generated docs.

## Observability

Log config summary at info level on boot—**redact secrets**:

```json
{ "embedding_model": "text-embedding-3-large", "vector_backend": "pinecone", "corpus_version": "2026-07-01" }
```

Include `config_hash` in readiness probe response for debugging pod skew—two pods with different hashes indicate rolling update stuck on bad ReplicaSet.

Env var validation schema turns "works on my laptop" into "fails in CI if prod config wrong." RAG services boot with dozens of interdependent settings; Zod or pydantic at startup catches missing API keys, typos in index names, and forbidden debug flags before users hit retrieval— not after half your pods silently serve empty search results.

## Twelve-factor alignment and secret rotation

When rotating embedding API keys, validate **overlap window** config: `OPENAI_API_KEY` plus `OPENAI_API_KEY_PREVIOUS` optional during rotation—schema accepts both, client tries primary then fallback. Remove previous key from schema required list after rotation completes.

Reject configs where production DSN points to `localhost` or staging hostnames via DNS suffix allowlist in schema refinement.

## Local development ergonomics

`envSchema.partial()` or separate `devEnvSchema` relaxes requirements—mock embedding provider enum value `local` skips API key. Production boot remains strict. Document in README generated from schema so new engineers do not copy prod `.env` to laptop.

Pre-commit hook runs `validate-env.ts` on staged `.env*` files—catch typos before push, not after deploy.

## Kubernetes admission integration

OPA/Gatekeeper policy rejects pods whose ConfigMap env fails JSON schema validation at admission—catch bad config before pods boot loop. Schema published as CRD versioned alongside application.

Helm chart values.schema.json generated from same Zod source as runtime config—single definition, dual consumption. Chart lint in CI prevents shipping invalid default values to staging clusters.

## Runtime config refresh edge cases

Some teams mount ConfigMap updates without pod restart—if supporting hot reload, atomic swap pointer to validated config struct after re-parse; in-flight requests finish on old config. Most RAG services prefer restart on config change for simplicity—document that ConfigMap change alone insufficient without rollout restart.

Feature flags from LaunchDarkly separate from env validation—flags toggle behavior; env defines infrastructure endpoints. Mixing flag and env for same concern (reranker on/off) creates confusion; schema docs clarify boundary.

Validated configuration is the cheapest insurance in RAG operations. One schema file prevents classes of outages that take longer to debug than to write: wrong index, missing API key, debug logging in prod. Invest in schema-first config early; retrofitting after dozens of microservices each reading raw env is a multi-sprint tax every growing platform pays eventually.

Schema evolution adds fields with defaults—never remove fields without major service version bump and coordinated deploy. Deprecation warnings logged at boot for renamed env vars give operators one release cycle to update Helm values before validation hardens.

## Acceptance criteria for env var validation schema

Ship only when staging demonstrates the failure modes you claim to handle. Record the evidence — load test output, chaos result, or screenshot of the alert firing — in the PR. Revisit the settings after the first real incident; production will teach you which timeout or retention value was optimistic. Prefer boring, documented tradeoffs over clever defaults that only exist in one engineer's head.
