import json
from collections import Counter, defaultdict
from pathlib import Path

trades = json.loads(Path("output/backtest_10y/trades.json").read_text(encoding="utf-8"))
dc = Counter(t["entry"][:10] for t in trades if t.get("closed"))
etf_by_day = {t["entry"][:10]: t for t in trades if t["code"] == "1306" and t.get("closed")}
days8 = [d for d, n in dc.items() if n >= 8]
missing = [d for d in days8 if d not in etf_by_day]
print(f"8+ days: {len(days8)}, 1306 entry same day: {len(days8)-len(missing)}, missing: {len(missing)}")
print("missing sample:", missing[:10])
