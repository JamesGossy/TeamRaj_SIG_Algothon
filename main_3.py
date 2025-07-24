#!/usr/bin/env python
"""Faster index-momentum strategy (tuned on 1000-day file)."""
import numpy as np

# ===== tuned hyper-parameters =====
THRESH        = 0.002
DOLLAR_CAP    = 10_000        # exchange limit

# Strategy 1 parameters (more conservative)
LOOKBACK_1      = 10
VOL_WINDOW_1    = 10
TARGET_DOLLAR_1 = 1500

# Strategy 2 parameters (more aggressive)
LOOKBACK_2      = 5
VOL_WINDOW_2    = 5
TARGET_DOLLAR_2 = 500

def getMyPosition(price_history: np.ndarray) -> list[int]:
    """Return desired integer position for each of the 50 instruments."""
    prices = np.asarray(price_history, dtype=float)
    if prices.shape[0] != 50:
        prices = prices.T                              # accept either orientation
    n_inst, n_days = prices.shape

    if n_days <= max(LOOKBACK_1, VOL_WINDOW_1, LOOKBACK_2, VOL_WINDOW_2):
        return [0] * n_inst

    # ── 1) Market regime filter (index momentum) ─────────────────────────
    idx = prices.mean(axis=0)
    mom_short = idx[-1] / idx[-LOOKBACK_2 - 1] - 1.0
    direction = 1 if mom_short > 0 else -1
    p_today   = prices[:, -1]
    abs_mom = abs(mom_short)

    # do nothing
    if abs_mom < THRESH:
        return [0] * n_inst

    # aggressive strategy (2)
    if abs_mom >= 2 * THRESH:
        print("AGGRESSIVE")

        # ── 2) Realised volatility ───────────────────────────────────────────
        window = prices[:, -VOL_WINDOW_2 - 1 : -1]
        rets   = window[:, 1:] / window[:, :-1] - 1.0
        vol    = np.std(rets, axis=1, ddof=0) + 1e-8       # avoid /0

        # ── 3) Vol-scaled sizing ─────────────────────────────────────────────
        shares = np.floor(TARGET_DOLLAR_2 / (p_today * vol)).astype(int)

    # conservative strategy (1)
    else: 
        print("CONSERVATIVE")

        # ── 2) Realised volatility ───────────────────────────────────────────
        window = prices[:, -VOL_WINDOW_1 - 1 : -1]
        rets   = window[:, 1:] / window[:, :-1] - 1.0
        vol    = np.std(rets, axis=1, ddof=0) + 1e-8       # avoid /0

        # ── 3) Vol-scaled sizing ─────────────────────────────────────────────
        shares = np.floor(TARGET_DOLLAR_1 / (p_today * vol)).astype(int)

    shares[shares < 1] = 1                             # min 1 share

    # ── 4) Clip by \$10 k rule ───────────────────────────────────────────
    cap = np.floor(DOLLAR_CAP / p_today).astype(int)
    shares = np.clip(shares, 0, cap)

    return (direction * shares).tolist()
