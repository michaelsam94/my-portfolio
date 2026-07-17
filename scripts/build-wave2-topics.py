#!/usr/bin/env python3
"""Build wave2-topics.json with 989 unique slugs."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content" / "blog"
existing = {f.stem for f in BLOG.glob("*.md")}

SEED = json.loads((ROOT / "scripts" / "wave2-seed-topics.json").read_text())
TERMS = json.loads((ROOT / "scripts" / "wave2-term-bank.json").read_text())

PATTERNS = {
    "AI": [("llm-{t}", "{T}"), ("rag-{t}", "RAG: {T}"), ("agent-{t}", "AI Agents: {T}")],
    "Backend": [("backend-{t}", "{T}"), ("api-{t}", "API Design: {T}"), ("grpc-{t}", "gRPC: {T}")],
    "Security": [("sec-{t}", "Security: {T}"), ("auth-{t}", "Authentication: {T}")],
    "Web": [("web-{t}", "{T}"), ("react-{t}", "React: {T}"), ("nextjs-{t}", "Next.js: {T}")],
    "Data": [("data-{t}", "Data Engineering: {T}"), ("postgres-{t}", "PostgreSQL: {T}")],
    "Platform": [("kubernetes-{t}", "Kubernetes: {T}"), ("terraform-{t}", "Terraform: {T}")],
    "IoT": [("iot-{t}", "IoT: {T}"), ("mqtt-{t}", "MQTT: {T}"), ("ocpp-{t}", "OCPP: {T}")],
    "Go": [("go-{t}", "Go: {T}")],
    "Rust": [("rust-{t}", "Rust: {T}")],
    "Python": [("python-{t}", "Python: {T}")],
    "Testing": [("testing-{t}", "Testing: {T}")],
    "Architecture": [("architecture-{t}", "Software Architecture: {T}")],
}

all_topics = []
seen = set(existing)

def add(slug, title, cat):
    if slug in seen:
        return
    seen.add(slug)
    all_topics.append({"slug": slug, "title": title, "category": cat})

for item in SEED:
    add(item["slug"], item["title"], item["category"])

for cat, patterns in PATTERNS.items():
    for term in TERMS:
        title_base = term.replace("-", " ").title()
        for pslug, ptitle in patterns:
            add(pslug.format(t=term), ptitle.format(T=title_base), cat)
            if len(all_topics) >= 989:
                break
        if len(all_topics) >= 989:
            break
    if len(all_topics) >= 989:
        break

topics = all_topics[:989]
(ROOT / "scripts" / "wave2-topics.json").write_text(json.dumps(topics, indent=2))
print(f"existing={len(existing)} new_topics={len(topics)} total_would_be={len(existing)+len(topics)}")
