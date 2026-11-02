"""Compensated volume balance (CPM).

Reads SCADA tags only, never the true_* columns. Synthetic data only.
"""
from pathlib import Path

import pandas as pd

from generator import TAGS, derived

DATA_DIR = Path(__file__).parent / "data"


def line_pack(df):
    """Line pack in m3 from the pressure and temperature tags (only changes matter).

    Average pressure: trapezoidal rule over transmitters at 0, 50 and 100 km.
    Average temperature: mean of the two ends.
    """
    g = derived()
    p_avg = (df[TAGS["p_in"]] + 2 * df[TAGS["p_mid"]] + df[TAGS["p_out"]]) / 4
    t_avg = (df[TAGS["t_in"]] + df[TAGS["t_out"]]) / 2
    return g["linepack_m3_per_mpa"] * p_avg - g["linepack_m3_per_c"] * t_avg


def balance(df, window_min=60, compensate=True):
    """Volume imbalance over a sliding window, in m3. Positive = oil unaccounted for.

    compensate=False gives the plain line balance (in minus out).
    compensate=True also subtracts the change in line pack over the window.
    NaN until the window is full.
    """
    vol_m3 = (df[TAGS["q_in"]] - df[TAGS["q_out"]]) * 60  # m3/s x 60 s = m3 each minute
    imb = vol_m3.rolling(window_min, min_periods=window_min).sum()
    if compensate:
        imb = imb - line_pack(df).diff(window_min)
    return imb


def alarms(imb, threshold_m3=3.0, persistence=3):
    """True from the Nth consecutive minute the imbalance is over the threshold.

    threshold_m3 = 3.0 is a placeholder until Part 6 derives it from uncertainty.
    """
    over = imb > threshold_m3
    run = over.astype(int).rolling(persistence, min_periods=persistence).sum()
    return run == persistence


def first_alarm(alarm):
    """Timestamp of the first alarm, or None."""
    return alarm.idxmax() if alarm.any() else None


if __name__ == "__main__":
    for name in ("case_pumpstart", "case_leak1"):
        df = pd.read_csv(DATA_DIR / f"{name}.csv", index_col="timestamp", parse_dates=True)
        print(name)
        for compensate in (False, True):
            imb = balance(df, 60, compensate)
            label = "compensated " if compensate else "line balance"
            print(f"  {label}: max 1 h imbalance {imb.max():6.2f} m3, first alarm {first_alarm(alarms(imb))}")