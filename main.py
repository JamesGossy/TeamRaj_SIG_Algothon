#!/usr/bin/env python

import numpy as np

# Strategy settings
WINDOW_SMA = 13      # how many days to look back for the average
REBALANCE_DAYS = 5   # how often to rebalance
NUM_TRADES = 6       # number of long and short trades
GAP_THRESHOLD = 0.018
VOLATILITY_WINDOW = 20
RISK_DOLLARS = 1000  # risk budget per name
MAX_LEG_DOLLARS = 10000

# Keep track of last rebalance day and positions
last_rebalance = 0
positions = None


def getMyPosition(price_history):
    global last_rebalance, positions
    
    # Convert to numpy array
    prices = np.array(price_history, dtype=float)
    # Make sure prices has shape (50, days)
    if prices.shape[0] != 50:
        prices = prices.T

    num_instruments, num_days = prices.shape
    today = num_days - 1

    # Initialize positions on first call
    if positions is None:
        positions = [0] * num_instruments

    # Not enough data or not time to rebalance yet
    if num_days <= max(WINDOW_SMA, VOLATILITY_WINDOW):
        return positions
    if today - last_rebalance < REBALANCE_DAYS:
        return positions

    # Compute simple moving average for each instrument
    sma = []
    for i in range(num_instruments):
        window = prices[i, today - WINDOW_SMA + 1 : today + 1]
        sma.append(sum(window) / len(window))

    # Compute gap from current price to SMA
    gaps = []
    for i in range(num_instruments):
        gap = prices[i, today] / sma[i] - 1.0
        gaps.append(gap)

    # Rank instruments by gap
    sorted_indices = sorted(range(num_instruments), key=lambda i: gaps[i])

    longs = []
    for i in sorted_indices[:NUM_TRADES]:
        if gaps[i] <= -GAP_THRESHOLD:
            longs.append(i)

    shorts = []
    for i in sorted_indices[-NUM_TRADES:]:
        if gaps[i] >= GAP_THRESHOLD:
            shorts.append(i)

    # Prepare new positions
    new_positions = [0] * num_instruments

    # Only trade if we have both longs and shorts
    if longs and shorts:
        # Calculate daily returns over the volatility window
        returns = []
        for i in range(num_instruments):
            ret = []
            for d in range(today - VOLATILITY_WINDOW + 1, today + 1):
                ret.append(prices[i, d] / prices[i, d-1] - 1)
            returns.append(ret)

        # Compute standard deviation for each instrument
        volatility = []
        for ret in returns:
            volatility.append(np.std(ret))

        # Replace any zero volatility with the median of non-zero volatilities
        non_zero_vol = [v for v in volatility if v > 0]
        fallback = np.median(non_zero_vol)
        for i in range(len(volatility)):
            if volatility[i] == 0:
                volatility[i] = fallback

        # Determine position sizes
        for i in longs:
            size = int(RISK_DOLLARS / (volatility[i] * prices[i, today]))
            size = max(1, min(size, int(MAX_LEG_DOLLARS / prices[i, today])))
            new_positions[i] = size

        for i in shorts:
            size = int(RISK_DOLLARS / (volatility[i] * prices[i, today]))
            size = max(1, min(size, int(MAX_LEG_DOLLARS / prices[i, today])))
            new_positions[i] = -size

    # Save the new state
    positions = new_positions
    last_rebalance = today

    return new_positions
