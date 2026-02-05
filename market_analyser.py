import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import statsmodels.api as sm

# ───────────────────────────────────────────────────────────────────────
# 1) Load Data Robustly
# ───────────────────────────────────────────────────────────────────────
DATA_PATH = "price_files/2025_prices.txt"

df = pd.read_csv(DATA_PATH, sep=r"\s+", header=None)
df.index = pd.date_range("2023-01-01", periods=len(df), freq="B")
df.columns = [f"Stock_{i+1}" for i in range(df.shape[1])]

# Ensure numeric
df = df.apply(pd.to_numeric, errors="coerce")

# ───────────────────────────────────────────────────────────────────────
# 2) Calculate Metrics
# ───────────────────────────────────────────────────────────────────────
log_returns = np.log(df / df.shift(1))

if log_returns.dropna(how="all").empty:
    raise ValueError("Log returns are empty. Check your input file format or separators.")

# Rolling Volatility (30-day, Annualized)
rolling_vol = log_returns.rolling(window=30).std() * np.sqrt(252)

# Market proxies
market_returns = log_returns.mean(axis=1).dropna()
market_price = df.mean(axis=1)  # equal-weight "index" level proxy
market_rebased = market_price / market_price.iloc[0] * 100

# ───────────────────────────────────────────────────────────────────────
# Helpers
# ───────────────────────────────────────────────────────────────────────
def mean_rolling_autocorr(series: pd.Series, max_window: int = 100, lag: int = 1) -> pd.Series:
    """
    For each window w in [lag+2 .. max_window], compute rolling autocorr at given lag,
    then take the mean over time (ignoring NaNs). Returns a Series indexed by window size.
    """
    s = series.dropna().astype(float)
    x = s
    y = s.shift(lag)

    out = {}
    for w in range(lag + 2, max_window + 1):
        cov = x.rolling(w).cov(y)
        stdx = x.rolling(w).std()
        stdy = y.rolling(w).std()
        ac = cov / (stdx * stdy)
        out[w] = ac.mean()

    return pd.Series(out)


def finite_vals(arr: np.ndarray) -> np.ndarray:
    """Flatten and filter finite values from an array."""
    vals = np.asarray(arr).ravel()
    return vals[np.isfinite(vals)]


# ───────────────────────────────────────────────────────────────────────
# 3) Generate Graphs (each in its own figure)
# ───────────────────────────────────────────────────────────────────────
figures = {}  # name -> figure (for optional saving)

# 1) Correlation Matrix
fig, ax = plt.subplots(figsize=(10, 8))
corr_matrix = log_returns.corr()
im = ax.imshow(corr_matrix, cmap="coolwarm", interpolation="none", aspect="auto")
fig.colorbar(im, ax=ax, label="Correlation")
ax.set_title(f"Correlation Matrix ({df.shape[1]} Stocks)")
ax.set_xlabel("Stock (column index)")
ax.set_ylabel("Stock (column index)")
plt.tight_layout()
figures["01_correlation_matrix"] = fig

# 2) Histogram of Log Returns
fig, ax = plt.subplots(figsize=(10, 6))
vals = finite_vals(log_returns.to_numpy())
ax.hist(vals, bins=100, color="skyblue", edgecolor="black", alpha=0.7)
ax.set_title("Distribution of Log Returns")
ax.set_xlabel("Daily Log Return")
ax.set_ylabel("Frequency")
plt.tight_layout()
figures["02_log_return_hist"] = fig

# 3) Histogram of Rolling Volatility
fig, ax = plt.subplots(figsize=(10, 6))
vvals = finite_vals(rolling_vol.to_numpy())
ax.hist(vvals, bins=100, color="orange", edgecolor="black", alpha=0.7)
ax.set_title("Distribution of Rolling Volatility (30-Day)")
ax.set_xlabel("Annualized Volatility")
ax.set_ylabel("Frequency")
plt.tight_layout()
figures["03_rolling_vol_hist"] = fig

# 4) Cumulative Returns (Rebased to 100) — Day number on x-axis
fig, ax = plt.subplots(figsize=(12, 6))
rebased_df = df / df.iloc[0] * 100
x_days = np.arange(len(rebased_df))
ax.plot(x_days, rebased_df.values, alpha=0.1, color="gray")
ax.plot(x_days, rebased_df.mean(axis=1).values, color="red", linewidth=2, label="Index (equal-weight)")
ax.set_title("Cumulative Returns (Rebased to 100)")
ax.set_xlabel("Day")
ax.set_ylabel("Rebased Price Level")
ax.legend(loc="upper left")
plt.tight_layout()
figures["04_cumulative_returns"] = fig

# 5) Autocorrelation (ACF) of the "Market"
fig, ax = plt.subplots(figsize=(10, 6))
if not market_returns.empty:
    sm.graphics.tsa.plot_acf(market_returns.dropna(), lags=20, ax=ax)
    ax.set_title("ACF of Market Returns")
    ax.set_xlabel("Lag (days)")
    ax.set_ylabel("Autocorrelation")
