#!/usr/bin/env python
"""Faster index-momentum strategy (tuned on 1000-day file)."""
import numpy as np

# ===== tuned hyper-parameters =====
LOOKBACK      = 5
VOL_WINDOW    = 5
THRESH        = 0.002
TARGET_DOLLAR = 500
DOLLAR_CAP    = 10_000        # exchange limit

# breadth thresholds
BREADTH_LONG = 0.51 # % of stocks that must be rising to go long
BREADTH_SHORT = 0.49 # % of stocks that must be falling to go short

def getMyPosition(price_history: np.ndarray) -> list[int]:
    """Return desired integer position for each of the 50 instruments."""
    prices = np.asarray(price_history, dtype=float)
    if prices.shape[0] != 50:
        prices = prices.T                              # accept either orientation
    n_inst, n_days = prices.shape

    if n_days <= max(LOOKBACK, VOL_WINDOW):
        return [0] * n_inst

    # ── 1) Market regime filter (index momentum) ─────────────────────────
    idx = prices.mean(axis=0)
    mom = idx[-1] / idx[-LOOKBACK - 1] - 1.0
    if abs(mom) < THRESH:
        return [0] * n_inst
    direction = 1 if mom > 0 else -1
    p_today   = prices[:, -1]

    # ── 2) Breadth filter ───────────────────────────────────────────
    indiv_mom = prices[:, -1] / prices[:, -LOOKBACK - 1] - 1.0
    breadth = np.mean(indiv_mom > 0)

    if mom > 0 and breadth > BREADTH_LONG:
        direction = 1
    elif mom < 0 and breadth < BREADTH_SHORT:
        direction = -1
    else:
        return [0] * n_inst  # skip if momentum and breadth disagree

    # ── 2) Realised volatility ───────────────────────────────────────────
    window = prices[:, -VOL_WINDOW - 1 : -1]
    rets   = window[:, 1:] / window[:, :-1] - 1.0
    vol    = np.std(rets, axis=1, ddof=0) + 1e-8       # avoid /0

    # ── 3) Vol-scaled sizing ─────────────────────────────────────────────
    shares = np.floor(TARGET_DOLLAR / (p_today * vol)).astype(int)
    shares[shares < 1] = 1                             # min 1 share

    # ── 4) Clip by \$10 k rule ───────────────────────────────────────────
    cap = np.floor(DOLLAR_CAP / p_today).astype(int)
    shares = np.clip(shares, 0, cap)

    return (direction * shares).tolist()
