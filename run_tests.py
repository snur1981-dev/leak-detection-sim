"""Test runs and figures for the report. Synthetic data only.

Part 5 (v0): the basic version - one leak, one 1 h window, line pack correction on and off.
Every number in the report must come from a file this script writes.
Run:  python run_tests.py
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # write image files without needing a screen
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

import cpm
from generator import TAGS, make_case

ROOT = Path(__file__).parent
RESULTS = ROOT / "results"
FIGS = ROOT / "report" / "figures"

THRESHOLD_M3 = 3.0  # placeholder until Part 6
PUMP_T = pd.Timestamp("2026-10-01 06:00")
LEAK_T = pd.Timestamp("2026-10-01 10:00")


def part5_basic():
    """Pump start at 06:00 and a 1% leak at 10:00 in one day. Saves fig0 and results/basic.csv."""
    df = make_case(q_m3s=0.10, events=[("pump_start", 360, 10, 0.10, 0.20)],
                   leak_pct=1.0, leak_start_min=600, seed=3)

    imb_line = cpm.balance(df, 60, compensate=False)
    imb_comp = cpm.balance(df, 60, compensate=True)
    alarm_line = cpm.alarms(imb_line, THRESHOLD_M3)
    alarm_comp = cpm.alarms(imb_comp, THRESHOLD_M3)
    p_avg = (df[TAGS["p_in"]] + 2 * df[TAGS["p_mid"]] + df[TAGS["p_out"]]) / 4

    # --- Figure: three panels sharing one time axis ---
    fig, ax = plt.subplots(3, 1, sharex=True, figsize=(8, 6.5))

    ax[0].plot(df.index, df[TAGS["q_in"]] * 3600, color="tab:blue", label="Inlet PS1_FT101")
    ax[0].plot(df.index, df[TAGS["q_out"]] * 3600, color="tab:orange", label="Outlet TRM_FT201")
    ax[0].set_ylabel("Flow (m³/h)")
    ax[0].legend(loc="lower right")

    ax[1].plot(df.index, p_avg, color="tab:blue")
    ax[1].set_ylabel("Avg pressure (MPa)")

    ax[2].plot(df.index, imb_line, color="tab:orange", label="Line balance (no line pack correction)")
    ax[2].plot(df.index, imb_comp, color="tab:blue", label="Compensated balance")
    ax[2].axhline(THRESHOLD_M3, ls="--", color="grey", label="Threshold 3.0 m³ (placeholder)")
    for alarm, imb, colour in ((alarm_line, imb_line, "tab:orange"), (alarm_comp, imb_comp, "tab:blue")):
        t = cpm.first_alarm(alarm)
        if t is not None:
            ax[2].plot(t, imb.loc[t], "v", ms=9, color=colour)  # marker at the first alarm
    ax[2].set_ylabel("1 h imbalance (m³)")
    ax[2].set_xlabel("Time of day")
    ax[2].legend(loc="upper right", fontsize=8)
    ax[2].xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))

    for a in ax:
        a.axvline(PUMP_T, ls=":", color="grey")
        a.axvline(LEAK_T, ls=":", color="grey")
        a.grid(alpha=0.3)
    ax[0].text(PUMP_T, 520, " pump start", color="grey")
    ax[0].text(LEAK_T, 520, " 1% leak starts", color="grey")

    fig.suptitle("Line pack correction removes the pump-start false alarm (synthetic data)")
    fig.tight_layout()
    fig.savefig(FIGS / "fig0_basic.png", dpi=150)
    plt.close(fig)

    # --- Numbers for the report, saved so every figure in the text is traceable ---
    false_line = alarm_line[alarm_line].index < LEAK_T
    res = {
        "line_balance_max_m3_before_leak": round(float(imb_line.loc[:LEAK_T].max()), 2),
        "compensated_max_m3_before_leak": round(float(imb_comp.loc[:LEAK_T].max()), 2),
        "line_balance_first_alarm": str(cpm.first_alarm(alarm_line)),
        "line_balance_false_alarm_before_leak": bool(false_line.any()),
        "compensated_first_alarm": str(cpm.first_alarm(alarm_comp)),
    }
    pd.Series(res).to_csv(RESULTS / "basic.csv", header=["value"])
    return res


if __name__ == "__main__":
    RESULTS.mkdir(exist_ok=True)
    FIGS.mkdir(parents=True, exist_ok=True)
    print("Part 5: basic version (synthetic data)")
    for key, value in part5_basic().items():
        print(f"  {key:40s} {value}")
    print(f"Saved {FIGS / 'fig0_basic.png'} and {RESULTS / 'basic.csv'}")