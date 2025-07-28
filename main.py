#!/usr/bin/env python
"""Index momentum strategy with a geometric-mean index and volatility-scaled sizing.

This strategy computes the market index as the geometric mean of all 50 instruments’
prices, then measures its momentum over a short lookback window. Only when the
absolute momentum exceeds a threshold does it take positions; otherwise it stays flat.
Positions are sized inversely to each instrument’s recent volatility and capped at
$10,000 notional.  A smaller per-instrument risk target of $1,000 helps improve
risk-adjusted returns on the provided data.

Author: participant in Algothon Pt 3
"""

import numpy as np

# Parameters: 5-day lookback, 0.3% momentum threshold,
# $1 000 risk target per instrument, and volatility window equal to the lookback.
LOOKBACK = 5
# Momentum threshold: require at least ±0.3% move in the geometric index
THRESH = 0.003
# Dollar risk target per instrument
TARGET_DOLLAR = 1000.0
# Volatility estimation window (set equal to LOOKBACK)
VOL_WINDOW = LOOKBACK

def getMyPosition(price_history: np.ndarray) -> list[int]:
    """
    Determine positions for each of the 50 instruments based on the momentum
    of a geometric-mean market index.

    Parameters
    ----------
    price_history : np.ndarray
        Price history as a (nInst x nDays) or (nDays x nInst) array.

    Returns
    -------
    list[int]
        Integer desired positions for each instrument.
    """
    prices = np.asarray(price_history, dtype=float)
    # Ensure array shape is (nInst, nDays)
    if prices.shape[0] != 50:
        prices = prices.T
    n_inst, n_days = prices.shape

    # Require enough data for momentum and volatility calculations
    if n_days <= max(LOOKBACK, VOL_WINDOW):
        return [0] * n_inst

    # 1) Compute a geometric-mean index and its momentum
    log_prices = np.log(prices)
    geom_index = np.exp(log_prices.mean(axis=0))
    mom = geom_index[-1] / geom_index[-LOOKBACK - 1] - 1.0

    # If momentum magnitude is too small, stay flat
    if abs(mom) < THRESH:
        return [0] * n_inst

    # Determine direction of trade
    direction = 1 if mom > 0 else -1
    price_today = prices[:, -1]

    # 2) Estimate per-instrument volatility over the recent VOL_WINDOW
    window = prices[:, -VOL_WINDOW - 1 : -1]
    returns = window[:, 1:] / window[:, :-1] - 1.0
    vol = np.std(returns, axis=1, ddof=0) + 1e-8  # avoid zero division

    # 3) Size positions inversely to price and volatility
    raw_shares = TARGET_DOLLAR / (price_today * vol)
    shares = np.floor(raw_shares).astype(int)

    # Enforce $10k notional limit per stock
    dollar_position = shares * price_today
    over_limit = dollar_position > 10000.0
    shares[over_limit] = np.floor(10000.0 / price_today[over_limit]).astype(int)

    # Ensure at least one share if a position is taken
    shares[shares < 1] = 1

    # 4) Apply the direction to all positions
    positions = (direction * shares).tolist()
    return positions
