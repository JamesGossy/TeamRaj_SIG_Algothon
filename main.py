"""Index momentum strategy with volatility-scaled sizing."""
import numpy as np


LOOKBACK      = 10
THRESH        = 0.002
TARGET_DOLLAR = 1500
VOL_WINDOW    = LOOKBACK  # you could also use a longer vol window


def getMyPosition(price_history: np.ndarray) -> list[int]:
    prices = np.asarray(price_history, dtype=float)
    if prices.shape[0] != 50:
        prices = prices.T
    n_inst, n_days = prices.shape


    # need at least LOOKBACK+1 days of data
    if n_days <= max(LOOKBACK, VOL_WINDOW):
        return [0] * n_inst


    # 1) compute index momentum
    index = prices.mean(axis=0)
    mom = index[-1] / index[-LOOKBACK-1] - 1.0
    if abs(mom) < THRESH:
        return [0] * n_inst


    direction = 1 if mom > 0 else -1
    price_today = prices[:, -1]


    # 2) compute each instrument's realized vol over VOL_WINDOW days
    window = prices[:, -VOL_WINDOW-1 : -1]  # shape (50, VOL_WINDOW)
    rets   = window[:, 1:] / window[:, :-1] - 1
    vol     = np.std(rets, axis=1, ddof=0) + 1e-8


    # 3) size = TARGET_DOLLAR / (price * vol)
    raw_shares = TARGET_DOLLAR / (price_today * vol)
    shares     = np.floor(raw_shares).astype(int)
    dollar_position = shares * price_today
    shares[dollar_position > 10000] = np.floor(10000 / price_today[dollar_position > 10000]).astype(int)
    # enforce at least 1 share for non-zero positions
    shares[shares < 1] = 1


    # 4) apply direction
    positions = (direction * shares).tolist()
    return positions
