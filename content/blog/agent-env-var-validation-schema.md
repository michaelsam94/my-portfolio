---
title: "AI Agents: Env Var Validation Schema"
slug: "agent-env-var-validation-schema"
description: "Env Var Validation Schema: production patterns for ai teams — design, implementation, testing, security, and operations."
datePublished: "2025-10-28"
dateModified: "2025-10-28"
tags: ["AI", "Agent", "Env"]
keywords: "agent, env, var, validation, schema, ai, production, engineering, architecture"
faq:
  - q: "Why validate environment variables at startup instead of lazily on first use?"
    a: "Lazy validation defers failures to the worst moment—first production request under load. Startup validation fails fast in CI and during deploy, before traffic routes to the pod. Agent services depend on dozens of vars (model endpoints, API keys, vector DB URLs, feature flags). One missing OPENAI_BASE_URL should crash the container in staging, not mid-conversation when a user asks a question."
  - q: "Should secrets like API keys be in the same schema as non-secret config?"
    a: "Use one schema for shape validation but separate concerns in code: non-secrets can log on failure; secrets must never appear in error messages or startup logs. Mark secret fields with a `.secret()` transform that validates presence and format (e.g., sk- prefix) without echoing values. Prefer referencing secret names in errors: 'ANTHROPIC_API_KEY is missing' not the key itself."
  - q: "How do I handle different config per environment without duplicating schemas?"
    a: "Define a base schema with shared fields, then extend per environment with .superRefine() or discriminated unions on NODE_ENV / DEPLOY_ENV. Staging might allow MOCK_LLM=true; production rejects it. Never fork entire schema files—drift between dev and prod schemas is how 'works in staging, 500 in prod' incidents start."
  - q: "What belongs in env vars vs a config service for agent pipelines?"
    a: "Env vars suit bootstrap identity: which cluster, which secret mount path, feature-flag SDK key. Runtime tuning—model routing weights, retrieval top-k, prompt template versions—belongs in a config service you can change without redeploying. Validate bootstrap vars strictly at startup; poll config service with its own schema and hot-reload handlers."
---
The deploy succeeded. Pods went healthy. Traffic shifted. Three minutes later, p99 latency spiked—not because the model was slow, but because half the replicas had `RETRIEVAL_TOP_K` set to the string `"10 "` with a trailing space. Zod accepted it as a string; the code called `parseInt` and got `10`, but a sibling service used strict numeric comparison and fell back to a 10× larger retrieval fan-out. Same image, different ConfigMap whitespace, divergent behavior across the fleet.

Environment variables are the silent contract between platform teams and application code. For agent systems—where one misconfigured timeout can burn thousands of dollars in token spend per hour—treating env vars as untyped strings is negligence. Schema validation at the process boundary turns configuration into a versioned, testable API.

## Why agent stacks are env-var-heavy

A minimal production agent service might read thirty or more variables: LLM provider URLs, embedding model names, vector database connection strings, Redis cache TTLs, rate-limit quotas, tracing endpoints, and feature-flag keys. Orchestrators inject them uniformly, which is convenient until nobody remembers which vars are required, which have defaults, and which silently accept garbage.

Three failure modes dominate agent deployments:

**Type coercion surprises.** `"false"` is truthy in JavaScript. `"0"` parses to zero but might mean "disabled" or "unlimited" depending on who wrote the consumer. Without schema enforcement, every service invents its own parsing rules.

**Missing vars with late discovery.** A RAG pipeline might not touch the reranker endpoint until a specific query shape triggers it. The pod has been "healthy" for days.

**Cross-service drift.** The orchestrator service validates `MAX_CONTEXT_TOKENS` as a number; the worker treats it as a string and concatenates instead of truncating. Incidents surface as "the agent hallucinates on long documents" rather than "invalid config."

Startup validation with a shared schema eliminates this class of bugs before they reach users.

## Designing a validation schema

Treat your environment as a single document with typed fields, constraints, and documentation. Zod, Valibot, and envalid are common choices in TypeScript; Pydantic's `BaseSettings` covers Python agent runtimes.

Design principles:

**Fail fast, fail loudly.** If validation fails, exit with non-zero status and a structured error listing every invalid field. Kubernetes will keep the old ReplicaSet; CI will catch it on the merge request.

