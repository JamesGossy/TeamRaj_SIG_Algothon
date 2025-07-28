
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
No-peek regime-gated EMA trend follower (balanced preset).

How this was chosen (outside this file):
- We defined three simple presets (trend_lean / balanced / chop_defens) and
  selected the "balanced" preset using only pre-target data (days 1000-1250),
  to avoid overfitting to the last 250 days.
- This preset produced strong scores on 1000-1250 and materially improved
  1250-1500 vs pure trend, maximizing the combined 500-day window without
  tuning on 1250-1500 directly.

Mechanics:
- Geometric-mean index EMA signal with volatility-based dynamic threshold.
- Efficiency Ratio (ER) gating de-levers/widens trigger in choppy regimes.
- Inverse-vol per-instrument sizing; $10k cap at trade time.
- 10-share lot rounding and $2k per-name no-trade band to reduce churn.
'''
import numpy as np

# --- Balanced preset parameters (picked with no-peek validation) ---
SPAN_FAST = 7
SPAN_SLOW = 10
VOL_WINDOW = 5
IDX_VOL_WINDOW = 20

BASE_TARGET_DOLLAR = 1500.0
THRESHOLD_VOL_MULT = 0.4
SIZE_SCALE_K = 0.4
LOT_SIZE = 10
NO_TRADE_MIN_DOLLARS = 2000.0

ER_WINDOW = 25
ER_LOW  = 0.26
ER_HIGH = 0.56
CHOP_SIZE_MULT = 0.30
CHOP_THR_MULT  = 2.0
CHOP_FLAT = False

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

    prices_today = P[:, -1]
    prices_prev  = P[:, -2]

    # Index & vol
    g = np.exp(np.log(P).mean(axis=0))
    ret = g[1:] / g[:-1] - 1.0
    idx_vol = np.std(ret[-IDX_VOL_WINDOW:], ddof=0) + 1e-12

    # ER gating
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
    base_dollar_eff = BASE_TARGET_DOLLAR * (CHOP_SIZE_MULT ** (1.0 - w))

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

    # per-name inverse-vol sizing
    win = P[:, -VOL_WINDOW-1:-1]
    ivol = np.std(win[:, 1:] / win[:, :-1] - 1.0, axis=1, ddof=0) + 1e-8

    scale = 1.0 + SIZE_SCALE_K * (abs(dev) / max(thr, 1e-12) - 1.0)
    scale = float(np.clip(scale, 0.5, 2.5))

    dollars = base_dollar_eff * scale / ivol
    raw = dollars / np.maximum(prices_today, 1e-12)
    tgt_today = (np.floor(np.abs(raw) / max(1, LOT_SIZE)).astype(int) * max(1, LOT_SIZE)) * np.sign(raw)
    tgt_today = _clip_to_dollar_cap(tgt_today, prices_today)
    tgt_today[tgt_today < 1] = 1
    tgt_today = (direction * tgt_today).astype(int)

    # Yesterday target approx for no-trade band
    g_prev = g[:-1]
    ema_prev = np.empty_like(g_prev); ema_prev[0] = g_prev[0]
    for t in range(1, len(g_prev)):
        ema_prev[t] = alpha * g_prev[t] + (1.0 - alpha) * ema_prev[t-1]
    dev_prev = g_prev[-1] / max(ema_prev[-1], 1e-12) - 1.0
    idx_vol_prev = np.std((g_prev[1:] / g_prev[:-1] - 1.0)[-IDX_VOL_WINDOW:], ddof=0) + 1e-12

    # ER prev approx (same gates)
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
        rawp = dollarsp / np.maximum(prices_prev, 1e-12)
        tgt_prev = (np.floor(np.abs(rawp) / max(1, LOT_SIZE)).astype(int) * max(1, LOT_SIZE)) * np.sign(rawp)
        tgt_prev = _clip_to_dollar_cap(tgt_prev, prices_prev)
        tgt_prev[tgt_prev < 1] = 1
        tgt_prev = (dir_prev * tgt_prev).astype(int)

    # No-trade band
    delta = tgt_today - tgt_prev
    small = (np.abs(delta) * prices_today) < NO_TRADE_MIN_DOLLARS
    y_final = tgt_today.copy()
    y_final[small] = tgt_prev[small]

    return y_final.astype(int).tolist()
