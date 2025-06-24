#!/usr/bin/env python

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from main import getMyPosition as getPosition

# ───────── constants ─────────
PRICE_FILE    = Path("prices.txt")
COMM_RATE     = 0.0005    # commission rate (5 bps)
POS_LIMIT_USD = 10000
TRAIN_DAYS    = 250
TEST_DAYS     = 50
NOISE_PCT     = 2       # ±2% daily-return noise

# ───────── data loader ─────────
def loadPrices(fn):
    df = pd.read_csv(fn, sep='\s+', header=None)
    prc = df.values.T  # shape: (nInst, nt)
    nInst, nt = prc.shape
    print(f"Loaded {nInst} instruments × {nt} days\n")
    return prc

# ───────── P/L calculator ─────────
def calcPL(prcHist, numTestDays):
    nInst, nt_local = prcHist.shape
    cash = 0.0
    curPos = np.zeros(nInst, dtype=int)
    totalDVol = 0.0
    value = 0.0
    pl_list = []
    startDay = nt_local - numTestDays + 1

    for t in range(startDay, nt_local + 1):
        prices = prcHist[:, t-1]
        if t <= nt_local - 1:
            tgt = np.asarray(getPosition(prcHist[:, :t]), int)
            cap = np.floor(POS_LIMIT_USD / prices).astype(int)
            tgt = np.clip(tgt, -cap, cap)
            delta = tgt - curPos
            dvol = np.abs(delta) * prices
            totalDVol += dvol.sum()
            cash -= prices.dot(delta) + dvol.sum() * COMM_RATE
            curPos = tgt
        val = cash + curPos.dot(prices)
        todayPL = val - value
        value = val
        if t > startDay:
            pl_list.append(todayPL)
    arr = np.array(pl_list)
    return arr.mean(), arr.std(ddof=0), totalDVol, arr

# ───────── evaluation functions ─────────
def walkForward(prc):
    _, nt = prc.shape
    scores = []
    start = 0
    while start + TRAIN_DAYS + TEST_DAYS <= nt:
        block = prc[:, : start + TRAIN_DAYS + TEST_DAYS]
        m, s, _, _ = calcPL(block, TEST_DAYS)
        scores.append(m - 0.1 * s)
        start += TEST_DAYS
    return np.array(scores)

def noiseTest(prc, repeats=10):
    rng = np.random.default_rng(42)
    vals = []
    for _ in range(repeats):
        ret = prc[:,1:] / prc[:,:-1] - 1
        noisy = np.concatenate([
            prc[:,:1],
            prc[:,:-1] * (1 + ret * (1 + rng.normal(0, NOISE_PCT/100, ret.shape)))
        ], axis=1)
        vals.append(walkForward(noisy).mean())
    return float(np.mean(vals))

def shuffleTest(prc, repeats=20):
    rng = np.random.default_rng(42)
    vals = []
    for _ in range(repeats):
        sh = prc.copy()
        for i in range(sh.shape[0]):
            sh[i] = np.roll(sh[i], rng.integers(sh.shape[1]))
        vals.append(walkForward(sh).mean())
    return float(np.mean(vals))

# ───────── main script ─────────
if __name__ == "__main__":
    prcAll = loadPrices(PRICE_FILE)

    # 1) Walk-forward
    wf_scores = walkForward(prcAll)
    wts = np.arange(1, len(wf_scores)+1)
    tw_mean = (wf_scores * wts).sum() / wts.sum()

    # 2) Noise
    noise_mean = noiseTest(prcAll)

    # 3) Shuffle
    shuffle_mean = shuffleTest(prcAll)

    # ───────── summary display ─────────
    print("========== Evaluation Summary ==========")
    print(f"Walk-forward folds : {wf_scores.round(2)}")
    print(f"Time-weighted mean : {tw_mean:.2f}\n")
    print("---- Robustness Tests ----")
    print(f"Noise test (±{NOISE_PCT}%)   : {noise_mean:+.2f}")
    print(f"Shuffle test         : {shuffle_mean:+.2f}")
    print("========================================\n")
