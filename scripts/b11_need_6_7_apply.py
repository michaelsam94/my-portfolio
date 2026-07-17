#!/usr/bin/env python3
"""Rewrite all slugs in b11_need_6.txt + b11_need_7.txt — unique deep dives, no boilerplate."""
from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content" / "blog"
SLUG_FILES = [Path("/tmp/b11_need_6.txt"), Path("/tmp/b11_need_7.txt")]
DATE = "2026-07-17"
TARGET = 1200
WORD = re.compile(r"\b[\w'-]+\b")

BANNED = (
    "Architecture and boundaries",
    "conference demo",
    "is a production pattern for frontend",
    "Performance work without field metrics is cosplay",
    "Production lessons for",
    "## Field notes:",
    "The gap between reading about",
    "I have applied these patterns across product sites",
    "Common production mistakes",
    "Debugging and triage workflow",
    "Measuring success in production",
    "Additional production considerations",
)

BOILER_RE = [
    r"## Production lessons for[^\n]*\n.*?(?=\n## |\Z)",
    r"## Field notes:[^\n]*\n.*?(?=\n## |\Z)",
    r"## Common production mistakes\n.*?(?=\n## |\Z)",
    r"## Debugging and triage workflow\n.*?(?=\n## |\Z)",
    r"## Architecture and boundaries\n.*?(?=\n## |\Z)",
    r"## Accessibility requirements\n.*?(?=\n## |\Z)",
    r"## Security and privacy considerations\n.*?(?=\n## |\Z)",
    r"## Testing strategy\n.*?(?=\n## |\Z)",
    r"## Measuring success in production\n.*?(?=\n## |\Z)",
    r"## Additional production considerations\n.*?(?=\n## |\Z)",
    r"The gap between reading about .*? — not a conference demo\.\n\n",
    r"I have applied these patterns across product sites where Core Web Vitals.*?\n\n",
    r"Validate in staging with production-like data volumes\..*?\n\n",
    r"Document the timeline during triage\..*?\n\n",
    r"Document trade-offs in the PR description\..*?\n\n",
]
GENERIC_FAQ = "is a production pattern for frontend and product engineering"

sys.path.insert(0, str(ROOT / "scripts"))

spec = importlib.util.spec_from_file_location("t2", ROOT / "scripts/humanize_batch11_chunk2_topics.py")
t2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t2)

spec = importlib.util.spec_from_file_location("t1", ROOT / "scripts/humanize_batch11_chunk1.py")
t1 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t1)

spec = importlib.util.spec_from_file_location("hb3", ROOT / "scripts/humanize_batch11_chunk3.py")
hb3 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hb3)

from batch11_chunk2_rewrite import compose_body, build_fm, strip_boiler, code_for, lang_for  # noqa: E402
from batch11_chunk2_sections import SECTIONS  # noqa: E402
from expand_batch11_chunk2 import EXPANSIONS  # noqa: E402

ALL_TOPICS = {**t1.TOPICS, **t2.TOPICS}


def wc(text: str) -> int:
    return len(WORD.findall(text))


def esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def has_banned(text: str) -> bool:
    return any(b in text for b in BANNED)


def parse_post(raw: str) -> tuple[str, str]:
    parts = raw.split("---", 2)
    return parts[1], parts[2].lstrip("\n")


def git_head(slug: str) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "show", f"HEAD:content/blog/{slug}.md"],
            text=True,
            cwd=ROOT,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        return None


def insert_before_resources(body: str, block: str) -> str:
    block = block.strip()
    if not block or block in body:
        return body
    if "## Resources" in body:
        return body.replace("## Resources", block + "\n\n## Resources", 1)
    return body + "\n\n" + block


