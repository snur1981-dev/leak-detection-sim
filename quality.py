"""Data quality checks, run before the balance.

A CPM should not turn bad data into a leak alarm, and should say when it is blind.
These checks are causal: each minute is judged only on readings up to that minute.
"""
import pandas as pd

from generator import TAGS

# Plausible ranges for this pipeline (instrument span, not operating limits)
RANGES = {
    TAGS["q_in"]: (0.0, 0.40), TAGS["q_out"]: (0.0, 0.40),               # m3/s
    TAGS["p_in"]: (-0.1, 10.0), TAGS["p_mid"]: (-0.1, 10.0), TAGS["p_out"]: (-0.1, 10.0),  # MPa
    TAGS["t_in"]: (-20.0, 60.0), TAGS["t_out"]: (-20.0, 60.0),           # degC
}


def check(df, frozen_n=10):
    """Flag bad readings. Returns a DataFrame of True/False flags per tag and check, plus 'bad'.

    missing:  the reading is NaN (comms dropout)
    frozen:   the reading has not changed for frozen_n readings in a row (real noise always moves it)
    range:    the reading is outside its instrument range
    """
    flags = pd.DataFrame(index=df.index)
    for tag, (lo, hi) in RANGES.items():
        x = df[tag]
        flags[f"{tag}_missing"] = x.isna()
        unchanged = (x.diff() == 0).astype(int)
        flags[f"{tag}_frozen"] = unchanged.rolling(frozen_n - 1, min_periods=frozen_n - 1).sum() == frozen_n - 1
        flags[f"{tag}_range"] = x.notna() & ((x < lo) | (x > hi))
    flags["bad"] = flags.any(axis=1)
    return flags


def summary(flags):
    """Minutes flagged, per check type."""
    out = {}
    for kind in ("missing", "frozen", "range"):
        cols = [c for c in flags.columns if c.endswith(f"_{kind}")]
        out[kind] = int(flags[cols].any(axis=1).sum())
    out["bad"] = int(flags["bad"].sum())
    return out
