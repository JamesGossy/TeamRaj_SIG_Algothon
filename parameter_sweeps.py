import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from tqdm import tqdm  # Install via: pip install tqdm

# --- Strategy Logic (Modified to accept params) ---
def getMyPosition_Parametric(price_history, lookback, thresh):
    TARGET_DOLLAR = 1500
    VOL_WINDOW = lookback
    
    prices = np.asarray(price_history, dtype=float)
    if prices.shape[0] != 50:
        prices = prices.T
    n_inst, n_days = prices.shape

    if n_days <= max(lookback, VOL_WINDOW):
        return [0] * n_inst

    # 1) compute index momentum
    index = prices.mean(axis=0)
    mom = index[-1] / index[-lookback-1] - 1.0
    if abs(mom) < thresh:
        return [0] * n_inst

    direction = 1 if mom > 0 else -1
    price_today = prices[:, -1]

    # 2) compute vol
    window = prices[:, -VOL_WINDOW-1 : -1]
    rets = window[:, 1:] / window[:, :-1] - 1
    vol = np.std(rets, axis=1, ddof=0) + 1e-8

    # 3) sizing
    raw_shares = TARGET_DOLLAR / (price_today * vol)
    shares = np.floor(raw_shares).astype(int)
    
    # Position limit logic
    dollar_position = shares * price_today
    shares[dollar_position > 10000] = np.floor(10000 / price_today[dollar_position > 10000]).astype(int)
    shares[shares < 1] = 1

    return (direction * shares).tolist()

# --- Backtester ---
def run_backtest(prcHist, numTestDays, lookback, thresh, comm_rate=0.0005, dollar_pos_limit=10000.0):
    nInst, nt_total = prcHist.shape
    cash = 0.0
    curPos = np.zeros(nInst)
    value = 0.0
    dailyPL = []
    startDay = nt_total - numTestDays + 1

    for t in range(startDay, nt_total + 1):
        hist = prcHist[:, :t]
        price = hist[:, -1]

        if t < nt_total:
            rawPos = getMyPosition_Parametric(hist, lookback, thresh)
            pos_limit = np.floor(dollar_pos_limit / price).astype(int)
            newPos = np.clip(rawPos, -pos_limit, pos_limit)

            delta = newPos - curPos
            traded = np.abs(delta) * price
            cash -= price.dot(delta) + comm_rate * traded.sum()
            curPos = newPos.copy()

        posValue = curPos.dot(price)
        todayPL = cash + posValue - value
        value = cash + posValue
        if t > startDay:
            dailyPL.append(todayPL)

    pll = np.array(dailyPL)
    mu = pll.mean()
    sigma = pll.std(ddof=0)
    score = mu - 0.1 * sigma
    return score

# --- Main Sweep Execution ---
if __name__ == "__main__":
    # Load Data
    prices_file = "price_files/2025_prices.txt"
    df = pd.read_csv(prices_file, sep=r'\s+', header=None)
    prcAll = df.values.T 
    
    # Define Sweep Ranges
    lookback_range = [2,3,4,5,6,7,8,9,10,11,12,13,14,15]
    thresh_range = [0, 0.0001,0.0002,0.0003 ,0.0004,0.0005, 0.001, 0.0015, 0.002, 0.0025, 0.003, 0.0035, 0.004]
    test_days = 1000 # Reduced for speed during sweep
    
    results = np.zeros((len(lookback_range), len(thresh_range)))

    print("Starting Parameter Sweep...")
    for i, lb in enumerate(tqdm(lookback_range)):
        for j, th in enumerate(thresh_range):
            results[i, j] = run_backtest(prcAll, test_days, lb, th)

    # Convert to DataFrame for Plotting
    res_df = pd.DataFrame(results, index=lookback_range, columns=thresh_range)

    # --- Plot Heatmap ---
    plt.figure(figsize=(10, 8))
    sns.heatmap(res_df, annot=True, fmt=".2f", cmap="RdYlGn", cbar_kws={'label': 'Score'})
    plt.title(f"Parameter Sweep: Lookback vs Threshold (Last {test_days} Days)")
    plt.xlabel("Momentum Threshold")
    plt.ylabel("Lookback Window (Days)")
    
    plt.savefig("plots/parameter_heatmap.png")
    plt.show()