"""Warm-up 2: pandas time series for cpm.py. Run it, read the output, then do the TODOs."""
from pathlib import Path

import numpy as np
import pandas as pd

rng = np.random.default_rng(7)
n = 1440
t = pd.date_range("2026-10-01 00:00", periods=n, freq="1min")

leak = np.where(np.arange(n) >= 600, 0.002, 0.0)
df = pd.DataFrame(
    {
        "PS1_FT101": 0.20 + rng.normal(0, 0.0002, n),
        "TRM_FT201": 0.20 - leak + rng.normal(0, 0.0002, n),
    },
    index=t,
)
df.index.name = "timestamp"

# Volume lost each minute, then summed over sliding windows
df["imb_m3"] = (df["PS1_FT101"] - df["TRM_FT201"]) * 60
df["imb_5min"] = df["imb_m3"].rolling("5min").sum()
df["imb_1h"] = df["imb_m3"].rolling("60min").sum()

print(df.head(3), "\n")
print("Around the leak start (10:00):")
print(df.loc["2026-10-01 09:58":"2026-10-01 10:02", ["imb_m3", "imb_5min"]], "\n")

# Hourly summary table, as you would put in the report
hourly = df["imb_m3"].resample("1h").sum()
print("Volume imbalance per hour (m3):")
print(hourly.round(2).to_string(), "\n")

# First time the 1 h window crossed an example threshold
threshold = 3.0  # m3, example only; cpm.py will derive this from uncertainty
over = df["imb_1h"] > threshold
first = over.idxmax() if over.any() else None
print(f"First time 1 h imbalance > {threshold} m3: {first}")

# Save and reload, the way generator.py and cpm.py will hand data over
out = Path(__file__).parent / "warmup.csv"
df.to_csv(out)
back = pd.read_csv(out, index_col="timestamp", parse_dates=True)
print(f"Reloaded {len(back)} rows; index type: {type(back.index).__name__}")

# TODO 1: How many minutes after 10:00 did the 1 h window cross 3.0 m3?
#         Work it out by hand first: 0.12 m3/min leak, so about how long to reach 3 m3?
# TODO 2: A 5 s clock skew can't be shown with 1-minute rows. Instead try
#         df["TRM_FT201"].shift(1) (a 1-minute skew). What happens to imb_m3 when
#         flow is constant? Then think: when would skew matter? (Answer: in B1/B3.)
# TODO 3: Set every TRM_FT201 value between 12:00 and 12:30 to the 12:00 value
#         (a frozen reading). Hint: df.loc["...":"...", "TRM_FT201"] = value
#         Does it show up in imb_5min?
