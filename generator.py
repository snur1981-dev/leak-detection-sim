"""Test pipeline parameters and the synthetic SCADA data generator.

Synthetic data only: a simplified hydraulic model, not a real pipeline or SCADA system.
"""
import math
from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).parent / "data"

# Test pipeline (see README). SI units throughout.
PIPE = {
    "length_m": 100_000.0,
    "od_m": 0.4064,          # NPS 16
    "wall_m": 0.0079,
    "roughness_m": 0.045e-3,  # 0.045 mm
    "steel_E_pa": 200e9,
}
FLUID = {
    "density_kgm3": 850.0,
    "nu_m2s": 1.0e-5,        # 10 cSt, assumed
    "bulk_modulus_pa": 1.4e9,
    "beta_per_c": 8e-4,      # thermal expansion, assumed
}
OPERATION = {"flow_m3s": 0.20, "p_out_mpa": 0.5}
METERS = {"flow_uncertainty_pct": 0.5}

TAGS = {
    "q_in": "PS1_FT101", "q_out": "TRM_FT201",
    "p_in": "PS1_PT101", "p_mid": "MID_PT201", "p_out": "TRM_PT301",
    "t_in": "PS1_TT101", "t_out": "TRM_TT201",
}
STATUS_TAGS = ["PS1_PUMP_ST", "TRM_XV201"]
OUTLET_TAGS = [TAGS["q_out"], TAGS["p_out"], TAGS["t_out"]]  # all read through the terminal RTU


def derived(pipe=PIPE, fluid=FLUID):
    """Geometry and line pack numbers used everywhere else."""
    d = pipe["od_m"] - 2 * pipe["wall_m"]
    area = math.pi / 4 * d ** 2
    vol = area * pipe["length_m"]
    fluid_term = 1 / fluid["bulk_modulus_pa"]
    pipe_term = d / (pipe["steel_E_pa"] * pipe["wall_m"])
    return {
        "id_m": d,
        "area_m2": area,
        "volume_m3": vol,
        "linepack_m3_per_mpa": vol * (fluid_term + pipe_term) * 1e6,
        "linepack_m3_per_c": vol * fluid["beta_per_c"],
    }


def friction_factor(re, rel_rough):
    """Darcy friction factor by Swamee-Jain (turbulent flow).

    re: Reynolds number (dimensionless). rel_rough: roughness / diameter (dimensionless).
    """
    return 0.25 / math.log10(rel_rough / 3.7 + 5.74 / re ** 0.9) ** 2


def steady_state(q_m3s, p_out_mpa=OPERATION["p_out_mpa"], pipe=PIPE, fluid=FLUID):
    """Steady flow on a flat line: velocity, Re, f, friction loss and pressures (MPa)."""
    g = derived(pipe, fluid)
    v = q_m3s / g["area_m2"]
    re = v * g["id_m"] / fluid["nu_m2s"]
    f = friction_factor(re, pipe["roughness_m"] / g["id_m"])
    dp_pa = f * (pipe["length_m"] / g["id_m"]) * fluid["density_kgm3"] * v ** 2 / 2
    dp_mpa = dp_pa / 1e6
    return {
        "v_ms": v,
        "re": re,
        "f": f,
        "dp_mpa": dp_mpa,
        "p_in_mpa": p_out_mpa + dp_mpa,
        "p_mid_mpa": p_out_mpa + dp_mpa / 2,   # straight-line profile, midpoint
        "p_out_mpa": p_out_mpa,
        "p_avg_mpa": p_out_mpa + dp_mpa / 2,   # average of a straight line = midpoint
    }


def wave_speed(pipe=PIPE, fluid=FLUID):
    """Pressure wave speed in m/s, slowed by pipe elasticity."""
    d = derived(pipe, fluid)["id_m"]
    k = fluid["bulk_modulus_pa"]
    return math.sqrt((k / fluid["density_kgm3"]) / (1 + k * d / (pipe["steel_E_pa"] * pipe["wall_m"])))


def check_hand_calcs():
    """Check the code against my hand calculations."""
    def close(got, want, tol_frac):
        assert abs(got - want) <= tol_frac * want, f"got {got:.4f}, expected {want}"

    close(steady_state(0.10)["dp_mpa"], 1.76, 0.01)
    close(steady_state(0.15)["dp_mpa"], 3.64, 0.01)
    close(steady_state(0.20)["dp_mpa"], 6.10, 0.01)
    close(steady_state(0.20)["p_in_mpa"], 6.60, 0.01)
    assert abs(derived()["linepack_m3_per_mpa"] - 11.52) <= 0.01
    close(wave_speed(), 1106, 0.01)
    print("All hand-check asserts passed.")


