import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from main import getMyPosition

# --- Configuration ---
PRICES_PATH = "price_files/2025_prices.txt"
STOCK_IDX = 1
LOOKBACK_DAYS = 200
COMM_RATE = 0.0005

# 1. Load Data
df = pd.read_csv(PRICES_PATH, sep=r"\s+", header=None)
prices_full = df.values.T if df.shape[1] == 50 else df.values
n_days = prices_full.shape[1]

# 2. Generate Positions (Walk-forward)
pos_full = np.zeros(n_days)
for t in range(n_days):
    pos_full[t] = getMyPosition(prices_full[:, :t+1])[STOCK_IDX]

# 3. Slice for Analysis Window
start = n_days - LOOKBACK_DAYS
p = prices_full[STOCK_IDX, start:]
pos = pos_full[start:]

# 4. Compute Returns and PnL
daily_pnl = pos[:-1] * np.diff(p)
trades = np.abs(np.diff(pos)) 
commissions = trades * p[1:] * COMM_RATE
net_pnl = daily_pnl - commissions

# 5. Plotting
# Updated to 3 subplots and adjusted figsize for the extra graph
fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 15), sharex=True)

# Top: Price, Regimes, and Trade Markers
ax1.plot(p, color='black', alpha=0.2, label='Price')

for i in range(1, len(pos)):
    # Background Shading
    color = 'green' if pos[i-1] > 0 else 'red' if pos[i-1] < 0 else None
    if color:
        ax1.axvspan(i-1, i, color=color, alpha=0.05)
    
    # Trade Markers (Arrows and Xs)
    prev, curr = pos[i-1], pos[i]
    if curr > 0 and prev <= 0: # Entry Long
        ax1.scatter(i, p[i], marker='^', color='green', s=100, zorder=5)
    elif curr < 0 and prev >= 0: # Entry Short
        ax1.scatter(i, p[i], marker='v', color='red', s=100, zorder=5)
    elif curr == 0 and prev != 0: # Exit to Flat
        ax1.scatter(i, p[i], marker='x', color='black', s=80, zorder=5)

ax1.set_title(f"Stock {STOCK_IDX} Price & Trade Signals")
ax1.set_ylabel("Price")

# Middle: Cumulative PnL
ax2.plot(np.cumsum(daily_pnl), label="Gross PnL", alpha=0.7)
ax2.plot(np.cumsum(net_pnl), label="Net PnL (inc. Comm)", color='black', lw=1.5)
ax2.axhline(0, color='red', lw=0.5, ls='--')
ax2.legend()
ax2.set_title("Equity Curve")
ax2.set_ylabel("PnL ($)")

# Bottom: Position Amount
# Using step plot to accurately represent discrete position changes
ax3.step(range(len(pos)), pos, where='post', color='blue', lw=1.5)
ax3.axhline(0, color='black', lw=0.8, ls='--')
ax3.set_title("Position Amount")
ax3.set_ylabel("Quantity")
ax3.set_xlabel("Days")
ax3.grid(True, alpha=0.3)

plt.show()

print(f"Total Net PnL: {np.sum(net_pnl):.2f}")