#!/usr/bin/env python
"""Index momentum strategy using a geometric-mean index and volatility-scaled sizing.

This strategy calculates a geometric-mean market index (the exponential of the
average log price across all 50 instruments) to gauge broad market direction.
When the momentum of this index over a short lookback exceeds a threshold,
the algorithm takes uniform long or short positions in all instruments,
with position sizes scaled inversely to each instrument’s recent volatility.
Each position is capped at $10,000 notional.  If the momentum magnitude
falls below the threshold, it stays flat.
"""

import numpy as np

# Tunable parameters for the momentum lookback, trading threshold and sizing
LOOKBACK      = 5        # days over which to measure momentum
THRESH        = 0.002    # minimum absolute momentum (0.2%) to trigger trades
TARGET_DOLLAR = 1500.0   # risk target per instrument in dollars
VOL_WINDOW    = LOOKBACK  # window length for volatility estimation

def getMyPosition(price_history: np.ndarray) -> list[int]:
    """
    Compute desired positions for each of 50 instruments based on the momentum of a
    geometric-mean index.  If the momentum magnitude is below THRESH, the function
    returns zero positions.  Otherwise, it takes long (or short) positions in all
    instruments, with sizes scaled by the inverse of recent volatility and capped at
    $10,000 notional.

    Parameters
    ----------
    price_history : np.ndarray
        Historical prices with shape (nInst, nDays) or (nDays, nInst).

    Returns
    -------
    list[int]
        Desired integer positions for each instrument.
    """
    # Coerce to a 2D array of shape (nInst, nDays)
    prices = np.asarray(price_history, dtype=float)
    if prices.shape[0] != 50:
        prices = prices.T
    n_inst, n_days = prices.shape

    # Require sufficient data for momentum and volatility calculations
    if n_days <= max(LOOKBACK, VOL_WINDOW):
        return [0] * n_inst

    # --- 1) Geometric-mean index and momentum ---
    # Use logs to compute the geometric mean across instruments
    log_prices = np.log(prices)
    geom_index = np.exp(log_prices.mean(axis=0))
    # Momentum over the lookback period
    mom = geom_index[-1] / geom_index[-LOOKBACK - 1] - 1.0
    if abs(mom) < THRESH:
        return [0] * n_inst  # stay flat if momentum is too small

    # Direction of trades: +1 for long, -1 for short
    direction = 1 if mom > 0 else -1
    price_today = prices[:, -1]

    # --- 2) Estimate per-instrument volatility over the recent window ---
    window = prices[:, -VOL_WINDOW - 1 : -1]
    returns = window[:, 1:] / window[:, :-1] - 1.0
    vol = np.std(returns, axis=1, ddof=0) + 1e-8  # avoid zero division

    # --- 3) Size positions inversely to price and volatility ---
    raw_shares = TARGET_DOLLAR / (price_today * vol)
    shares = np.floor(raw_shares).astype(int)

    # Enforce the $10k per-stock notional limit
    dollar_position = shares * price_today
    over_limit = dollar_position > 10000.0
    shares[over_limit] = np.floor(10000.0 / price_today[over_limit]).astype(int)

    # Ensure at least one share in any non-zero position
    shares[shares < 1] = 1

    # --- 4) Apply the market direction ---
    positions = (direction * shares).tolist()
    return positions
