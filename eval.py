#!/usr/bin/env python

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import importlib
import main

# ─── User parameters ────────────────────────────────────────────────
prices_file      = "prices.txt"
test_days        = 200
comm_rate        = 0.0005
dollar_pos_limit = 10000.0

# Amount of per-price noise to inject into the *execution* price (e.g. 0.01 = 1%)
noise_pct        = 0.001
random_seed      = 42
# ────────────────────────────────────────────────────────────────────


def load_prices(fn):
    df = pd.read_csv(fn, sep=r'\s+', header=None)
    prc = df.values.T
    print(f"Loaded {prc.shape[0]} instruments for {prc.shape[1]} days")
    return prc


def calcPL(prcHist: np.ndarray,
           numTestDays: int,
           noise_pct: float = 0.0,
           seed: int | None = None):
    """
    Calculate P/L series, injecting noise *only* on the execution price each day.
    Returns: (mu, ret, sigma, sharpe, totDVolume, dailyPL_array)
    """
    # prepare RNG if needed
    rng = np.random.RandomState(seed) if noise_pct and seed is not None else None

    prc_exec = prcHist            # true prices for execution & P/L
    nInst, nt = prc_exec.shape

    cash = 0.0
    curPos = np.zeros(nInst)
    totDVolume = 0.0
    value = 0.0
    dailyPL = []

    start_day = nt - numTestDays + 1
    for t in range(start_day, nt + 1):
        # 1) True execution price for today
        price_ex = prc_exec[:, t-1]

        # 2) True history (no corruption)
        hist_true = prc_exec[:, :t]

        # 3) Simulate noisy *fill* price for today only
        if noise_pct and rng is not None:
            noise = noise_pct * rng.randn(nInst)
            # Option A: multiplicative Gaussian shock
            price_sig = price_ex * (1.0 + noise)

            # Option B: log-normal shock (uncomment if preferred)
            # price_sig = price_ex * np.exp(noise_pct * rng.randn(nInst))
        else:
            price_sig = price_ex.copy()

        # 4) Build the history fed to your strategy
        hist_sig = hist_true.copy()
        hist_sig[:, -1] = price_sig

        # 5) Call your algo on the noisy history
        if t < nt:
            rawPos = main.getMyPosition(hist_sig)

            # enforce dollar-limit at the *true* execution price
            pos_limit = np.floor(dollar_pos_limit / price_ex).astype(int)
            newPos = np.clip(rawPos, -pos_limit, pos_limit)

            # settle trades at true execution price
            delta = newPos - curPos
            traded = np.abs(delta) * price_ex
            totDVolume += traded.sum()
            cash -= price_ex.dot(delta) + comm_rate * traded.sum()
        else:
            newPos = curPos.copy()

        # 6) Update position and mark-to-market
        curPos = newPos.copy()
        posValue = curPos.dot(price_ex)
        todayPL = cash + posValue - value
        value = cash + posValue

        # 7) Record P/L (skip the very first day)
        if t > start_day:
            dailyPL.append(todayPL)

    pll   = np.array(dailyPL)
    mu    = pll.mean()
    sigma = pll.std(ddof=0)
    sharpe = np.sqrt(249) * mu / sigma if sigma > 0 else 0.0
    ret    = value / totDVolume if totDVolume > 0 else 0.0

    return mu, ret, sigma, sharpe, totDVolume, pll


if __name__ == "__main__":
    prcAll = load_prices(prices_file)

    # ─── Regular test ────────────────────────────────────────────────
    mu, ret, sigma, sharpe, dvol, pll = calcPL(
        prcAll, test_days, noise_pct=0.0
    )
    score = mu - 0.1 * sigma
    print("\n=== Regular Test ===")
    print(f"Score: {score:.2f}, meanPL: {mu:.1f}, return: {ret:.5f}, "
          f"σ: {sigma:.2f}, annSharpe: {sharpe:.2f}")

    # ─── Reset strategy state ─────────────────────────────────────────
    importlib.reload(main)

    # ─── Noise test ──────────────────────────────────────────────────
    mu_n, ret_n, sigma_n, sharpe_n, dvol_n, pll_n = calcPL(
        prcAll, test_days, noise_pct=noise_pct, seed=random_seed
    )
    score_n = mu_n - 0.1 * sigma_n
    print(f"\n=== Noise Test (noise_pct={noise_pct}) ===")
    print(f"Score: {score_n:.2f}, meanPL: {mu_n:.1f}, return: {ret_n:.5f}, "
          f"σ: {sigma_n:.2f}, annSharpe: {sharpe_n:.2f}")

    # ─── Plot results of the noise test ───────────────────────────────
    days = np.arange(1, len(pll_n) + 1)
    plt.figure(figsize=(10,4))
    plt.bar(days, pll_n, width=1.0)
    plt.title(f'Daily P/L (noise_pct={noise_pct})')
    plt.xlabel('Test Day'); plt.ylabel('P/L ($)'); plt.grid(True)

    plt.figure(figsize=(10,4))
    plt.plot(days, np.cumsum(pll_n), lw=1)
    plt.title(f'Cumulative P/L (noise_pct={noise_pct})')
    plt.xlabel('Test Day'); plt.ylabel('Cumulative P/L ($)'); plt.grid(True)

    plt.figure(figsize=(8,4))
    plt.hist(pll_n, bins=30, edgecolor='black')
    plt.title(f'Distribution of Daily P/L (noise_pct={noise_pct})')
    plt.xlabel('Daily P/L ($)'); plt.ylabel('Frequency'); plt.grid(True)

    plt.tight_layout()
    plt.show()
