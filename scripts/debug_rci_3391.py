"""3391 RCI: verify KabuRadar matches SBI convention."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from kaburadar3.settings.encoding import read_csv
from kaburadar3.settings.loader import read_path_config
from kaburadar3.strategy import rci as tc_rci

results = Path(read_path_config("SHUUKEI", "PATH_HONBAN"))
df = read_csv(list(results.glob("code3391*.csv"))[0])
df = tc_rci.attach_rci(df, period=9, price_col="close")

print("3391 RCI9 (SBI-compatible):")
for _, row in df.tail(5).iterrows():
    d = str(row["Index"])[:10]
    print(f"  {d}  close={int(row['close'])}  RCI9={row['RCI9']:.2f}")