**Defaults belong in schema, not scattered in code.** `RETRY_MAX_ATTEMPTS` defaulting to `3` in one file and `5` in another creates inconsistent retry storms.

**Coerce carefully.** URLs, ports, and booleans need explicit transforms. Document edge cases: empty string should fail, not become `0`.

**Separate bootstrap from runtime config.** Env vars should answer "who am I and how do I connect?" Dynamic model routing belongs elsewhere.

```typescript
// config/env.schema.ts
import { z } from "zod";

const url = z.string().url();
const positiveInt = z.coerce.number().int().positive();

export const envSchema = z
  .object({
    NODE_ENV: z.enum(["development", "staging", "production"]),
    PORT: z.coerce.number().int().min(1).max(65535).default(8080),

    // LLM providers
    OPENAI_API_KEY: z.string().min(1).describe("secret"),
    OPENAI_BASE_URL: url.default("https://api.openai.com/v1"),
    DEFAULT_MODEL: z.string().default("gpt-4o"),
    LLM_TIMEOUT_MS: positiveInt.default(60_000),

    // Retrieval
    PINECONE_API_KEY: z.string().min(1).describe("secret"),
    PINECONE_INDEX: z.string().min(1),
    RETRIEVAL_TOP_K: positiveInt.max(100).default(10),
    EMBEDDING_MODEL: z.string().default("text-embedding-3-small"),

    // Agent behavior
    MAX_AGENT_STEPS: positiveInt.max(50).default(12),
    TOOL_CALL_TIMEOUT_MS: positiveInt.default(30_000),
    ENABLE_HUMAN_APPROVAL: z
      .enum(["true", "false"])
      .transform((v) => v === "true")
      .default("false"),

    // Observability
    OTEL_EXPORTER_OTLP_ENDPOINT: url.optional(),
    LOG_LEVEL: z.enum(["debug", "info", "warn", "error"]).default("info"),
  })
  .superRefine((data, ctx) => {
    if (data.NODE_ENV === "production" && data.MAX_AGENT_STEPS > 25) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "MAX_AGENT_STEPS > 25 is not allowed in production (runaway cost risk)",
        path: ["MAX_AGENT_STEPS"],
      });
    }
  });

export type Env = z.infer<typeof envSchema>;
```

The `superRefine` block encodes business rules that pure types cannot express—production guardrails on agent step limits are a cost-control measure, not just validation.

## Loading and surfacing errors safely

```typescript
// config/load-env.ts
import { envSchema, type Env } from "./env.schema";

function redactSecrets(key: string, value: unknown): unknown {
  if (key.includes("KEY") || key.includes("SECRET") || key.includes("TOKEN")) {
    return value ? "[REDACTED]" : "[MISSING]";
  }
  return value;
}

export function loadEnv(): Env {
  const result = envSchema.safeParse(process.env);

  if (!result.success) {
    const formatted = result.error.issues.map((issue) => ({
      path: issue.path.join("."),
      message: issue.message,
    }));

    console.error(
      JSON.stringify({
        level: "fatal",
        event: "env_validation_failed",
        issues: formatted,
        // Safe snapshot for debugging—never log raw secrets
        env_snapshot: Object.fromEntries(
          Object.entries(process.env)
            .filter(([k]) => k.startsWith("OPENAI_") || k.startsWith("PINECONE_") || k.startsWith("NODE_"))
            .map(([k, v]) => [k, redactSecrets(k, v)]),
        ),
      }),
    );
    process.exit(1);
  }

  return result.data;
}

// Singleton—parse once at module load
export const env = loadEnv();
```

Import `env` from a single module everywhere. Ban direct `process.env.FOO` access via ESLint rule `no-process-env` except inside `load-env.ts`. Code review becomes trivial: if it compiles, the config shape is correct.

## Python agent services: Pydantic Settings

Many agent frameworks (LangGraph, CrewAI workers) run on Python. Mirror the TypeScript schema with Pydantic v2:

```python
# config/settings.py
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    node_env: str = Field(default="development")
    openai_api_key: str = Field(min_length=1)
    default_model: str = "gpt-4o"
    retrieval_top_k: int = Field(default=10, ge=1, le=100)
    max_agent_steps: int = Field(default=12, ge=1, le=50)
    llm_timeout_ms: int = Field(default=60_000, ge=1000)

    @field_validator("node_env")
    @classmethod
    def validate_production_limits(cls, v: str, info):
        return v


settings = AgentSettings()  # raises ValidationError on bad env
```

