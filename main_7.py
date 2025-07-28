
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Momentum-primary index strategy with ER-based sizing only.

Intent:
- Preserve the strong performance of your simple index-momentum rule on the last 250 days.
- Avoid overfitting by keeping the rule simple and selecting only execution knobs on pre-target data.
- Add two robust controls from our prior work:
  (1) ER (Efficiency Ratio) used ONLY to de-lever size in chop (no blocking of trades).
  (2) Small no-trade band + 20-share lots to cut fee drag without hurting the momentum edge.

Mechanics:
- Market index = geometric mean of the 50 instruments.
- Momentum signal: mom = idx[t]/idx[t-LB] - 1; act only if |mom| >= MOM_THRESH.
- Direction = sign(mom). All instruments trade the same direction.
- Sizing = inverse-volatility per instrument, scaled by ER-based size multiplier.
- $10k per-stock cap is enforced at trade time.

Parameters chosen with no-peek selection on days <= 1250:
  MOM_LOOKBACK=5, MOM_THRESH=0.003, LOT_SIZE=20, NO_TRADE_MIN_DOLLARS=$500,
  ER_WINDOW=25, ER_LOW=0.20, ER_HIGH=0.60, CHOP_SIZE_MULT=0.30, BASE_TARGET=$1000.
"""
import numpy as np

# ---- Signal parameters ----
MOM_LOOKBACK = 5
MOM_THRESH   = 0.003

# ---- Sizing & execution ----
VOL_WINDOW = 5
LOT_SIZE = 20
NO_TRADE_MIN_DOLLARS = 500.0
BASE_TARGET = 1000.0      # base dollar risk before ER scaling
CAP_DOLLARS = 10000.0

# ---- ER sizing (no blocking) ----
ER_WINDOW = 25
ER_LOW  = 0.20
ER_HIGH = 0.60
CHOP_SIZE_MULT = 0.30     # size multiplier in chop (blended by ER)

def _clip_to_dollar_cap(shares, prices_today, cap_dollars=CAP_DOLLARS):
    max_shares = np.floor(cap_dollars / np.maximum(prices_today, 1e-12)).astype(int)
    return np.clip(shares, -max_shares, max_shares).astype(int)

def getMyPosition(price_history):
    P = np.asarray(price_history, dtype=float)
    if P.ndim != 2:
        raise ValueError("price_history must be a 2D array")
    if P.shape[0] != 50:
        P = P.T
    n_inst, n_days = P.shape
    min_hist = max(VOL_WINDOW, MOM_LOOKBACK, ER_WINDOW) + 2
    if n_days < min_hist:
        return [0]*n_inst

    prices_today = P[:, -1]
    prices_prev  = P[:, -2]

    # Index
    g = np.exp(np.log(P).mean(axis=0))

    # Momentum signal
    mom = g[-1] / max(g[-MOM_LOOKBACK-1], 1e-12) - 1.0
    if abs(mom) < MOM_THRESH:
        return [0]*n_inst
    direction = 1 if mom > 0 else -1

    # ER weight for sizing ONLY
    delta = abs(g[-1] - g[-ER_WINDOW])
    noise = np.sum(np.abs(np.diff(g[-ER_WINDOW:])))
    er = delta / (noise + 1e-12)
    if er <= ER_LOW:
        w = 0.0
    elif er >= ER_HIGH:
        w = 1.0
    else:
        w = (er - ER_LOW) / (ER_HIGH - ER_LOW)
    base_eff = BASE_TARGET * (CHOP_SIZE_MULT ** (1.0 - w))

    # Per-instrument volatility
    win = P[:, -VOL_WINDOW-1:-1]
    ivol = np.std(win[:, 1:] / win[:, :-1] - 1.0, axis=1, ddof=0) + 1e-8

    # Target today
    raw = (base_eff / ivol) / np.maximum(prices_today, 1e-12)
    tgt_today = (np.floor(np.abs(raw) / max(1, LOT_SIZE)).astype(int) * max(1, LOT_SIZE)) * np.sign(raw)
    tgt_today = _clip_to_dollar_cap(tgt_today, prices_today)
    tgt_today[tgt_today < 1] = 1
    tgt_today = (direction * tgt_today).astype(int)

    # Approximate yesterday's target for a small no-trade band
    if n_days > MOM_LOOKBACK + 2:
        mom_prev = g[-2] / max(g[-MOM_LOOKBACK-2], 1e-12) - 1.0
        if abs(mom_prev) < MOM_THRESH:
            tgt_prev = np.zeros(n_inst, dtype=int)
        else:
            dir_prev = 1 if mom_prev > 0 else -1
            winp = P[:, -VOL_WINDOW-2:-2]
            ivolp = np.std(winp[:, 1:] / winp[:, :-1] - 1.0, axis=1, ddof=0) + 1e-8
            # ER prev for size
            if len(g) > ER_WINDOW + 1:
                delta_p = abs(g[-2] - g[-ER_WINDOW-1])
                noise_p = np.sum(np.abs(np.diff(g[-ER_WINDOW-1:-1])))
                er_p = delta_p / (noise_p + 1e-12)
                if er_p <= ER_LOW:
                    wp = 0.0
                elif er_p >= ER_HIGH:
                    wp = 1.0
                else:
                    wp = (er_p - ER_LOW) / (ER_HIGH - ER_LOW)
            else:
                wp = w
            base_eff_prev = BASE_TARGET * (CHOP_SIZE_MULT ** (1.0 - wp))

            rawp = (base_eff_prev / ivolp) / np.maximum(prices_prev, 1e-12)
            tgt_prev = (np.floor(np.abs(rawp) / max(1, LOT_SIZE)).astype(int) * max(1, LOT_SIZE)) * np.sign(rawp)
            tgt_prev = _clip_to_dollar_cap(tgt_prev, prices_prev)
            tgt_prev[tgt_prev < 1] = 1
            tgt_prev = (dir_prev * tgt_prev).astype(int)
    else:
        tgt_prev = np.zeros(n_inst, dtype=int)

    # No-trade band to avoid tiny rebalances
    delta_shares = tgt_today - tgt_prev
    small = (np.abs(delta_shares) * prices_today) < NO_TRADE_MIN_DOLLARS
    y_final = tgt_today.copy()
    y_final[small] = tgt_prev[small]

    return y_final.astype(int).tolist()
