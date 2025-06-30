#!/usr/bin/env python3
import numpy as np

# --- parameters ---
LOOKBACK      = 10     # days in momentum / vol window
THRESH        = 0.002  # index-momentum entry filter
TARGET_DOLLAR = 1_500  # risk capital per leg
POSITION_CAP  = 10_000 # max $ exposure per stock

def getMyPosition(price_history: np.ndarray) -> list[int]:
    # shape safeguard (50 × T)
    prices = np.asarray(price_history, float)
    if prices.shape[0] != 50:
        prices = prices.T
    n_inst, n_days = prices.shape

    # need enough history
    if n_days <= LOOKBACK:
        return [0] * n_inst

    # index momentum signal
    idx = prices.mean(axis=0)
    mom = idx[-1] / idx[-LOOKBACK-1] - 1
    if abs(mom) < THRESH:
        return [0] * n_inst
    direction = 1 if mom > 0 else -1

    # per-stock realised vol
    rets = prices[:, -LOOKBACK-1:-1][:, 1:] / prices[:, -LOOKBACK-1:-1][:, :-1] - 1
    vol  = np.std(rets, axis=1) + 1e-8

    # position sizing
    price_today = prices[:, -1]
    shares = np.floor(TARGET_DOLLAR / (price_today * vol)).astype(int)
    shares[shares < 1] = 1                                 # min 1 share
    shares = np.minimum(shares, np.floor(POSITION_CAP / price_today).astype(int))

    return (direction * shares).tolist()
