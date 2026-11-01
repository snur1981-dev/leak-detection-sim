"""Warm-up 1: numpy for the generator. Run it, read the output, then do the TODOs.

Everything here is a small version of something generator.py will do.
"""
import numpy as np

rng = np.random.default_rng(42)  # seeded: same numbers every run

# One day of 1-minute readings
n = 1440
minute = np.arange(n)                      # 0, 1, 2, ... 1439

# True flow is constant 0.20 m3/s. A 1% leak starts at minute 600.
q_true_in = np.full(n, 0.20)
leak = np.where(minute >= 600, 0.002, 0.0)  # m3/s, 1% of 0.20
q_true_out = q_true_in - leak

# Meters: +0.2% bias on the inlet, random noise on both (std 0.1% of flow)
q_in = q_true_in * 1.002 + rng.normal(0, 0.0002, n)
q_out = q_true_out + rng.normal(0, 0.0002, n)

# Volume lost each minute (m3) and the running total
imb_m3 = (q_in - q_out) * 60
cum = np.cumsum(imb_m3)

print(f"Mean inlet flow:            {q_in.mean():.5f} m3/s")
print(f"Imbalance before leak:      {imb_m3[:600].mean():.4f} m3/min  (this is the bias)")
print(f"Imbalance after leak:       {imb_m3[600:].mean():.4f} m3/min")
print(f"Cumulative imbalance, day:  {cum[-1]:.1f} m3")
print(f"Bias alone over a day:      {0.20 * 0.002 * 86400:.1f} m3")
print(f"Leak alone over 840 min:    {0.002 * 60 * 840:.1f} m3")

# Boolean mask: which minutes had imbalance above 0.15 m3?
mask = imb_m3 > 0.15
print(f"Minutes above 0.15 m3:      {mask.sum()} of {n}")

# TODO 1: Set the bias to 0 (change 1.002 to 1.0). Re-run. What happens to the
#         "before leak" imbalance? Why?
# TODO 2: Make the noise 10x bigger. Does the cumulative total change much?
#         Does the minute-by-minute mask count change much? Explain the difference
#         (hint: noise averages out in a sum, bias does not).
# TODO 3: Change the leak to 0.5% of flow. With the bias at 0.2%, could you
#         tell bias and leak apart from the cumulative total alone?
