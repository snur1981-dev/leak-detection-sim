"""Compensated volume balance (CPM).

Reads SCADA tags only, never the true_* columns. Synthetic data only.
"""
from pathlib import Path

import pandas as pd

from generator import STATUS_TAGS, TAGS, derived

DATA_DIR = Path(__file__).parent / "data"

SETTINGS = {
    "windows_min": (5, 60, 1440),   # 5 min, 1 h, 24 h, evaluated every minute
    "persistence": 3,               # alarm on the 3rd consecutive exceedance
    "inhibit_min": 15,              # hold alarms for 15 min after a pump or valve status change
    "bias_allowance_pct": 0.1,      # residual meter bias assumed after proving
    "k_sigma": 3.0,                 # noise multiplier
    "q_nominal_m3s": 0.20,
    "thresholds_m3": {5: 3.0, 60: 3.0, 1440: 3.0},  # placeholders until tune() is run
}


# --- Part 4: the balance ---

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
    NaN until the window is full, and while any reading in it is missing.
    """
    vol_m3 = (df[TAGS["q_in"]] - df[TAGS["q_out"]]) * 60  # m3/s x 60 s = m3 each minute
    imb = vol_m3.rolling(window_min, min_periods=window_min).sum()
    if compensate:
        imb = imb - line_pack(df).diff(window_min)
    return imb


def alarms(imb, threshold_m3=3.0, persistence=3):
    """True from the Nth consecutive minute the imbalance is over the threshold."""
    over = imb > threshold_m3
    run = over.astype(int).rolling(persistence, min_periods=persistence).sum()
    return run == persistence


def first_alarm(alarm):
    """Timestamp of the first alarm, or None."""
    return alarm.idxmax() if alarm.any() else None


# --- Part 6: thresholds from a no-leak tuning run, three windows, persistence, inhibit ---

def tune(df_noleak, settings=SETTINGS):
    """Thresholds per window: bias allowance + k x (std dev of the compensated imbalance).

    T_W = b x Q x (60 x n) + k x sigma_W, with sigma_W measured on no-leak data, the way
    a real system is tuned. Returns (thresholds, sigmas), both dicts keyed by window minutes.
    """
    b = settings["bias_allowance_pct"] / 100
    q = settings["q_nominal_m3s"]
    sigmas, thresholds = {}, {}
    for w in settings["windows_min"]:
        sigmas[w] = balance(df_noleak, w, compensate=True).std()
        thresholds[w] = b * q * 60 * w + settings["k_sigma"] * sigmas[w]
    return thresholds, sigmas


def inhibit_mask(df, minutes):
    """True for `minutes` after any status tag changes (pump start/stop, valve move)."""
    status = df[[t for t in STATUS_TAGS if t in df.columns]]
    changed = status.diff().abs().sum(axis=1) > 0
    return changed.astype(int).rolling(minutes, min_periods=1).max().astype(bool)


def run_cpm(df, settings=SETTINGS, compensate=True, use_inhibit=True, bad=None):
    """Evaluate every window every minute. Returns imbalances, alarms and status flags.

    bad: optional True/False per minute from quality.check(); a window that contains a bad
    reading is suppressed and marked degraded rather than allowed to alarm.
    """
    out = pd.DataFrame(index=df.index)
    inhibit = inhibit_mask(df, settings["inhibit_min"]) if use_inhibit else pd.Series(False, index=df.index)
    out["inhibit"] = inhibit
    if bad is None:
        bad = pd.Series(False, index=df.index)
    for w in settings["windows_min"]:
        imb = balance(df, w, compensate)
        degraded = bad.astype(int).rolling(w + 1, min_periods=1).max().astype(bool)
        over = (imb > settings["thresholds_m3"][w]) & ~inhibit & ~degraded
        run = over.astype(int).rolling(settings["persistence"], min_periods=settings["persistence"]).sum()
        out[f"imb_{w}"] = imb
        out[f"alarm_{w}"] = run == settings["persistence"]
        out[f"degraded_{w}"] = degraded
    return out


def alarm_events(alarm):
    """Number of separate alarms (a run of alarm minutes counts once)."""
    return int((alarm & ~alarm.shift(fill_value=False)).sum())


if __name__ == "__main__":
    for name in ("case_pumpstart", "case_leak1"):
        df = pd.read_csv(DATA_DIR / f"{name}.csv", index_col="timestamp", parse_dates=True)
        print(name)
        for compensate in (False, True):
            imb = balance(df, 60, compensate)
            label = "compensated " if compensate else "line balance"
            print(f"  {label}: max 1 h imbalance {imb.max():6.2f} m3, first alarm {first_alarm(alarms(imb))}")
