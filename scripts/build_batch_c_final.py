#!/usr/bin/env python3
"""Build generate_batch_c_posts.py with 250 inline topic tuples."""
from pathlib import Path

ROOT = Path(__file__).parent
OUT = ROOT / "generate_batch_c_posts.py"

# Import k8s topics from _mk_batch_c
ns = {}
exec((ROOT / "_mk_batch_c.py").read_text().split("print(")[0], ns)
RAW = list(ns["RAW"])

# Import rest via exec of topic batches
for batch_file in ["_topics_rest.py", "_topics_batch2.py", "_topics_batch3.py", "_topics_batch4.py", "_topics_batch5.py"]:
    p = ROOT / batch_file
    if p.exists():
        bns = {"R": RAW.append}
        exec(f"def add_rest(R):\n    pass\n" + p.read_text(), bns)
        if "add_rest" in bns:
            bns["add_rest"](RAW.append)

print(f"RAW count before generation: {len(RAW)}")
