
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
Enhanced adaptive index trend follower for the Algothon.

Key features vs. simple EMA strategy:
- Regime-aware dynamic threshold: the trade trigger scales with recent index volatility.
- Regime-aware sizing: position size scales up when the index trend is strong relative to its threshold,
  and scales down in choppy regimes.
- Volatility-based per-instrument risk parity sizing and $10k/stock hard cap.
- Lot rounding (5-share lots) to reduce turnover and commissions.
Only uses NumPy and runs in O(T * nInst) time per evaluation.
'''
import numpy as np

# ---- Tuned parameters (robust across our 1000-day set and forward split) ----
SPAN_FAST = 7           # EMA span used in normal vols
SPAN_SLOW = 10          # EMA span used when index vol is elevated
VOL_WINDOW = 5          # per-instrument vol window for sizing
IDX_VOL_WINDOW = 20     # index vol lookback window (days)
BASE_TARGET_DOLLAR = 1500.0  # base dollar risk per instrument
THRESHOLD_VOL_MULT = 0.5     # trade trigger = THRESHOLD_VOL_MULT * index volatility
SIZE_SCALE_K = 0.5           # exposure scaling with signal/threshold
LOT_SIZE = 5                 # round shares to multiples of this to reduce churn

CAP_DOLLARS = 10000.0        # $10k per stock hard cap at trade time

def _clip_to_dollar_cap(shares, prices_today, cap_dollars=CAP_DOLLARS):
    max_shares = np.floor(cap_dollars / np.maximum(prices_today, 1e-12)).astype(int)
    return np.clip(shares, -max_shares, max_shares).astype(int)

def getMyPosition(price_history: np.ndarray) -> list[int]:
    '''
    Compute desired integer positions (shares) for each of the 50 instruments.
    The evaluator will trade the difference from yesterday at today's close.

    Input
    -----
    price_history : np.ndarray of shape (nInst x nDays) or (nDays x nInst)

    Output
    ------
    List[int] of length 50: desired total shares per instrument.
    '''
    P = np.asarray(price_history, dtype=float)
    if P.ndim != 2:
        raise ValueError("price_history must be a 2D array")
    if P.shape[0] != 50:
        P = P.T
    n_inst, n_days = P.shape
    min_hist = max(SPAN_SLOW, VOL_WINDOW, IDX_VOL_WINDOW) + 2
    if n_days < min_hist:
        return [0]*n_inst

    prices_today = P[:, -1]

    # Geometric-mean index and its EMA
    gidx = np.exp(np.log(P).mean(axis=0))
    idx_ret = gidx[1:] / gidx[:-1] - 1.0
    idx_vol = np.std(idx_ret[-IDX_VOL_WINDOW:], ddof=0) + 1e-12

    span = SPAN_SLOW if idx_vol > 0.01 else SPAN_FAST
    alpha = 2.0 / (span + 1.0)
    ema = np.empty_like(gidx)
    ema[0] = gidx[0]
    for t in range(1, n_days):
        ema[t] = alpha * gidx[t] + (1.0 - alpha) * ema[t-1]

    dev = gidx[-1] / max(ema[-1], 1e-12) - 1.0

    # Dynamic threshold and early exit in flat regime
    threshold = THRESHOLD_VOL_MULT * idx_vol
    if abs(dev) < threshold:
        return [0]*n_inst

    # Direction of exposure: long if index above EMA, short if below
    direction = 1 if dev > 0 else -1

    # Per-instrument volatility for sizing
    window = P[:, -VOL_WINDOW-1:-1]
    r = window[:, 1:] / window[:, :-1] - 1.0
    ivol = np.std(r, axis=1, ddof=0) + 1e-8

    # Regime-aware size scaling (bounded)
    scale = 1.0 + SIZE_SCALE_K * (abs(dev) / max(threshold, 1e-12) - 1.0)
    scale = float(np.clip(scale, 0.5, 2.5))

    # Dollar risk per instrument (risk-parity like)
    dollars = BASE_TARGET_DOLLAR * scale / ivol

    # Convert to shares and round to lots to reduce churn & cost
    raw_shares = dollars / np.maximum(prices_today, 1e-12)
    shares = (np.floor(np.abs(raw_shares) / LOT_SIZE).astype(int) * LOT_SIZE) * np.sign(raw_shares)

    # Enforce $10k cap at trade time
    shares = _clip_to_dollar_cap(shares, prices_today, cap_dollars=CAP_DOLLARS)

    # Ensure strictly positive size when non-zero
    shares[shares < 1] = 1

    return (direction * shares).astype(int).tolist()
