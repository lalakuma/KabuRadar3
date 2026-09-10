#!/usr/bin/env python3
import json
from pathlib import Path

EXCLUDE = {"2020"}
CACHE = Path(__file__).resolve().parents[1] / "output" / "optimize" / "ma5_grid_prev"
rows = []
for f in sorted(CACHE.glob("*.json")):
    if f.name == "grid_summary.json":
        continue
    trades = json.loads(f.read_text(encoding="utf-8"))
    closed = [t for t in trades if t.get("closed") and t["entry"][:4] not in EXCLUDE]
    wins = sum(1 for t in closed if t["gain"] > 0)
    total = sum(t["gain"] for t in closed)
    wr = round(wins / len(closed) * 100, 1) if closed else 0
    ma5 = sum(1 for t in closed if t.get("exit_reason") == "MA5")
    rows.append((wr, total, ma5, len(closed), f.stem))
rows.sort(reverse=True)
print("=== MA5 grid cached (2020除) ===")
for wr, total, ma5, n, name in rows:
    print(f"{name:>16}  勝率{wr:5.1f}%  損益{total:+10,}  MA5={ma5}  取引={n}")
if rows:
    print(f"\n最高勝率: {rows[0][4]} -> {rows[0][0]}%")