def flow_profile(n, q_start, events):
    """True inlet flow each minute: q_start, then straight-line ramps from the event list.

    events: list of (kind, start_min, duration_min, q_from, q_to), in time order.
    """
    t_pts, q_pts = [0], [q_start]
    for _kind, start_min, dur_min, q_from, q_to in events:
        t_pts += [start_min, start_min + dur_min]
        q_pts += [q_from, q_to]
    t_pts.append(n - 1)
    q_pts.append(q_pts[-1])
    return np.interp(np.arange(n), t_pts, q_pts)


def make_case(duration_h=24, q_m3s=OPERATION["flow_m3s"], leak_pct=0.0, leak_start_min=None,
              noise_m3s=0.0002, bias_pct=(0.0, 0.0), p_noise_mpa=0.005, t_noise_c=0.02,
              t_c=15.0, events=None, seed=0, start="2026-10-01 00:00"):
    """Synthetic 1-minute SCADA data for one test case.

    q_m3s: starting flow. events: optional ramps, e.g. [("pump_start", 360, 10, 0.10, 0.20)].
    leak_pct: leak size as % of normal flow, 0.20 m3/s (1.0 means 1%). leak_start_min: when it starts.
    bias_pct: (inlet, outlet) meter bias in % of reading. noise_m3s: std dev of each meter's noise.
    Returns a DataFrame: one column per SCADA tag, plus true_* columns used only for scoring.
    """
    rng = np.random.default_rng(seed)
    n = int(duration_h * 60)
    minute = np.arange(n)
    index = pd.date_range(start, periods=n, freq="1min", name="timestamp")
    events = events or []
    g = derived()

    # True flow, pressures and line pack, minute by minute (quasi-steady)
    q_in = flow_profile(n, q_m3s, events)
    states = [steady_state(q) for q in q_in]
    p_in = np.array([s["p_in_mpa"] for s in states])
    p_mid = np.array([s["p_mid_mpa"] for s in states])
    p_out = np.array([s["p_out_mpa"] for s in states])
    p_avg = np.array([s["p_avg_mpa"] for s in states])
    t_avg = np.full(n, t_c)
    lp = g["linepack_m3_per_mpa"] * p_avg - g["linepack_m3_per_c"] * t_avg  # m3 (only changes matter)

    leak = np.zeros(n)
    if leak_start_min is not None:
        leak = np.where(minute >= leak_start_min, OPERATION["flow_m3s"] * leak_pct / 100, 0.0)

    # out = in - leak - change in line pack
    dlp_dt = np.diff(lp, prepend=lp[0]) / 60  # m3/s
    q_out = q_in - leak - dlp_dt

    # Status tags. PS1_PUMP_ST: 1 = second pump running. TRM_XV201 flips on each valve move.
    # "setpoint" events change flow without a status change, so they don't trigger the inhibit.
    pump_kinds = [k for k, *_ in events if k in ("pump_start", "pump_stop")]
    pump_st = np.full(n, 1.0 if pump_kinds[:1] == ["pump_stop"] else 0.0)
    valve_st = np.ones(n)
    for kind, start_min, *_ in events:
        if kind == "pump_start":
            pump_st[start_min:] = 1
        elif kind == "pump_stop":
            pump_st[start_min:] = 0
        elif kind == "valve":
            valve_st[start_min:] = 1 - valve_st[start_min]

    # Measured = true x (1 + bias) + noise, separate noise for each meter
    bias_in, bias_out = bias_pct
    meas_in = q_in * (1 + bias_in / 100) + rng.normal(0, noise_m3s, n)
    meas_out = q_out * (1 + bias_out / 100) + rng.normal(0, noise_m3s, n)

    def noisy(value, sd):
        return value + rng.normal(0, sd, n)

    df = pd.DataFrame({
        TAGS["q_in"]: meas_in,
        TAGS["q_out"]: meas_out,
        TAGS["p_in"]: noisy(p_in, p_noise_mpa),
        TAGS["p_mid"]: noisy(p_mid, p_noise_mpa),
        TAGS["p_out"]: noisy(p_out, p_noise_mpa),
        TAGS["t_in"]: noisy(t_c, t_noise_c),
        TAGS["t_out"]: noisy(t_c, t_noise_c),
        "PS1_PUMP_ST": pump_st,
        "TRM_XV201": valve_st,
        "true_q_in": q_in,
        "true_q_out": q_out,
        "true_leak": leak,
        "true_lp": lp,
    }, index=index)
    return df


def check_case_leak1(df):
    """Checks for the 1% leak case (no meter bias)."""
    assert len(df) == 1440 and df.shape[1] == 13 and not df.isna().any().any()
    after = df.iloc[600:]
    diff = (after[TAGS["q_in"]] - after[TAGS["q_out"]]).mean()
    assert abs(diff - 0.0020) <= 0.0001, f"mean imbalance after leak {diff:.5f}"
    sd = df[TAGS["q_in"]].std()
    assert abs(sd - 0.0002) <= 0.1 * 0.0002, f"inlet noise std {sd:.6f}"
    print(f"Leak case OK: mean in-out after leak {diff:.5f} m3/s, inlet std {sd:.6f} m3/s")