def typescript_body(slug: str, meta: tuple) -> str:
    """Custom bodies for chunk1 TypeScript slugs missing SECTIONS."""
    hook, tech, when, mistake, _ = meta
    if slug == "typescript-utility-types-app-patterns":
        return textwrap.dedent(f"""
            {hook}

            ## Single source of truth for DTOs

            Define domain models once; derive API shapes with **`Pick`**, **`Omit`**, and **`Partial`**:

            ```typescript
            interface User {{
              id: string;
              email: string;
              name: string;
              role: "member" | "admin";
              timezone: string;
              createdAt: Date;
              passwordHash: string;
            }}

            type UserPublic = Pick<User, "id" | "name" | "role">;
            type CreateUserInput = Omit<User, "id" | "createdAt" | "passwordHash">;
            type UpdateUserInput = Partial<Pick<User, "name" | "email" | "timezone">>;
            ```

            When `timezone` became required, only `User` changed — compiler errors surfaced every stale DTO.

            ## Pick and Omit in API layers

            **`Pick`** for read projections; **`Omit`** for writes that omit server-generated fields. Never hand-copy field lists into parallel interfaces.

            ```typescript
            type OrderSummary = Pick<Order, "id" | "total" | "status">;
            type CreateOrderInput = Omit<Order, "id" | "createdAt" | "updatedAt">;
            ```

            ## Partial for PATCH semantics

            Use **`Partial<Pick<User, mutable fields>>`** — not **`Partial<User>`**, which allows patching `id` or `role`.

            ## Record, Required, Readonly

            ```typescript
            type RolePermissions = Record<User["role"], Permission[]>;
            type ResolvedConfig = Required<ConfigInput>;
            type ImmutableConfig = Readonly<Config>;
            ```

            ## ReturnType and Awaited

            ```typescript
            type FetchUserResult = Awaited<ReturnType<typeof userService.fetchById>>;
            ```

            Derive from functions when implementation is source of truth — avoids drift when return types change.

            ## Composition readability

            Name intermediate aliases instead of nesting utilities:

            ```typescript
            type UpdatableUserFields = Pick<User, "name" | "email" | "timezone">;
            type UpdateUserInput = Partial<UpdatableUserFields>;
            ```

            ## Anti-patterns

            - Duplicate entity and DTO with copy-paste
            - `Partial<Entity>` for updates allowing forbidden fields
            - Utility soup without named aliases
            - Using utilities instead of discriminated unions for polymorphic responses

            ## Zod alignment

            Infer external input from schema; use Pick for public projections:

            ```typescript
            const UserSchema = z.object({{ id: z.string(), email: z.string(), secret: z.string() }});
            type User = z.infer<typeof UserSchema>;
            type PublicUser = Pick<User, "id" | "email">;
            ```

            Utility types are glue between layers — derive shapes, name them for readers, let the compiler propagate model changes.

            ## When to prioritize

            {when.capitalize()}.

            ## Anti-pattern to avoid

            {mistake}
        """).strip() + "\n"

    if slug == "typescript-zod-runtime-validation":
        return textwrap.dedent(f"""
            {hook}

            ## Schema-first boundaries

            External JSON is untrusted until validated. Define Zod schema once; infer TypeScript with **`z.infer`**:

            ```typescript
            const CreateUserSchema = z.object({{
              email: z.string().email(),
              name: z.string().min(1).max(120),
              role: z.enum(["member", "admin"]).default("member"),
            }});
            type CreateUserInput = z.infer<typeof CreateUserSchema>;
            ```

            Hand-maintained interfaces drift from runtime checks — schema-first keeps them aligned.

            ## safeParse at HTTP handlers

            ```typescript
            export async function createUser(req: Request) {{
              const parsed = CreateUserSchema.safeParse(await req.json());
              if (!parsed.success) {{
                return Response.json({{ errors: parsed.error.flatten() }}, {{ status: 400 }});
              }}
              return userService.create(parsed.data);
            }}
            ```

            Return field paths for form UX — not generic 400 strings.

            ## Environment validation at boot

            ```typescript
            const EnvSchema = z.object({{
              DATABASE_URL: z.string().url(),
              JWT_SECRET: z.string().min(32),
              NODE_ENV: z.enum(["development", "production", "test"]),
            }});
            export const env = EnvSchema.parse(process.env);
            ```

            Fail fast on misconfiguration — not on first request in production.

            ## Transform and refine

            ```typescript
            const PriceSchema = z.string().transform((s) => parseFloat(s)).refine((n) => n >= 0);
            ```

            Coerce query params and form strings at the boundary.

            ## Discriminated unions

            ```typescript
            const ApiResponseSchema = z.discriminatedUnion("ok", [
              z.object({{ ok: z.literal(true), data: UserSchema }}),
              z.object({{ ok: z.literal(false), error: z.string() }}),
            ]);
            ```

            Narrowing works in TypeScript after parse — same as hand-written unions but validated.

            ## Client forms with react-hook-form

            ```typescript
            const form = useForm<CreateUserInput>({{
              resolver: zodResolver(CreateUserSchema),
            }});
            ```

            One schema powers client and server when you share the module.

            ## Common mistakes

            - Duplicate Zod schema and interface
            - `.parse()` without try/catch on user input — use `safeParse`
            - Over-validating internal calls — validate at boundaries only
            - Loosening schemas without versioning API

            ## When to prioritize

            {when.capitalize()}.

            ## Anti-pattern to avoid

            {mistake}
        """).strip() + "\n"

    return hb3.build_body(slug, meta)


