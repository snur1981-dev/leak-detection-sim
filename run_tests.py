"""Test matrix: runs every case, writes results/*.csv, report/figures/*.png and results/summary.md.

Synthetic data only. Every number in the report must come from a file this script writes.
Run:  python run_tests.py
"""
from pathlib import Path

import matplotlib
import matplotlib.dates
import matplotlib.ticker

matplotlib.use("Agg")  # write files without needing a screen
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import cpm
import quality
from generator import OUTLET_TAGS, TAGS, add_drift, add_dropout, add_frozen, apply_deadband, apply_skew, make_case

ROOT = Path(__file__).parent
RESULTS = ROOT / "results"
FIGS = ROOT / "report" / "figures"
DEFAULT_BIAS = (0.05, -0.03)  # inlet reads 0.05% high, outlet 0.03% low: meters after proving (assumed)
WINDOWS = cpm.SETTINGS["windows_min"]
WIN_NAME = {5: "5 min", 60: "1 h", 1440: "24 h"}

# Colours: categorical slots 1-3 of the reference palette; recessive greys for grid and text
C1, C2, C3 = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
plt.rcParams.update({
    "font.size": 9, "axes.edgecolor": INK2, "axes.labelcolor": INK, "xtick.color": INK2,
    "ytick.color": INK2, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
    "axes.spines.top": False, "axes.spines.right": False, "lines.linewidth": 1.4,
    "legend.frameon": False,
})


# --- Event schedules ---

def reliability_events(days=7):
    """Each of the first 6 days: pump stop 02:00, pump start 05:00. Days 3 and 5: valve cut 14:00-16:00."""
    ev = []
    for d in range(days):
        base = d * 1440
        if d < 6:
            ev += [("pump_stop", base + 120, 10, 0.20, 0.10), ("pump_start", base + 300, 10, 0.10, 0.20)]
        if d in (3, 5):
            ev += [("valve", base + 840, 5, 0.20, 0.15), ("valve", base + 960, 5, 0.15, 0.20)]
    return sorted(ev, key=lambda e: e[1])


