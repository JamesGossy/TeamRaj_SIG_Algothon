#!/usr/bin/env python

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from main import getMyPosition as getPosition

nInst = 50
nt = 0
commRate = 0.0005
dlrPosLimit = 10000

def loadPrices(fn):
    global nt, nInst
    df = pd.read_csv(fn, sep='\s+', header=None, index_col=None)
    (nt, nInst) = df.shape
    return df.values.T

pricesFile = "prices.txt"
prcAll = loadPrices(pricesFile)
print(f"Loaded {nInst} instruments for {nt} days")

def calcPL(prcHist, numTestDays):
    cash = 0.0
    curPos = np.zeros(nInst)
    totDVolume = 0.0
    value = 0.0
    todayPLL = []
    (_, nt_local) = prcHist.shape
    startDay = nt_local + 1 - numTestDays

    for t in range(startDay, nt_local + 1):
        prcHistSoFar = prcHist[:, :t]
        curPrices = prcHistSoFar[:, -1]

        if t < nt_local:
            # Trading, do not do it on the very last day of the test
            newPosOrig = getPosition(prcHistSoFar)
            posLimits = np.array([int(x) for x in dlrPosLimit / curPrices])
            newPos = np.clip(newPosOrig, -posLimits, posLimits)
            deltaPos = newPos - curPos
            dvolumes = curPrices * np.abs(deltaPos)
            dvolume = np.sum(dvolumes)
            totDVolume += dvolume
            comm = dvolume * commRate
            cash -= curPrices.dot(deltaPos) + comm
        else:
            newPos = np.array(curPos)

        curPos = np.array(newPos)
        posValue = curPos.dot(curPrices)
        todayPL = cash + posValue - value
        value = cash + posValue

        if t > startDay:
            ret = value / totDVolume if totDVolume > 0 else 0.0
            print(f"Day {t} value: {value:.2f} todayPL: ${todayPL:.2f} $-traded: {totDVolume:.0f} return: {ret:.5f}")
            todayPLL.append(todayPL)

    pll = np.array(todayPLL)
    plmu = np.mean(pll)
    plstd = np.std(pll)
    annSharpe = np.sqrt(249) * plmu / plstd if plstd > 0 else 0.0

    # return stats plus the daily P/L array
    return plmu, (value / totDVolume if totDVolume > 0 else 0.0), plstd, annSharpe, totDVolume, pll

# run the back-test
meanpl, ret, plstd, sharpe, dvol, pll = calcPL(prcAll, 200)
score = meanpl - 0.1 * plstd

print("=====")
print(f"mean(PL): {meanpl:.1f}")
print(f"return: {ret:.5f}")
print(f"StdDev(PL): {plstd:.2f}")
print(f"annSharpe(PL): {sharpe:.2f}")
print(f"totDvolume: {dvol:.0f}")
print(f"Score: {score:.2f}")

# ————— PLOTS —————
days = np.arange(1, len(pll) + 1)

plt.figure(figsize=(10, 4))
plt.bar(days, pll, width=1.0)
plt.title('Daily P/L')
plt.xlabel('Test Day')
plt.ylabel('P/L ($)')
plt.grid(True)

plt.figure(figsize=(10, 4))
plt.plot(days, np.cumsum(pll), linewidth=1)
plt.title('Cumulative P/L')
plt.xlabel('Test Day')
plt.ylabel('Cumulative P/L ($)')
plt.grid(True)

plt.figure(figsize=(8, 4))
plt.hist(pll, bins=30, edgecolor='black')
plt.title('Distribution of Daily P/L')
plt.xlabel('Daily P/L ($)')
plt.ylabel('Frequency')
plt.grid(True)

plt.tight_layout()
plt.show()