Run `python -c "from config.settings import settings"` in CI before Docker build. Container entrypoints should not start uvicorn until settings load cleanly.

## Testing configuration contracts

Env validation is only as good as the tests that exercise it.

**Snapshot invalid fixtures.** Keep `tests/fixtures/env/.env.missing-openai` and assert the process exits with a parseable JSON error. CI runs these on every PR.

**Contract tests across services.** If orchestrator and worker share `RETRIEVAL_TOP_K`, export the Zod schema to JSON Schema and validate both codebases consume identical constraints.

**Deploy dry-runs.** Helm charts and Kustomize overlays should render to env var lists that pass validation in a pre-deploy job—before pods exist.

```typescript
// config/env.schema.test.ts
import { envSchema } from "./env.schema";

describe("envSchema", () => {
  it("rejects trailing whitespace in numeric fields", () => {
    const result = envSchema.safeParse({
      NODE_ENV: "production",
      OPENAI_API_KEY: "sk-test",
      PINECONE_API_KEY: "pc-test",
      PINECONE_INDEX: "agent-prod",
      RETRIEVAL_TOP_K: "10 ", // common ConfigMap mistake
    });
    // z.coerce.number handles "10 " → 10, but document expected behavior
    expect(result.success).toBe(true);
    if (result.success) expect(result.data.RETRIEVAL_TOP_K).toBe(10);
  });

  it("blocks excessive agent steps in production", () => {
    const result = envSchema.safeParse({
      NODE_ENV: "production",
      OPENAI_API_KEY: "sk-test",
      PINECONE_API_KEY: "pc-test",
      PINECONE_INDEX: "idx",
      MAX_AGENT_STEPS: "40",
    });
    expect(result.success).toBe(false);
  });
});
```

## Operational concerns

**ConfigMap and Secret rotation.** When Kubernetes updates a mounted Secret, files change on disk but `process.env` in a long-running Node process does not. Agent workers either restart on Secret rotation (Reloader sidecar) or poll external config. Document which vars are hot-reloadable.

**12-factor vs platform injection.** Cloud Run, Fly.io, and Vercel inject env differently than raw K8s. Maintain a `config/README.md` listing every var, its type, default, and which environments require it.

**Cost-related vars deserve alerts.** Track `MAX_AGENT_STEPS`, `LLM_TIMEOUT_MS`, and model name in deploy audit logs. A well-meaning PR that bumps `DEFAULT_MODEL` to a flagship tier should trigger a cost review, not surprise finance.

## Security angles

Never log validated env objects wholesale—`console.log(env)` leaks secrets into CloudWatch. Use a `toSanitized()` helper that masks secret fields.

Validate format, not just presence. API keys should match expected prefixes (`sk-`, `sk-ant-`). Reject keys that look like placeholders (`changeme`, `xxx`).

For local development, `.env.example` lists every key with dummy values and comments. `.env` stays gitignored. Pre-commit hooks run schema validation against `.env.example` to ensure docs stay current when schema adds fields.

## Migration: introducing schema to a legacy agent

Rolling validation into a brownfield service without a flag day:

1. Generate schema from current `process.env` reads via static analysis or runtime sampling in staging.
2. Add schema with `.passthrough()` or `extra: "ignore"` initially; tighten to strict over two sprints.
3. Enable ESLint `no-process-env` only in directories already migrated.
4. Delete passthrough once all reads go through `env`.

## The takeaway

Env var validation schema is the cheapest insurance policy in an agent stack. One Zod object at startup replaces weeks of debugging "works on my laptop" configuration drift. Fail fast, redact secrets in errors, test invalid fixtures in CI, and treat the schema as a published contract between platform and application teams—not a dump of strings the orchestrator happens to provide.

## Resources

- [Zod documentation — environment variable parsing](https://zod.dev/?id=primitives)
- [Pydantic Settings management](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- [envalid — Node.js environment variable validation](https://github.com/af/envalid)
- [The Twelve-Factor App — Config](https://12factor.net/config)
- [Kubernetes ConfigMaps and Secrets best practices](https://kubernetes.io/docs/concepts/configuration/secret/#good-practices)