def setpoint_events(hours=48):
    """Eight setpoint changes of 0.02 m3/s over 5 min, every 6 h from 03:00. No status change."""
    ev, q = [], 0.20
    for k in range(hours // 6):
        q_to = 0.18 if q == 0.20 else 0.20
        ev.append(("setpoint", 180 + k * 360, 5, q, q_to))
        q = q_to
    return ev


def with_thresholds(thresholds):
    s = dict(cpm.SETTINGS)
    s["thresholds_m3"] = thresholds
    return s


def detection(out, w, leak_start, horizon_min=1440):
    """Minutes from leak start to the first alarm in window w (None if none within the horizon)."""
    a = out[f"alarm_{w}"].to_numpy()
    hits = np.flatnonzero(a[leak_start:leak_start + horizon_min])
    return int(hits[0]) if hits.size else None


def md_table(df):
    """Plain markdown table (no extra packages needed)."""
    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for row in df.itertuples(index=False):
        lines.append("| " + " | ".join("" if pd.isna(v) else (f"{v:.2f}" if isinstance(v, float) else str(v))
                                       for v in row) + " |")
    return "\n".join(lines)


# --- Part 5: the basic version (one leak, one window, line pack on and off) ---

def part5_basic():
    df = make_case(q_m3s=0.10, events=[("pump_start", 360, 10, 0.10, 0.20)],
                   leak_pct=1.0, leak_start_min=600, seed=3)
    imb_line = cpm.balance(df, 60, compensate=False)
    imb_comp = cpm.balance(df, 60, compensate=True)
    a_line, a_comp = cpm.alarms(imb_line, 3.0), cpm.alarms(imb_comp, 3.0)
    p_avg = (df[TAGS["p_in"]] + 2 * df[TAGS["p_mid"]] + df[TAGS["p_out"]]) / 4

    fig, ax = plt.subplots(3, 1, sharex=True, figsize=(8, 6.2))
    ax[0].plot(df.index, df[TAGS["q_in"]] * 3600, color=C1, label="Inlet PS1_FT101")
    ax[0].plot(df.index, df[TAGS["q_out"]] * 3600, color=C2, label="Outlet TRM_FT201")
    ax[0].set_ylabel("Flow (m³/h)")
    ax[0].legend(loc="lower right", ncol=2)
    ax[1].plot(df.index, p_avg, color=C1)
    ax[1].set_ylabel("Average pressure (MPa)")
    ax[2].plot(df.index, imb_line, color=C2, label="Line balance (no line pack correction)")
    ax[2].plot(df.index, imb_comp, color=C1, label="Compensated balance")
    ax[2].axhline(3.0, ls="--", color=INK2, lw=1, label="Threshold 3.0 m³ (placeholder)")
    for alarm, col in ((a_line, C2), (a_comp, C1)):
        t = cpm.first_alarm(alarm)
        if t is not None:
            ax[2].plot(t, imb_line.loc[t] if col == C2 else imb_comp.loc[t], "v", ms=8, color=col)
    for a in ax:
        a.axvline(pd.Timestamp("2026-10-01 06:00"), ls=":", color=INK2, lw=1)
        a.axvline(pd.Timestamp("2026-10-01 10:00"), ls=":", color=INK2, lw=1)
    ax[0].text(pd.Timestamp("2026-10-01 05:50"), 500, "pump start 06:00", color=INK2, ha="right")
    ax[0].text(pd.Timestamp("2026-10-01 10:10"), 500, "1% leak from 10:00", color=INK2)
    ax[2].xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%H:%M"))
    ax[2].set_xlabel("Time of day")
    ax[2].set_ylabel("1 h imbalance (m³)")
    ax[2].legend(loc="upper right")
    fig.suptitle("Line pack correction removes the pump-start false alarm (synthetic data)", x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(FIGS / "fig0_basic.png", dpi=160)
    plt.close(fig)

    leak_t = pd.Timestamp("2026-10-01 10:00")
    alarms_line = a_line[a_line].index
    res = {
        "line_balance_max_m3_before_leak": float(imb_line.loc[:leak_t].max()),
        "compensated_max_m3_before_leak": float(imb_comp.loc[:leak_t].max()),
        "line_balance_first_alarm": str(cpm.first_alarm(a_line)),
        "line_balance_false_alarm_before_leak": bool((alarms_line < leak_t).any()),
        "compensated_first_alarm": str(cpm.first_alarm(a_comp)),
    }
    pd.Series(res).to_csv(RESULTS / "basic.csv", header=["value"])
    return res


# --- Part 6: thresholds from a no-leak tuning run ---

def part6_tune():
    # 7 days: a 24 h window needs several days of data for its sigma to mean anything
    df = make_case(duration_h=24 * 7, bias_pct=DEFAULT_BIAS, seed=100)
    thresholds, sigmas = cpm.tune(df)
    tab = pd.DataFrame({"window": [WIN_NAME[w] for w in WINDOWS],
                        "sigma_m3": [sigmas[w] for w in WINDOWS],
                        "threshold_m3": [thresholds[w] for w in WINDOWS],
                        "min_detectable_leak_pct_of_flow": [thresholds[w] / (60 * w) / 0.20 * 100 for w in WINDOWS]})
    tab.to_csv(RESULTS / "thresholds.csv", index=False)
    return thresholds, tab


# --- Part 7: sensitivity (and accuracy of the leak rate estimate) ---

def part7_sensitivity(settings):
    rows = []
    start = 34 * 60  # day 2, 10:00, so the 24 h window is full
    for pct in (0.5, 1.0, 2.0, 5.0):
        for seed in range(11, 16):
            df = make_case(duration_h=72, leak_pct=pct, leak_start_min=start, bias_pct=DEFAULT_BIAS, seed=seed)
            out = cpm.run_cpm(df, settings)
            est = out["imb_60"].iloc[start + 120] / 3600
            for w in WINDOWS:
                rows.append({"leak_pct": pct, "seed": seed, "window": WIN_NAME[w],
                             "detect_min": detection(out, w, start),
                             "false_alarms_before_leak": cpm.alarm_events(out[f"alarm_{w}"].iloc[:start]),
                             "est_leak_m3s_1h": est, "true_leak_m3s": 0.20 * pct / 100})
    res = pd.DataFrame(rows)
    res.to_csv(RESULTS / "sensitivity.csv", index=False)

    summ = (res.groupby(["leak_pct", "window"], sort=False)["detect_min"]
            .agg(detected=lambda s: f"{s.notna().sum()}/5", median="median", low="min", high="max")
            .reset_index())
    acc = (res[res.window == "1 h"].groupby("leak_pct")
           .apply(lambda g: pd.Series({"est_mean_m3h": g.est_leak_m3s_1h.mean() * 3600,
                                       "true_m3h": g.true_leak_m3s.iloc[0] * 3600}), include_groups=False)
           .reset_index())
    acc["error_pct_of_true"] = (acc.est_mean_m3h / acc.true_m3h - 1) * 100

    fig, ax = plt.subplots(figsize=(7, 4))
    for w, col in zip(WINDOWS, (C1, C2, C3)):
        s = summ[(summ.window == WIN_NAME[w]) & (summ.detected == "5/5")]  # plot only reliable detection
        if s.empty:
            continue
        ax.errorbar(s.leak_pct, s["median"], yerr=[s["median"] - s.low, s.high - s["median"]],
                    color=col, marker="o", ms=6, capsize=3, label=f"{WIN_NAME[w]} window")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xticks([0.5, 1, 2, 5], ["0.5%", "1%", "2%", "5%"])
    ax.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    ax.text(0.01, -0.2, "Points shown only where all 5 seeds alarmed within 24 h. Bars: fastest to slowest seed.",
            transform=ax.transAxes, color=INK2, fontsize=8)
    ax.set_xlabel("Leak size (% of 0.20 m³/s)")
    ax.set_ylabel("Time to alarm (minutes, median of 5 seeds)")
    ax.legend(loc="upper right")
    ax.set_title("Bigger leaks are caught faster; each window has a floor (synthetic data)", loc="left")
    fig.tight_layout()
    fig.savefig(FIGS / "fig1_sensitivity.png", dpi=160)
    plt.close(fig)
    return summ, acc


# --- Part 8: reliability (false alarms with no leak, normal operations) ---

CONFIGS = {"Line balance": dict(compensate=False, use_inhibit=False),
           "Compensated": dict(compensate=True, use_inhibit=False),
           "Compensated + inhibit": dict(compensate=True, use_inhibit=True)}


def part8_reliability(settings):
    rows = []
    for seed in range(21, 26):
        df = make_case(duration_h=24 * 7, events=reliability_events(), bias_pct=DEFAULT_BIAS, seed=seed)
        for name, kw in CONFIGS.items():
            out = cpm.run_cpm(df, settings, **kw)
            for w in WINDOWS:
                ev = cpm.alarm_events(out[f"alarm_{w}"])
                rows.append({"config": name, "seed": seed, "window": WIN_NAME[w],
                             "false_alarm_events": ev, "per_day": ev / 7})
    res = pd.DataFrame(rows)
    res.to_csv(RESULTS / "reliability.csv", index=False)
    summ = res.groupby(["config", "window"], sort=False)["per_day"].mean().unstack()[[WIN_NAME[w] for w in WINDOWS]]

    fig, ax = plt.subplots(figsize=(7, 3.8))
    x = np.arange(len(CONFIGS))
    width = 0.26
    for i, (w, col) in enumerate(zip(WINDOWS, (C1, C2, C3))):
        vals = summ[WIN_NAME[w]].to_numpy()
        bars = ax.bar(x + (i - 1) * (width + 0.02), vals, width, color=col, label=f"{WIN_NAME[w]} window")
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, v, f"{v:.1f}", ha="center", va="bottom", color=INK, fontsize=8)
    ax.set_xticks(x, list(CONFIGS))
    ax.set_ylabel("False alarms per day (mean of 5 seeds)")
    ax.legend(loc="upper right")
    ax.set_title("7 days, 6 pump stop/starts, 2 valve moves, no leak (synthetic data)", loc="left")
    fig.tight_layout()
    fig.savefig(FIGS / "fig2_reliability.png", dpi=160)
    plt.close(fig)
    return summ


# --- Part 9: robustness (clock skew, deadband, drift, frozen value, dropout) ---

def part9_robustness(settings):
    # 9a. Clock skew on the outlet RTU, setpoint changes that do NOT trigger the inhibit
    skew_rows = []
    for seed in (31, 32, 33):
        base = make_case(duration_h=48, events=setpoint_events(), bias_pct=DEFAULT_BIAS, seed=seed)
        ref = cpm.run_cpm(base, settings)
        for s in (0, 2, 5, 10, 30, 60):
            out = cpm.run_cpm(apply_skew(base, s), settings)
            for w in WINDOWS:
                skew_rows.append({"skew_s": s, "seed": seed, "window": WIN_NAME[w],
                                  "false_alarm_events": cpm.alarm_events(out[f"alarm_{w}"]),
                                  "max_added_imbalance_m3": float((out[f"imb_{w}"] - ref[f"imb_{w}"]).abs().max())})
    skew = pd.DataFrame(skew_rows)
    skew.to_csv(RESULTS / "robustness_skew.csv", index=False)
    skew_summ = skew.groupby(["skew_s", "window"], sort=False).agg(
        false_alarms=("false_alarm_events", "sum"), max_added_m3=("max_added_imbalance_m3", "max")).reset_index()

    # 9b. Reporting deadband on both flow meters, reliability case
    db_rows = []
    for seed in (21, 22, 23):
        base = make_case(duration_h=24 * 7, events=reliability_events(), bias_pct=DEFAULT_BIAS, seed=seed)
        for db_m3h in (0.0, 0.5, 2.0):
            df = base.copy()
            if db_m3h:
                for tag in (TAGS["q_in"], TAGS["q_out"]):
                    df[tag] = apply_deadband(df[tag], db_m3h / 3600)
            out = cpm.run_cpm(df, settings)
            for w in WINDOWS:
                db_rows.append({"deadband_m3h": db_m3h, "seed": seed, "window": WIN_NAME[w],
                                "false_alarm_events": cpm.alarm_events(out[f"alarm_{w}"])})
    dband = pd.DataFrame(db_rows)
    dband.to_csv(RESULTS / "robustness_deadband.csv", index=False)
    db_summ = dband.groupby(["deadband_m3h", "window"], sort=False)["false_alarm_events"].sum().unstack()

    # 9c. Instrument and comms faults, with and without quality.py
    base = make_case(duration_h=24 * 7, events=reliability_events(), bias_pct=DEFAULT_BIAS, seed=21)
    leak_start = 2 * 1440 + 610
    leaky = make_case(duration_h=24 * 7, events=reliability_events(), bias_pct=DEFAULT_BIAS, seed=21,
                      leak_pct=2.0, leak_start_min=leak_start)
    faults = {
        "Outlet meter drifts -0.02%/day": add_drift(base, TAGS["q_out"], -0.02),
        "Outlet flow frozen 60 min at a pump start": add_frozen(base, TAGS["q_out"], 1440 + 300, 60),
        "Outlet RTU dropout 30 min, 2% leak starts 10 min in": add_dropout(leaky, OUTLET_TAGS, 2 * 1440 + 600, 30),
    }
    f_rows = []
    for name, raw in faults.items():
        flags = quality.check(raw)
        filled = raw.ffill()  # the historian holds the last value through a gap
        for mode, bad in (("without quality.py", None), ("with quality.py", flags["bad"])):
            out = cpm.run_cpm(filled, settings, bad=bad)
            row = {"fault": name, "mode": mode, "flagged_min": quality.summary(flags)["bad"] if bad is not None else 0}
            for w in WINDOWS:
                a = out[f"alarm_{w}"]
                if "leak" in name:  # a real leak: what matters is how long until the alarm
                    d = detection(out, w, leak_start)
                    row[f"{WIN_NAME[w]}"] = f"leak alarm after {d} min" if d is not None else "no alarm within 24 h"
                    row[f"{WIN_NAME[w]} suppressed (min)"] = int(out[f"degraded_{w}"].sum())
                else:  # no leak: every alarm is a false alarm
                    first = cpm.first_alarm(a)
                    row[f"{WIN_NAME[w]}"] = (f"{cpm.alarm_events(a)} false alarms, first on day {(first - out.index[0]).days + 1} at {first:%H:%M}"
                                             if first is not None else "no alarms")
            f_rows.append(row)
    fault = pd.DataFrame(f_rows)
    fault.to_csv(RESULTS / "robustness_faults.csv", index=False)

    # Figure 3: skew panel and deadband panel
    fig, ax = plt.subplots(1, 2, figsize=(9, 3.6))
    for w, col in zip(WINDOWS[:2], (C1, C2)):
        s = skew_summ[skew_summ.window == WIN_NAME[w]]
        ax[0].plot(s.skew_s, s.max_added_m3, marker="o", ms=6, color=col, label=f"{WIN_NAME[w]}: added imbalance")
        ax[0].axhline(settings["thresholds_m3"][w], ls="--", lw=1, color=col, label=f"{WIN_NAME[w]} threshold")
    ax[0].set_xlabel("Outlet clock skew (s)")
    ax[0].set_ylabel("Largest added imbalance (m³)")
    ax[0].set_title("Clock skew, 8 setpoint changes of 0.02 m³/s", loc="left")
    ax[0].legend(fontsize=7.5, loc="upper left")
    labels = [f"{d:g} m³/h" if d else "none" for d in db_summ.index]
    x = np.arange(len(labels))
    for i, (w, col) in enumerate(zip(WINDOWS, (C1, C2, C3))):
        vals = db_summ[WIN_NAME[w]].to_numpy()
        bars = ax[1].bar(x + (i - 1) * 0.28, vals, 0.26, color=col, label=f"{WIN_NAME[w]} window")
        for b, v in zip(bars, vals):
            ax[1].text(b.get_x() + b.get_width() / 2, v, f"{v:g}", ha="center", va="bottom", fontsize=8, color=INK)
    ax[1].set_xticks(x, labels)
    ax[1].set_xlabel("Flow meter reporting deadband")
    ax[1].set_ylabel("False alarms, 3 seeds x 7 days")
    ax[1].set_title("Deadband on both flow meters", loc="left")
    ax[1].legend(fontsize=7.5)
    fig.suptitle("Robustness (synthetic data)", x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(FIGS / "fig3_robustness.png", dpi=160)
    plt.close(fig)
    return skew_summ, db_summ, fault


# --- Run everything and write the summary ---

if __name__ == "__main__":
    RESULTS.mkdir(exist_ok=True)
    FIGS.mkdir(parents=True, exist_ok=True)

    print("Part 5: basic version ...")
    basic = part5_basic()
    print("Part 6: tuning thresholds ...")
    thresholds, thr_tab = part6_tune()
    settings = with_thresholds(thresholds)
    print("Part 7: sensitivity ...")
    sens, acc = part7_sensitivity(settings)
    print("Part 8: reliability ...")
    rel = part8_reliability(settings)
    print("Part 9: robustness ...")
    skew_summ, db_summ, fault = part9_robustness(settings)

    md = ["# Results summary (synthetic data; generated by run_tests.py)", "",
          "## Part 5: basic version (1 h window, 3.0 m3 placeholder threshold)", "",
          md_table(pd.DataFrame(list(basic.items()), columns=["result", "value"])), "",
          "## Part 6: thresholds from a 7-day no-leak tuning run", "", md_table(thr_tab), "",
          "## Part 7: sensitivity (minutes from leak start to alarm, 5 seeds)", "", md_table(sens), "",
          "Accuracy of the 1 h leak-rate estimate, 2 h after the leak starts:", "", md_table(acc), "",
          "## Part 8: reliability (false alarms per day, mean of 5 seeds x 7 days)", "",
          md_table(rel.reset_index()), "",
          "## Part 9a: clock skew (8 setpoint changes, 3 seeds x 48 h)", "", md_table(skew_summ), "",
          "## Part 9b: deadband (false alarm events, 3 seeds x 7 days)", "", md_table(db_summ.reset_index()), "",
          "## Part 9c: faults, with and without quality.py", "", md_table(fault), ""]
    (RESULTS / "summary.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))
    print(f"\nFigures in {FIGS}, tables in {RESULTS}")
