# main.py
# Enhanced ML-driven strategy with expanded features and z-score-driven picks
# Features: SMA gap, multi-horizon momentum, multi-window volatility, vol skew
# Uses rolling Ridge regression and strict z-score thresholds for robust selections

import numpy as np

# Strategy parameters
WINDOW_SMA       = 13         # SMA window for gap
MOM_WINDOWS      = [5, 10, 20]  # momentum lookbacks
VOL_WINDOWS      = [5, 20]     # volatility lookbacks
TRAIN_WINDOW     = 126        # shorter training window for recency
REBALANCE_DAYS   = 5          # days between rebalances
NUM_PICKS        = 8          # picks per side before thresholding
ZS_THRESHOLD     = 1.5        # z-score threshold for predicted returns
RISK_PER_SIDE    = 5000       # total risk dollars per side
MAX_LEG_DOLLARS  = 10000      # cap per leg in dollars
ALPHA            = 0.1        # Ridge regularization
EPS              = 1e-8

# State
_last_reb = -REBALANCE_DAYS
_positions = None


def getMyPosition(price_history):
    global _last_reb, _positions

    prices = np.array(price_history, float)
    if prices.shape[0] != 50:
        prices = prices.T
    n, t = prices.shape
    day = t - 1

    # init
    if _positions is None:
        _positions = np.zeros(n, dtype=int)

    # need history and rebalance check
    if day < max(WINDOW_SMA, max(MOM_WINDOWS), max(VOL_WINDOWS)) + 1:
        return _positions
    if day - _last_reb < REBALANCE_DAYS:
        return _positions
    _last_reb = day

    # rolling training slice
    start = max(0, t - TRAIN_WINDOW - 1)
    hist = prices[:, start:day+1]
    nh = hist.shape[1]
    min_req = max(WINDOW_SMA, max(MOM_WINDOWS), max(VOL_WINDOWS)) + 1
    if nh <= min_req:
        return _positions

    # build feature and target arrays
    X, y = [], []
    for d in range(min_req, nh-1):
        p = hist[:, d]
        # gap
        sma = hist[:, d-WINDOW_SMA+1:d+1].mean(axis=1)
        gap = p / sma - 1.0
        # momenta
        moms = [p / hist[:, d-w] - 1.0 for w in MOM_WINDOWS]
        # vols
        vols = [np.std(hist[:, d-w+1:d+1] / hist[:, d-w:d] - 1.0, axis=1) + EPS for w in VOL_WINDOWS]
        # vol skew
        skew = vols[0] / vols[1]
        # features
        feats = np.vstack([gap] + moms + vols + [skew]).T
        X.append(feats)
        y.append(hist[:, d+1] / p - 1.0)
    X = np.vstack(X)
    y = np.hstack(y)

    # standardize features
    mu = X.mean(axis=0)
    sigma = X.std(axis=0) + EPS
    Xs = (X - mu) / sigma

    # train ridge
    y_mean = y.mean()
    w = np.linalg.solve(Xs.T @ Xs + ALPHA * np.eye(Xs.shape[1]), Xs.T @ (y - y_mean))

    # today's features
    cur = prices[:, day]
    sma_t = prices[:, day-WINDOW_SMA+1:day+1].mean(axis=1)
    gap_t = cur / sma_t - 1.0
    moms_t = [cur / prices[:, day-w] - 1.0 for w in MOM_WINDOWS]
    vols_t = [np.std(prices[:, day-w+1:day+1] / prices[:, day-w:day] - 1.0, axis=1) + EPS for w in VOL_WINDOWS]
    skew_t = vols_t[0] / vols_t[1]
    Xp = np.column_stack([gap_t] + moms_t + vols_t + [skew_t])
    Xp_s = (Xp - mu) / sigma
    y_pred = Xp_s @ w + y_mean

    # cross-sectional z-score of predictions
    z = (y_pred - np.mean(y_pred)) / (np.std(y_pred) + EPS)

    # pick initial candidates by magnitude
    idx = np.argsort(z)
    longs = idx[::-1][:NUM_PICKS]
    shorts = idx[:NUM_PICKS]

    # filter by z-score threshold
    longs = [i for i in longs if z[i] >= ZS_THRESHOLD]
    shorts = [i for i in shorts if z[i] <= -ZS_THRESHOLD]

    # size positions proportional to absolute z
    new_pos = np.zeros(n, dtype=int)
    for side, picks in [(1, longs), (-1, shorts)]:
        if picks:
            vals = np.array([abs(z[i]) for i in picks])
            total = vals.sum() + EPS
            for i, v in zip(picks, vals):
                frac = v / total
                dollar = min(RISK_PER_SIDE * frac * len(picks), MAX_LEG_DOLLARS)
                size = max(1, int(dollar / cur[i]))
                new_pos[i] = side * size

    _positions = new_pos
    return _positions
