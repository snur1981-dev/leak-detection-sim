"""Compensated volume balance (CPM).

Build order:
  Oct 25  basic version: one window (1 h), flow imbalance, line pack correction on/off
  Oct 26  basic version working end to end on one leak case (milestone)
  Oct 27  5 min / 1 h / 24 h windows, uncertainty-based thresholds, persistence, pump-start inhibit
"""
