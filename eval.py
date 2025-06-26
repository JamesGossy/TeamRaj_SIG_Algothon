#!/usr/bin/env python

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from main import getMyPosition

# ─── User parameters ────────────────────────────────────────────────
prices_file      = "2024_prices.txt"
test_days        = 250       # only score the last 50 days
comm_rate        = 0.0005
dollar_pos_limit = 10000.0

nInst = None
nt = None

# ───────── load prices ─────────
def load_prices(fn):
    global nInst, nt
    df = pd.read_csv(fn, sep=r'\s+', header=None)
    prc = df.values.T          # shape: (nInst, nt)
    nInst, nt = prc.shape
    print(f"Loaded {nInst} instruments for {nt} days")
    return prc

# ───────── P/L calculator ─────────
def calcPL(prcHist, numTestDays):
    cash = 0.0
    curPos = np.zeros(nInst)
    totDVolume = 0.0
    value = 0.0
    dailyPL = []
    _, nt_local = prcHist.shape
    startDay = nt_local - numTestDays + 1

    for t in range(startDay, nt_local + 1):
        hist = prcHist[:, :t]
        price = hist[:, -1]

        if t < nt_local:
            rawPos = getMyPosition(hist)
            pos_limit = np.floor(dollar_pos_limit / price).astype(int)
            newPos = np.clip(rawPos, -pos_limit, pos_limit)

            delta = newPos - curPos
            traded = np.abs(delta) * price
            totDVolume += traded.sum()
            cash -= price.dot(delta) + comm_rate * traded.sum()
            curPos = newPos.copy()

        posValue = curPos.dot(price)
        todayPL = cash + posValue - value
        value = cash + posValue

        if t > startDay:
            print(f"Day {t}: value={value:.2f}, todayPL={todayPL:.2f}, totalVol={totDVolume:.0f}")
            dailyPL.append(todayPL)

    pll = np.array(dailyPL)
    mu = pll.mean()
    sigma = pll.std(ddof=0)
    sharpe = np.sqrt(249) * mu / sigma if sigma > 0 else 0.0
    ret = value / totDVolume if totDVolume > 0 else 0.0
    return mu, ret, sigma, sharpe, totDVolume, pll

# ───────── main ─────────
if __name__ == "__main__":
    prcAll = load_prices(prices_file)

    # run back-test on last test_days
    mu, ret, sigma, sharpe, dvol, pll = calcPL(prcAll, test_days)
    score = mu - 0.1 * sigma

    print("===== Summary =====")
    print(f"mean(PL):     {mu:.1f}")
    print(f"return:       {ret:.5f}")
    print(f"StdDev(PL):   {sigma:.2f}")
    print(f"annSharpe:    {sharpe:.2f}")
    print(f"totDvolume:   {dvol:.0f}")
    print(f"Score:        {score:.2f}")

    # ─── PLOTS ─────────
    days = np.arange(1, len(pll) + 1)

    plt.figure(figsize=(10,4))
    plt.bar(days, pll, width=1.0)
    plt.title('Daily P/L (last 50 days)')
    plt.xlabel('Test Day')
    plt.ylabel('P/L ($)')
    plt.grid(True)

    plt.figure(figsize=(10,4))
    plt.plot(days, np.cumsum(pll), lw=1)
    plt.title('Cumulative P/L (last 50 days)')
    plt.xlabel('Test Day')
    plt.ylabel('Cumulative P/L ($)')
    plt.grid(True)

    plt.figure(figsize=(8,4))
    plt.hist(pll, bins=30, edgecolor='black')
    plt.title('Distribution of Daily P/L (last 50 days)')
    plt.xlabel('Daily P/L ($)')
    plt.ylabel('Frequency')
    plt.grid(True)

    plt.tight_layout()
    plt.show()
