"""Warm-up 3: the two-panel figure the report will use. Run it, open the PNG, then do the TODOs."""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # write files without needing a screen
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

rng = np.random.default_rng(7)
n = 1440
t = pd.date_range("2026-10-01 00:00", periods=n, freq="1min")
leak = np.where(np.arange(n) >= 600, 0.002, 0.0)
q_in = 0.20 + rng.normal(0, 0.0002, n)
q_out = 0.20 - leak + rng.normal(0, 0.0002, n)
df = pd.DataFrame({"q_in": q_in, "q_out": q_out}, index=t)
df["imb_1h"] = ((df["q_in"] - df["q_out"]) * 60).rolling("60min").sum()

threshold = 3.0  # m3, example only

fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True, figsize=(9, 5))
ax1.plot(df.index, df["q_in"] * 3600, lw=0.8, label="Inlet PS1_FT101")
ax1.plot(df.index, df["q_out"] * 3600, lw=0.8, label="Outlet TRM_FT201")
ax1.set_ylabel("Flow (m3/h)")
ax1.legend(loc="lower left")

ax2.plot(df.index, df["imb_1h"], lw=1.2, label="1 h imbalance")
ax2.axhline(threshold, ls="--", color="grey", label="Threshold (example)")
ax2.axvline(pd.Timestamp("2026-10-01 10:00"), ls=":", color="k", label="Leak starts")
ax2.set_ylabel("Volume (m3)")
ax2.legend(loc="upper left")

fig.suptitle("Synthetic data: 1% leak at 10:00")
fig.tight_layout()
out = Path(__file__).parent / "warmup_fig.png"
fig.savefig(out, dpi=150)
print(f"Saved {out}")

# TODO 1: Here the leak is easy to see in both panels because the noise is small.
#         Change both noise values from 0.0002 to 0.002 (10x) and re-run. The leak
#         nearly disappears from the top panel but stays clear in the bottom one.
#         Write one sentence explaining why (this is the whole point of a volume
#         balance, and a good interview line).
# TODO 2: Add a third panel with the 5 min window and its own threshold of 0.5 m3.
#         Does it alarm sooner or later than the 1 h window? Does it alarm falsely?