def check_case_pumpstart(df):
    """Checks for the pump start case: hand calcs and conservation."""
    p_avg = (df["true_lp"] + derived()["linepack_m3_per_c"] * 15.0) / derived()["linepack_m3_per_mpa"]
    dp_avg = p_avg.iloc[-1] - p_avg.iloc[0]
    dlp = df["true_lp"].iloc[-1] - df["true_lp"].iloc[0]
    stored = ((df["true_q_in"] - df["true_q_out"]) * 60).sum()
    assert abs(dp_avg - 2.17) <= 0.02 * 2.17, f"avg pressure rise {dp_avg:.3f} MPa"
    assert abs(dlp - 25.0) <= 0.02 * 25.0, f"line pack rise {dlp:.2f} m3"
    assert abs(stored - dlp) <= 0.01, f"in-out {stored:.3f} vs line pack {dlp:.3f}"
    print(f"Pump start case OK: avg pressure +{dp_avg:.2f} MPa, line pack +{dlp:.1f} m3, "
          f"in minus out over the day {stored:.2f} m3")


# SCADA effects and instrument faults, applied to a finished case

def apply_skew(df, seconds, tags=OUTLET_TAGS):
    """Outlet clock runs `seconds` late: each outlet reading shows the value from s seconds earlier.

    Linear interpolation between 1-minute readings: x(t - s) ~ x(t) - (s / 60) * (x(t) - x(t - 1 min)).
    Valid for 0 <= s <= 60.
    """
    out = df.copy()
    for tag in tags:
        out[tag] = out[tag] - (seconds / 60) * out[tag].diff().fillna(0)
    return out


def apply_deadband(values, db):
    """Report-by-exception: hold the last reported value until the reading moves more than db."""
    x = np.asarray(values, dtype=float)
    out = x.copy()
    last = x[0]
    for i in range(len(x)):
        if abs(x[i] - last) > db:
            last = x[i]
        out[i] = last
    return out


def add_drift(df, tag, pct_per_day, start_min=0):
    """Meter calibration drifts by pct_per_day (signed) from start_min onward."""
    out = df.copy()
    days = np.clip((np.arange(len(out)) - start_min) / 1440, 0, None)
    out[tag] = out[tag] * (1 + pct_per_day / 100 * days)
    return out


def add_frozen(df, tag, start_min, minutes):
    """The tag repeats the same value for `minutes` (stuck transmitter or stale SCADA value)."""
    out = df.copy()
    col = out.columns.get_loc(tag)
    out.iloc[start_min:start_min + minutes, col] = out.iloc[start_min, col]
    return out


def add_dropout(df, tags, start_min, minutes):
    """Comms outage: the tags are missing (NaN) for `minutes`."""
    out = df.copy()
    for tag in tags:
        col = out.columns.get_loc(tag)
        out.iloc[start_min:start_min + minutes, col] = np.nan
    return out


if __name__ == "__main__":
    for k, v in derived().items():
        print(f"{k:22s} {v:,.4f}")
    print()
    print(f"{'Q (m3/s)':>9} {'v (m/s)':>8} {'Re':>8} {'f':>7} {'dP (MPa)':>9} {'P_in (MPa)':>10}")
    for q in (0.10, 0.15, 0.20):
        s = steady_state(q)
        print(f"{q:9.2f} {s['v_ms']:8.3f} {s['re']:8.0f} {s['f']:7.4f} {s['dp_mpa']:9.2f} {s['p_in_mpa']:10.2f}")
    a = wave_speed()
    print(f"\nWave speed {a:,.0f} m/s; crosses 100 km in {PIPE['length_m'] / a:.0f} s")
    print()
    check_hand_calcs()

    # 1% leak case
    DATA_DIR.mkdir(exist_ok=True)
    case = make_case(leak_pct=1.0, leak_start_min=600, seed=1)
    case.to_csv(DATA_DIR / "case_leak1.csv")
    check_case_leak1(case)
    same = make_case(leak_pct=1.0, leak_start_min=600, seed=1)
    assert case.equals(same), "same seed must give identical data"
    print(f"Saved {DATA_DIR / 'case_leak1.csv'} ({len(case)} rows)")

    # Pump start at 06:00, no leak
    pump = make_case(q_m3s=0.10, events=[("pump_start", 360, 10, 0.10, 0.20)], seed=2)
    pump.to_csv(DATA_DIR / "case_pumpstart.csv")
    check_case_pumpstart(pump)
    print(f"Saved {DATA_DIR / 'case_pumpstart.csv'} ({len(pump)} rows)")
