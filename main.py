from typing import List
import numpy as np

"""
Adaptive index trend follower with volatility‑weighted position sizing.

"""

SPAN: int = 6
EMA_THRESHOLD: float = 0.0015
TARGET_DOLLAR: float = 1000.0
VOL_WINDOW: int = 5

def getMyPosition(price_history: np.ndarray) -> List[int]:
    # Validate and orient the price history array
    prices = np.asarray(price_history, dtype=float)
    if prices.ndim != 2:
        raise ValueError("price_history must be a 2D array")
    
    # Ensure shape is (nInst, nDays)
    if prices.shape[0] != 50:
        if prices.shape[1] == 50:
            prices = prices.T
        else:
            raise ValueError("price_history must include 50 instruments")
    n_inst, n_days = prices.shape

    # Require sufficient history to compute EMA and volatility
    min_history = max(SPAN, VOL_WINDOW) + 2
    if n_days < min_history:
        return [0] * n_inst
    
    # Compute geometric mean index and its EMA
    log_prices = np.log(prices)
    geom_index = np.exp(log_prices.mean(axis=0))
    alpha = 2.0 / (SPAN + 1)
    ema = np.empty_like(geom_index)
    ema[0] = geom_index[0]
    for t in range(1, n_days):
        ema[t] = alpha * geom_index[t] + (1.0 - alpha) * ema[t - 1]
    deviation = geom_index[-1] / ema[-1] - 1.0

    # Stay flat if the index is too close to its EMA
    if abs(deviation) < EMA_THRESHOLD:
        return [0] * n_inst
    
    # Direction of trades (+1 for long, -1 for short)
    direction = 1 if deviation > 0 else -1
    price_today = prices[:, -1]

    # Estimate volatility over the last VOL_WINDOW days
    window = prices[:, -VOL_WINDOW - 1 : -1]
    returns = window[:, 1:] / window[:, :-1] - 1.0
    vol = np.std(returns, axis=1, ddof=0) + 1e-8
    
    # Base position sizing (inverse volatility)
    raw_shares = TARGET_DOLLAR / (price_today * vol)
    shares = np.floor(raw_shares).astype(int)

    # Apply dollar position limit of USD 10 000 per instrument
    dollar_position = shares * price_today
    over_limit = dollar_position > 10000.0
    if np.any(over_limit):
        shares[over_limit] = np.floor(10000.0 / price_today[over_limit]).astype(int)

    # Ensure at least one share when taking a non‑zero position
    shares[shares < 1] = 1
    
    # Apply the global direction to all positions.  
    final_positions = direction * shares
    return final_positions.tolist()
