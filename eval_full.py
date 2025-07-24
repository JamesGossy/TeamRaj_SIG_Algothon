#!/usr/bin/env python
"""
eval_full.py – Algathon scorer (2022-24, walk-forward + full-history noise)
Adds Max Draw-down and 5 % left-tail risk columns.
"""
from __future__ import annotations
import importlib, numpy as np, pandas as pd, main
from main import getMyPosition

# ────────── scenario files ──────────
PRICE_FILES = [
    "2022_prices1.txt",   # 500 d
    "2022_prices2.txt",   # 500 d
    "2023_prices.txt",    # 750 d
    "2024_prices.txt",    # 1250 d
    "prices.txt",    # 750 d
]

# ────────── evaluation knobs ──────────
TRAIN_DAYS, TEST_DAYS = 250, 50
NOISE_PCT,  LAMBDA_DECAY = 0.001, 0.10
COMM_RATE,  POS_LIMIT_USD = 0.0005, 10_000.0

# ────────── helpers ──────────
def load_prices(path: str) -> np.ndarray:
    return pd.read_csv(path, sep=r"\s+", header=None).values.T        # (nInst×nDays)

def calcPL(prcHist: np.ndarray, numTestDays: int,
           noise_pct: float = 0.0, seed: int | None = None):
    """Organisers’ logic (+ optional noise).  Returns score tuple + daily PL arr."""
    rng  = np.random.default_rng(seed) if seed is not None else np.random
    nInst, nt = prcHist.shape
    cash = 0.0; cur = np.zeros(nInst); totVol = value = 0.0; daily = []

    startDay = nt - numTestDays + 1
    for t in range(startDay, nt + 1):
        hist, price = prcHist[:, :t], prcHist[:, t-1].copy()
        if noise_pct: price *= 1 + rng.normal(0, noise_pct, nInst)

        if t < nt:                                         # no trade on last day
            raw = getMyPosition(hist);  lim = np.floor(POS_LIMIT_USD/price).astype(int)
            newPos = np.clip(raw, -lim, lim)
            delt = newPos - cur;  traded = np.abs(delt)*price
            totVol += traded.sum()
            cash -= price.dot(delt) + COMM_RATE*traded.sum();  cur = newPos

        portVal = cur.dot(price)
        daily.append(cash + portVal - value);  value = cash + portVal

    pll = np.array(daily[1:])                      # first element is 0
    mu, sigma = pll.mean(), pll.std(ddof=0)
    score = mu - 0.1*sigma;  sharpe = np.sqrt(249)*mu/sigma if sigma else 0.0
    return score, mu, sigma, sharpe, pll          # <--  return daily PL

def walk_forward(prc, train=TRAIN_DAYS, test=TEST_DAYS, λ=LAMBDA_DECAY):
    folds, start = [], 0; _, nt = prc.shape
    while start + train + test <= nt:
        importlib.reload(main)
        seg = prc[:, :start+train+test]
        s, *_ = calcPL(seg, test)
        folds.append(s);  start += test
    folds = np.asarray(folds);  w = np.exp(λ*np.arange(len(folds)))
    return folds, folds.mean(), (folds*w).sum()/w.sum()

def max_drawdown(cum: np.ndarray) -> float:
    peak = np.maximum.accumulate(cum);  draw = cum - peak
    return draw.min()                   # negative value ⇒ draw-down

def full_risk_stats(prices: np.ndarray):
    """Run once on full file (no noise) to get MaxDD & Tail-5 %."""
    _, _, _, _, pl = calcPL(prices, numTestDays=prices.shape[1])
    cum = pl.cumsum()
    mdd = max_drawdown(cum)
    tail = np.percentile(pl, 5)         # 5 % left-tail
    return mdd, tail

def fnum(x: float, w: int=9) -> str:
    return f"{x:+{w}.2f}" if np.isfinite(x) else f"{'—':>{w}}"

# ────────── main evaluation ──────────
if __name__ == "__main__":
    rows = []
    for fn in PRICE_FILES:
        P = load_prices(fn);  nDays = P.shape[1]
        folds, eq, exp = walk_forward(P)
        noise_score    = calcPL(P, nDays, noise_pct=NOISE_PCT, seed=42)[0]
        mdd, tail      = full_risk_stats(P)
        rows.append((fn, nDays, eq, exp, noise_score, mdd, tail, folds))

    # ─────────── scoreboard ───────────
    print("\n======== 2022-24  SCENARIO SCORECARD ========\n")
    hdr = f"{'File':<18}{'Days':>6}{'EQ-Mean':>10}{'EXP-Mean':>10}{'Noise':>10}{'MaxDD':>10}{'Tail-5%':>10}"
    print(hdr);  print("-"*len(hdr))

    for fn, nD, eq, ex, nz, mdd, tail, f in rows:
        print(f"{fn:<18}{nD:6d} {fnum(eq)} {fnum(ex)} {fnum(nz)}   {fnum(mdd)}{fnum(tail)}")