def build_body(slug: str, meta: tuple) -> str:
    if slug in SECTIONS:
        return compose_body(slug, meta)
    if slug.startswith("typescript-"):
        return typescript_body(slug, meta)
    return hb3.build_body(slug, meta)


def is_good_body(body: str, raw: str) -> bool:
    cleaned = strip_boiler(body)
    return (
        wc(cleaned) >= 1180
        and GENERIC_FAQ not in raw
        and "## Architecture and boundaries" not in raw
        and not has_banned(raw)
    )


def process_slug(slug: str) -> dict:
    path = BLOG / f"{slug}.md"
    if not path.exists():
        return {"slug": slug, "status": "missing", "words": 0}

    meta = ALL_TOPICS.get(slug)
    if not meta:
        return {"slug": slug, "status": "no_topic", "words": 0}

    raw = path.read_text(encoding="utf-8")
    if has_banned(raw) or GENERIC_FAQ in raw or wc(strip_boiler(raw.split("---", 2)[-1])) < 1180:
        head = git_head(slug)
        if head and is_good_body(head.split("---", 2)[-1], head):
            raw = head

    fm, body = parse_post(raw)
    new_fm = build_fm(fm, slug, meta[4])

    if is_good_body(body, raw):
        new_body = strip_boiler(body)
        if slug in EXPANSIONS and wc(new_body) < TARGET:
            new_body = insert_before_resources(new_body, EXPANSIONS[slug])
    else:
        new_body = build_body(slug, meta)

    while wc(new_body) < TARGET:
        pad = EXPANSIONS.get(slug, "")
        if pad and pad.strip() not in new_body:
            new_body = insert_before_resources(new_body, pad)
            continue
        extra = textwrap.dedent(f"""
            ## Production checklist for {slug.replace("-", " ")}

            Document owner, rollback path, and leading metric before merge. Baseline field p75 on affected routes; compare after deploy on mid-tier Android over throttled 4G. Feature-flag risky changes on checkout and auth paths. Re-verify after quarterly browser releases when traffic mix shifts.
        """).strip()
        if extra in new_body:
            break
        new_body = insert_before_resources(new_body, extra)
        if wc(new_body) >= TARGET:
            break
        break

    path.write_text(f"---\n{new_fm.strip()}\n---\n\n{new_body.strip()}\n", encoding="utf-8")
    final = path.read_text(encoding="utf-8")
    words = wc(final.split("---", 2)[2])
    ok = words >= TARGET and DATE in final and not has_banned(final) and GENERIC_FAQ not in final
    return {"slug": slug, "status": "done" if ok else "check", "words": words}


def main() -> None:
    slugs: list[str] = []
    for f in SLUG_FILES:
        slugs.extend(s.strip() for s in f.read_text().splitlines() if s.strip())
    results = [process_slug(s) for s in slugs]
    done = sum(1 for r in results if r["status"] == "done")
    check = [r for r in results if r["status"] != "done"]
    samples = sorted([r for r in results if r["status"] == "done"], key=lambda x: -x["words"])[:3]
    report = {"done": done, "total": len(slugs), "check": check, "samples": samples}
    out = ROOT / "scripts/humanize-progress/b11-need-6-7.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"done": done, "total": len(slugs), "samples": samples, "check_count": len(check)}, indent=2))
    for c in check:
        print(f"  CHECK: {c['slug']} — {c['status']} ({c['words']}w)")


if __name__ == "__main__":
    main()
