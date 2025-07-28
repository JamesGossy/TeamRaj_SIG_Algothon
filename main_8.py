
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Conviction-weighted ensemble of two simple, robust signals:

A) EMA-on-index trend follower (with ER gating for sizing/threshold)
B) Index momentum over a short lookback (momentum-primary)

Goal:
- Keep the strong performance on the most recent 250 days (momentum tends to excel there),
  without tanking the full-history score. We blend A and B based on the index Efficiency
  Ratio (ER): when ER is high (clean trend), lean more on momentum; when ER is moderate,
  include the EMA component; both remain simple and interpretable.

Risk/Cost controls:
- Inverse-volatility sizing per instrument.
- $10k-per-stock notional cap at trade time.
- 10-share lot rounding.
- Small $1,000 per-name no-trade band using a one-day-ago target approximation.

Only NumPy. Stateless API compatible with the hackathon runner.
"""

import numpy as np

# ---------------- Core knobs (kept narrow to avoid overfitting) ----------------
# EMA component
SPAN_FAST = 7
SPAN_SLOW = 10
VOL_WINDOW = 5
IDX_VOL_WINDOW = 20
BASE_TARGET_DOLLAR_EMA = 1500.0
THRESHOLD_MULT_EMA = 0.4
SIZE_SCALE_K_EMA = 0.4
ER_WINDOW = 25
ER_LOW = 0.26
ER_HIGH = 0.56
CHOP_SIZE_MULT = 0.30      # EMA size shrink in choppy regimes
CHOP_THR_MULT  = 2.0       # EMA trigger widening in choppy regimes

# Momentum component
MOM_LOOKBACK = 5
MOM_THRESH   = 0.003
BASE_TARGET_DOLLAR_MOM = 1000.0
ER_LOW_MOM  = 0.20
ER_HIGH_MOM = 0.60
CHOP_SIZE_MULT_MOM = 0.30  # Momentum: ER used ONLY to de-lever size (never blocks the signal)

# Ensemble execution
LOT_SIZE = 10
NO_TRADE_MIN_DOLLARS = 1000.0
CAP_DOLLARS = 10000.0

# Mixing: ER -> momentum weight via sigmoid; enforce a floor when momentum is active
MIX_ER_MID   = 0.80      # higher midpoint => require cleaner trend to favor momentum
MIX_ER_SLOPE = 12.0
MOM_WEIGHT_FLOOR = 0.50  # when momentum is active, at least this much weight goes to it

# ----------------------------------------------------------------------------

def _clip_to_dollar_cap(shares, prices_today, cap_dollars=CAP_DOLLARS):
    max_shares = np.floor(cap_dollars / np.maximum(prices_today, 1e-12)).astype(int)
    return np.clip(shares, -max_shares, max_shares).astype(int)

def _ema_er_component(P):
    """Return (target_shares, er, dev, thr)."""
    if P.shape[0] != 50:
        P = P.T
    n_inst, n_days = P.shape
    if n_days < max(SPAN_SLOW, VOL_WINDOW, IDX_VOL_WINDOW, ER_WINDOW) + 2:
        return np.zeros(n_inst, dtype=int), 0.0, 0.0, 0.0

    prices_today = P[:, -1]
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

    thr_mult_eff = THRESHOLD_MULT_EMA * (CHOP_THR_MULT ** (1.0 - w))
    base_dollar_eff = BASE_TARGET_DOLLAR_EMA * (CHOP_SIZE_MULT ** (1.0 - w))

    # EMA deviation
    span = SPAN_SLOW if idx_vol > 0.01 else SPAN_FAST
    alpha = 2.0 / (span + 1.0)
    ema = np.empty_like(g); ema[0] = g[0]
    for t in range(1, n_days):
        ema[t] = alpha * g[t] + (1.0 - alpha) * ema[t-1]

    dev = g[-1] / max(ema[-1], 1e-12) - 1.0
    thr = thr_mult_eff * idx_vol

    if abs(dev) < thr:
        return np.zeros(n_inst, dtype=int), er, dev, thr

    direction = 1 if dev > 0 else -1

    # Per-name inverse-vol sizing
    win = P[:, -VOL_WINDOW-1:-1]
    ivol = np.std(win[:, 1:] / win[:, :-1] - 1.0, axis=1, ddof=0) + 1e-8

    scale = 1.0 + SIZE_SCALE_K_EMA * (abs(dev) / max(thr, 1e-12) - 1.0)
    scale = float(np.clip(scale, 0.5, 2.5))

    dollars = base_dollar_eff * scale / ivol
    raw = dollars / np.maximum(prices_today, 1e-12)
    tgt = (np.floor(np.abs(raw) / max(1, LOT_SIZE)).astype(int) * max(1, LOT_SIZE)) * np.sign(raw)
    tgt = _clip_to_dollar_cap(tgt, prices_today)
    tgt[tgt < 1] = 1
    return (direction * tgt).astype(int), er, dev, thr

def _momentum_component(P):
    """Return (target_shares, er, mom, mom_thresh). ER only scales size; it never blocks trades."""
    if P.shape[0] != 50:
        P = P.T
    n_inst, n_days = P.shape
    if n_days < max(VOL_WINDOW, MOM_LOOKBACK, ER_WINDOW) + 2:
        return np.zeros(n_inst, dtype=int), 0.0, 0.0, MOM_THRESH

    prices_today = P[:, -1]
    g = np.exp(np.log(P).mean(axis=0))

    mom = g[-1] / max(g[-MOM_LOOKBACK-1], 1.0e-12) - 1.0
    if abs(mom) < MOM_THRESH:
        return np.zeros(n_inst, dtype=int), 0.0, mom, MOM_THRESH
    direction = 1 if mom > 0 else -1

    # ER for size only
    delta = abs(g[-1] - g[-ER_WINDOW])
    noise = np.sum(np.abs(np.diff(g[-ER_WINDOW:])))
    er = delta / (noise + 1e-12)
    if er <= ER_LOW_MOM:
        w = 0.0
    elif er >= ER_HIGH_MOM:
        w = 1.0
    else:
        w = (er - ER_LOW_MOM) / (ER_HIGH_MOM - ER_LOW_MOM)

    base_eff = BASE_TARGET_DOLLAR_MOM * (CHOP_SIZE_MULT_MOM ** (1.0 - w))

    win = P[:, -VOL_WINDOW-1:-1]
    ivol = np.std(win[:, 1:] / win[:, :-1] - 1.0, axis=1, ddof=0) + 1e-8

    raw = (base_eff / ivol) / np.maximum(prices_today, 1e-12)
    tgt = (np.floor(np.abs(raw) / max(1, LOT_SIZE)).astype(int) * max(1, LOT_SIZE)) * np.sign(raw)
    tgt = _clip_to_dollar_cap(tgt, prices_today)
    tgt[tgt < 1] = 1
    return (direction * tgt).astype(int), er, mom, MOM_THRESH

def _mix_weight_from_er(er):
    return 1.0 / (1.0 + np.exp(-MIX_ER_SLOPE * (er - MIX_ER_MID)))

def getMyPosition(price_history):
    P = np.asarray(price_history, dtype=float)
    if P.ndim != 2:
        raise ValueError("price_history must be a 2D array")
    if P.shape[0] != 50:
        P = P.T
    n_inst, n_days = P.shape
    if n_days < max(SPAN_SLOW, VOL_WINDOW, IDX_VOL_WINDOW, ER_WINDOW, MOM_LOOKBACK) + 2:
        return [0]*n_inst

    # Today's component targets
    y_ema, er_e, dev, thr = _ema_er_component(P)
    y_mom, er_m, mom, mom_thr = _momentum_component(P)

    if np.all(y_ema == 0) and np.all(y_mom == 0):
        return [0]*n_inst

    # ER-based mix, with momentum floor when active
    er = max(er_e, er_m)
    w_m = _mix_weight_from_er(er)
    if not np.all(y_mom == 0):
        w_m = max(w_m, MOM_WEIGHT_FLOOR)
    w_m = float(np.clip(w_m, 0.0, 1.0))

    # If signals disagree in sign, bias by "conviction"
    conv_e = max(0.0, abs(dev) - thr) / (thr + 1e-12) if thr > 0 else 0.0
    conv_m = max(0.0, abs(mom) - mom_thr) / (mom_thr + 1e-12) if mom_thr > 0 else 0.0
    s_e = 0 if np.all(y_ema == 0) else (1 if y_ema.sum() > 0 else -1)
    s_m = 0 if np.all(y_mom == 0) else (1 if y_mom.sum() > 0 else -1)

    if s_e != 0 and s_m != 0 and s_e != s_m:
        if conv_m > conv_e:
            w_m = max(0.8, w_m)
        else:
            w_m = min(0.2, w_m)

    # Blend to final target
    y_float = w_m * y_mom.astype(float) + (1.0 - w_m) * y_ema.astype(float)
    lot = max(1, LOT_SIZE)
    tgt_today = (np.floor(np.abs(y_float) / lot).astype(int) * lot) * np.sign(y_float)

    # Previous blended target for a small no-trade band
    prices_today = P[:, -1]
    if n_days > 61:
        P_prev = P[:, :-1]
        y_ema_p, er_e_p, dev_p, thr_p = _ema_er_component(P_prev)
        y_mom_p, er_m_p, mom_p, mom_thr_p = _momentum_component(P_prev)
        if np.all(y_ema_p == 0) and np.all(y_mom_p == 0):
            tgt_prev = np.zeros(n_inst, dtype=int)
        else:
            er_p = max(er_e_p, er_m_p)
            w_m_p = _mix_weight_from_er(er_p)
            if not np.all(y_mom_p == 0):
                w_m_p = max(w_m_p, MOM_WEIGHT_FLOOR)
            # simple previous disagreement resolution
            if (not np.all(y_ema_p == 0)) and (not np.all(y_mom_p == 0)):
                s_e_p = 1 if y_ema_p.sum() > 0 else -1
                s_m_p = 1 if y_mom_p.sum() > 0 else -1
                if s_e_p != s_m_p:
                    if abs(mom_p) - mom_thr_p > abs(dev_p) - thr_p:
                        w_m_p = max(0.8, w_m_p)
                    else:
                        w_m_p = min(0.2, w_m_p)
            y_prev_float = w_m_p * y_mom_p.astype(float) + (1.0 - w_m_p) * y_ema_p.astype(float)
            tgt_prev = (np.floor(np.abs(y_prev_float) / lot).astype(int) * lot) * np.sign(y_prev_float)
    else:
        tgt_prev = np.zeros(n_inst, dtype=int)

    # Cost-aware no-trade band
    delta = tgt_today - tgt_prev
    small = (np.abs(delta) * prices_today) < NO_TRADE_MIN_DOLLARS
    y_final = tgt_today.copy()
    y_final[small] = tgt_prev[small]

    return y_final.astype(int).tolist()
