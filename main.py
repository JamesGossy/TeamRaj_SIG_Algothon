#!/usr/bin/env python
"""
Adaptive index trend follower using an exponential moving average (EMA) on the
geometric‑mean index.
"""

import numpy as np

# Strategy parameters
SPAN = 7                 # EMA span (in days)
EMA_THRESHOLD = 0.0005   # Minimum relative deviation (0.05%) to trigger trades
TARGET_DOLLAR = 1000.0   # Base dollar risk per instrument
VOL_WINDOW = 5           # Volatility measurement window (days)

def getMyPosition(price_history: np.ndarray) -> list[int]:
    """
    Return desired positions for each instrument based on an EMA‑filtered trend.
    If the index/EMA deviation is below EMA_THRESHOLD, the function returns zero positions.
    Otherwise it goes long or short all instruments (same direction) and sizes positions
    inversely with recent volatility, capping exposure at USD 10 000 per instrument.
    """
    # Convert to array and ensure shape (nInst, nDays)
    prices = np.asarray(price_history, dtype=float)
    if prices.ndim != 2:
        raise ValueError("price_history must be a 2D array")
    if prices.shape[0] != 50:
        prices = prices.T
    n_inst, n_days = prices.shape

    # Need enough history to compute EMA and volatility
    min_history = max(SPAN, VOL_WINDOW) + 2
    if n_days < min_history:
        return [0] * n_inst

    # Geometric mean index
    log_prices = np.log(prices)
    geom_index = np.exp(log_prices.mean(axis=0))

    # Exponential moving average of the index
    alpha = 2.0 / (SPAN + 1)
    ema = np.empty_like(geom_index)
    ema[0] = geom_index[0]
    for t in range(1, n_days):
        ema[t] = alpha * geom_index[t] + (1.0 - alpha) * ema[t - 1]

    # Relative deviation of index from its EMA
    deviation = geom_index[-1] / ema[-1] - 1.0
    if abs(deviation) < EMA_THRESHOLD:
        return [0] * n_inst  # stay flat if deviation too small

    # Direction of trades (+1 long, –1 short)
    direction = 1 if deviation > 0 else -1
    price_today = prices[:, -1]

    # Volatility estimation over the last VOL_WINDOW days
    window = prices[:, -VOL_WINDOW - 1 : -1]
    returns = window[:, 1:] / window[:, :-1] - 1.0
    vol = np.std(returns, axis=1, ddof=0) + 1e-8  # avoid zero division

    # Initial position sizing
    raw_shares = TARGET_DOLLAR / (price_today * vol)
    shares = np.floor(raw_shares).astype(int)

    # Cap notional exposure at USD 10 000 per instrument
    dollar_position = shares * price_today
    over_limit = dollar_position > 10000.0
    if np.any(over_limit):
        shares[over_limit] = np.floor(10000.0 / price_today[over_limit]).astype(int)

    # Ensure at least one share when taking a non‑zero position
    shares[shares < 1] = 1

    # Apply the common direction
    return (direction * shares).tolist()
