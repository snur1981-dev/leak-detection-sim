"""Test matrix and figures.

  Sensitivity (Oct 28): leaks of 0.5, 1, 2, 5% of flow; detection time per window -> figure 1
  Reliability (Oct 29): 7 days, no leak, 6 pump starts, 2 valve moves; false alarms with/without
                        line pack correction and inhibit -> figure 2
  Robustness  (Oct 30): drift, frozen value, dropout, and clock skew / deadband cases -> figure 3
Only results actually produced by these runs go into the report.
"""
