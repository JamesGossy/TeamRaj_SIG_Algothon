
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
Regime-aware EMA trend follower with Efficiency Ratio (ER) gating and cost-aware rebalancing.

Motivation:
- In trending regimes, keep the high-scoring index-EMA trend with inverse-vol sizing.
- In choppy regimes (low ER), widen the trigger and cut size to avoid whipsaws that hurt
  the last-250-day performance, while preserving strength on earlier windows.

Mechanics:
- Geometric-mean index (50 instruments) and EMA signal.
- Index volatility sets a dynamic trigger; ER (Kaufman's efficiency ratio) on the index
  determines a blend between "trend" and "chop" settings:
    * threshold_mult_eff = THRESHOLD_VOL_MULT * (CHOP_THR_MULT ** (1 - w))
    * base_dollar_eff    = BASE_TARGET_DOLLAR * (CHOP_SIZE_MULT ** (1 - w))
  where w∈[0,1] rises from 0 (chop) to 1 (trend) as ER moves from ER_LOW to ER_HIGH.
- Per-instrument inverse-vol risk-parity sizing.
- 20-share lot rounding plus a small no-trade band to reduce unnecessary rebalances.
- $10k-per-stock cap enforced at trade time.

Only NumPy. Stateless API; yesterday's target is approximated from the price history.
'''
import numpy as np

# ---- Core parameters ----
SPAN_FAST = 7
SPAN_SLOW = 10
VOL_WINDOW = 5
IDX_VOL_WINDOW = 20

BASE_TARGET_DOLLAR = 1500.0
THRESHOLD_VOL_MULT = 0.4    # lower base trigger; ER-gating will widen it in chop
SIZE_SCALE_K = 0.4
LOT_SIZE = 20
NO_TRADE_MIN_DOLLARS = 1000.0

# ---- ER (Efficiency Ratio) regime gating ----
ER_WINDOW = 25
ER_LOW  = 0.276064
ER_HIGH = 0.560355
CHOP_SIZE_MULT = 0.25       # size shrink in chop (blended by ER)
CHOP_THR_MULT  = 1.5        # threshold widening in chop (blended by ER)
CHOP_FLAT = False           # do not force flat; just de-lever

CAP_DOLLARS = 10000.0

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
    min_hist = max(SPAN_SLOW, VOL_WINDOW, IDX_VOL_WINDOW, ER_WINDOW) + 2
    if n_days < min_hist:
        return [0]*n_inst

    price_today = P[:, -1]
    price_prev  = P[:, -2]

    # Index, its vol, and ER
    g = np.exp(np.log(P).mean(axis=0))
    ret = g[1:] / g[:-1] - 1.0
    idx_vol = np.std(ret[-IDX_VOL_WINDOW:], ddof=0) + 1e-12

    delta = abs(g[-1] - g[-ER_WINDOW])
    noise = np.sum(np.abs(np.diff(g[-ER_WINDOW:])))
    er = delta / (noise + 1e-12)

    if er <= ER_LOW:
        w = 0.0
    elif er >= ER_HIGH:
        w = 1.0
    else:
        w = (er - ER_LOW) / (ER_HIGH - ER_LOW)

    thr_mult_eff = THRESHOLD_VOL_MULT * (CHOP_THR_MULT ** (1.0 - w))
    size_mult_eff = (CHOP_SIZE_MULT ** (1.0 - w))
    base_dollar_eff = BASE_TARGET_DOLLAR * size_mult_eff

    # EMA with regime-dependent span
    span = SPAN_SLOW if idx_vol > 0.01 else SPAN_FAST
    alpha = 2.0 / (span + 1.0)
    ema = np.empty_like(g); ema[0] = g[0]
    for t in range(1, n_days):
        ema[t] = alpha * g[t] + (1.0 - alpha) * ema[t-1]

    dev = g[-1] / max(ema[-1], 1e-12) - 1.0
    thr = thr_mult_eff * idx_vol

    if (w == 0.0 and CHOP_FLAT) or abs(dev) < thr:
        return [0]*n_inst

    direction = 1 if dev > 0 else -1

    # Per-instrument inverse-vol sizing
    win = P[:, -VOL_WINDOW-1:-1]
    ivol = np.std(win[:, 1:] / win[:, :-1] - 1.0, axis=1, ddof=0) + 1e-8

    scale = 1.0 + SIZE_SCALE_K * (abs(dev) / max(thr, 1e-12) - 1.0)
    scale = float(np.clip(scale, 0.5, 2.5))

    dollars = base_dollar_eff * scale / ivol
    raw = dollars / np.maximum(price_today, 1e-12)
    tgt_today = (np.floor(np.abs(raw) / max(1, LOT_SIZE)).astype(int) * max(1, LOT_SIZE)) * np.sign(raw)
    tgt_today = _clip_to_dollar_cap(tgt_today, price_today)
    tgt_today[tgt_today < 1] = 1
    tgt_today = (direction * tgt_today).astype(int)

    # Approximate yesterday's target for a small no-trade band
    g_prev = g[:-1]
    ema_prev = np.empty_like(g_prev); ema_prev[0] = g_prev[0]
    for t in range(1, len(g_prev)):
        ema_prev[t] = alpha * g_prev[t] + (1.0 - alpha) * ema_prev[t-1]
    dev_prev = g_prev[-1] / max(ema_prev[-1], 1e-12) - 1.0
    idx_vol_prev = np.std((g_prev[1:] / g_prev[:-1] - 1.0)[-IDX_VOL_WINDOW:], ddof=0) + 1e-12

    # Blend ER for previous day too
    if len(g_prev) > ER_WINDOW:
        delta_p = abs(g_prev[-1] - g_prev[-ER_WINDOW])
        noise_p = np.sum(np.abs(np.diff(g_prev[-ER_WINDOW:])))
        er_p = delta_p / (noise_p + 1e-12)
        if er_p <= ER_LOW:
            wp = 0.0
        elif er_p >= ER_HIGH:
            wp = 1.0
        else:
            wp = (er_p - ER_LOW) / (ER_HIGH - ER_LOW)
    else:
        wp = w
    thr_prev = THRESHOLD_VOL_MULT * (CHOP_THR_MULT ** (1.0 - wp)) * idx_vol_prev

    if (wp == 0.0 and CHOP_FLAT) or abs(dev_prev) < thr_prev:
        tgt_prev = np.zeros(n_inst, dtype=int)
    else:
        dir_prev = 1 if dev_prev > 0 else -1
        winp = P[:, -VOL_WINDOW-2:-2]
        ivolp = np.std(winp[:, 1:] / winp[:, :-1] - 1.0, axis=1, ddof=0) + 1e-8
        scalep = 1.0 + SIZE_SCALE_K * (abs(dev_prev) / max(thr_prev, 1e-12) - 1.0)
        scalep = float(np.clip(scalep, 0.5, 2.5))
        dollarsp = base_dollar_eff * scalep / ivolp
        rawp = dollarsp / np.maximum(price_prev, 1e-12)
        tgt_prev = (np.floor(np.abs(rawp) / max(1, LOT_SIZE)).astype(int) * max(1, LOT_SIZE)) * np.sign(rawp)
        tgt_prev = _clip_to_dollar_cap(tgt_prev, price_prev)
        tgt_prev[tgt_prev < 1] = 1
        tgt_prev = (dir_prev * tgt_prev).astype(int)

    # Cost-aware no-trade band
    delta = tgt_today - tgt_prev
    small = (np.abs(delta) * price_today) < NO_TRADE_MIN_DOLLARS
    y_final = tgt_today.copy()
    y_final[small] = tgt_prev[small]

    return y_final.astype(int).tolist()
