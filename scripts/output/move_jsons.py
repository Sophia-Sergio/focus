#!/usr/bin/env python3
"""Move all .json from digitalizadas to jsons preserving folder structure."""
import os
from pathlib import Path

base = Path("/Users/sergiotorres/code/focus")
src_root = base / "digitalizadas"
dst_root = base / "jsons"

dst_root.mkdir(parents=True, exist_ok=True)
moved = 0
for f in src_root.rglob("*.json"):
    if not f.is_file():
        continue
    rel = f.relative_to(src_root)
    dest = dst_root / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    f.rename(dest)
    moved += 1
    if moved % 500 == 0:
        print(moved, "files moved...")
print("Done. Total moved:", moved)