else:
    ax.text(0.5, 0.5, "Insufficient Data for ACF", ha="center", va="center")
    ax.set_title("ACF of Market Returns")
    ax.set_xlabel("Lag (days)")
    ax.set_ylabel("Autocorrelation")
    ax.axis("off")
plt.tight_layout()
figures["05_market_acf"] = fig

# 6) Trend Strength Filter (Market vs MA) — Day number on x-axis
fig, ax = plt.subplots(figsize=(12, 6))
ma_window = 100
market_ma = market_rebased.rolling(ma_window).mean()
x_days = np.arange(len(market_rebased))
ax.plot(x_days, market_rebased.values, label="Market (rebased)")
ax.plot(x_days, market_ma.values, label=f"MA({ma_window})")
ax.set_title("Trend Strength Filter (Market vs Moving Average)")
ax.set_xlabel("Day")
ax.set_ylabel("Rebased Level")
ax.legend(loc="upper left")
plt.tight_layout()
figures["06_trend_strength_ma"] = fig

# 7) Z-score of Market Returns — Day number on x-axis + distinct horizontal line colors
fig, ax = plt.subplots(figsize=(12, 6))
z_window = 60
mr = log_returns.mean(axis=1)
z = (mr - mr.rolling(z_window).mean()) / mr.rolling(z_window).std()
x_days = np.arange(len(z))

ax.plot(x_days, z.values, label="Rolling Z-score")
ax.axhline(0, linewidth=1, color="black", label="0")
ax.axhline(2, linestyle="--", linewidth=1, color="dimgray", label="+2 / -2")
ax.axhline(-2, linestyle="--", linewidth=1, color="dimgray")

ax.set_title(f"Z-score of Market Returns (rolling {z_window}d)")
ax.set_xlabel("Day")
ax.set_ylabel("Z-score")
ax.legend(loc="upper left")
plt.tight_layout()
figures["07_market_zscore"] = fig

# 8) Rolling autocorrelation vs window, compared to random baselines
fig, ax = plt.subplots(figsize=(14, 5))

target = market_returns.dropna()
target_name = "MARKET"
max_window = 100
lag = 1

n_random = 150
rand_alpha = 0.18
rand_lw = 1.2

rng = np.random.default_rng(42)

target_line = mean_rolling_autocorr(target, max_window=max_window, lag=lag)

sigma = target.std(ddof=0)
N = len(target)

for _ in range(n_random):
    rs = pd.Series(rng.normal(0, sigma, size=N), index=target.index)
    rand_line = mean_rolling_autocorr(rs, max_window=max_window, lag=lag)
    ax.plot(rand_line.index, rand_line.values, color="black", alpha=rand_alpha, linewidth=rand_lw)

ax.plot(target_line.index, target_line.values, color="red", linewidth=2.5, label=target_name)
ax.axhline(0, linewidth=1)

ax.set_title(f"Rolling Autocorrelation vs Window (lag={lag}) — Random Baselines vs {target_name}")
ax.set_xlabel("Rolling Window Size (days)")
ax.set_ylabel("Mean Lag-1 Autocorrelation")
ax.legend(loc="best")
plt.tight_layout()
figures["08_autocorr_vs_window"] = fig

# 9) Is there volatility regimes? 
vol_by_day = rolling_vol.mean(axis=1)  # cross-sectional average vol each day
plt.figure(figsize=(10,6))
plt.hist(vol_by_day.dropna(), bins=60, edgecolor="black", alpha=0.7)
plt.title("Distribution of Cross-Sectional Avg Rolling Vol (by day)")
plt.xlabel("Annualized Volatility")
plt.ylabel("Frequency")

# 10) Do different stocks have different volatilties?
vol_by_stock = rolling_vol.mean(axis=0)  # average vol per stock
plt.figure(figsize=(10,6))
plt.hist(vol_by_stock.dropna(), bins=30, edgecolor="black", alpha=0.7)
plt.title("Distribution of Avg Rolling Vol (by stock)")
plt.xlabel("Annualized Volatility")
plt.ylabel("Count of stocks")
plt.show()


# ───────────────────────────────────────────────────────────────────────
# OPTIONAL: Save all figures to a folder (uncomment to enable)
# ───────────────────────────────────────────────────────────────────────
# OUTPUT_DIR = "analysis_plots"
# os.makedirs(OUTPUT_DIR, exist_ok=True)
# for name, fig in figures.items():
#     fig.savefig(os.path.join(OUTPUT_DIR, f"{name}.png"), dpi=200, bbox_inches="tight")

# ───────────────────────────────────────────────────────────────────────
# Show all figures
# ───────────────────────────────────────────────────────────────────────
plt.show()
