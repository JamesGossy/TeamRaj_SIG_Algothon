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
df = df.apply(pd.to_numeric, errors="coerce")

# ───────────────────────────────────────────────────────────────────────
# 2) Calculate Metrics
# ───────────────────────────────────────────────────────────────────────
log_returns = np.log(df / df.shift(1))

if log_returns.dropna(how="all").empty:
    raise ValueError("Log returns are empty. Check your input file format or separators.")

rolling_vol = log_returns.rolling(window=30).std() * np.sqrt(252)

market_returns = log_returns.mean(axis=1).dropna()
market_price = df.mean(axis=1)
market_rebased = market_price / market_price.iloc[0] * 100

# ───────────────────────────────────────────────────────────────────────
# Helpers
# ───────────────────────────────────────────────────────────────────────
def mean_rolling_autocorr(series: pd.Series, max_window: int = 100, lag: int = 1) -> pd.Series:
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
    vals = np.asarray(arr).ravel()
    return vals[np.isfinite(vals)]

def fwd_cum_return(r: pd.Series, k: int) -> pd.Series:
    rr = (1.0 + r).astype(float)
    return rr.shift(-1).rolling(k).apply(np.prod, raw=True) - 1.0

def fit_ar1(series: pd.Series):
    s = series.dropna().astype(float)
    if len(s) < 50:
        return np.nan, np.nan
    y = s.iloc[1:].values
    x = s.iloc[:-1].values
    X = sm.add_constant(x)
    try:
        model = sm.OLS(y, X).fit()
        alpha, phi = model.params[0], model.params[1]
        return phi, alpha
    except Exception:
        return np.nan, np.nan

# ───────────────────────────────────────────────────────────────────────
# 3) Generate Graphs
# ───────────────────────────────────────────────────────────────────────
figures = {}

# 1) Correlation Matrix
fig, ax = plt.subplots(figsize=(10, 8))
corr_matrix = log_returns.corr()
im = ax.imshow(corr_matrix, cmap="coolwarm", interpolation="none", aspect="auto")
fig.colorbar(im, ax=ax, label="Correlation")
ax.set_title(f"Correlation Matrix ({df.shape[1]} Stocks)")
plt.tight_layout()
figures["01_correlation_matrix"] = fig

# 2) Histogram of Log Returns
fig, ax = plt.subplots(figsize=(10, 6))
ax.hist(finite_vals(log_returns.to_numpy()), bins=100, edgecolor="black", alpha=0.7)
ax.set_title("Distribution of Log Returns")
plt.tight_layout()
figures["02_log_return_hist"] = fig

# 3) Histogram of Rolling Volatility
fig, ax = plt.subplots(figsize=(10, 6))
ax.hist(finite_vals(rolling_vol.to_numpy()), bins=100, edgecolor="black", alpha=0.7)
ax.set_title("Distribution of Rolling Volatility (30-Day)")
plt.tight_layout()
figures["03_rolling_vol_hist"] = fig

# 4) Cumulative Returns
fig, ax = plt.subplots(figsize=(12, 6))
rebased_df = df / df.iloc[0] * 100
x_days = np.arange(len(rebased_df))
ax.plot(x_days, rebased_df.values, alpha=0.1)
ax.plot(x_days, rebased_df.mean(axis=1).values, linewidth=2, label="Index")
ax.legend()
ax.set_title("Cumulative Returns (Rebased)")
plt.tight_layout()
figures["04_cumulative_returns"] = fig

# 5) Market ACF
fig, ax = plt.subplots(figsize=(10, 6))
if not market_returns.empty:
    sm.graphics.tsa.plot_acf(market_returns, lags=20, ax=ax)
ax.set_title("ACF of Market Returns")
plt.tight_layout()
figures["05_market_acf"] = fig

# 6) Trend Strength
fig, ax = plt.subplots(figsize=(12, 6))
ma_window = 100
market_ma = market_rebased.rolling(ma_window).mean()
x_days = np.arange(len(market_rebased))
ax.plot(x_days, market_rebased.values)
ax.plot(x_days, market_ma.values)
ax.set_title("Trend Strength (Market vs MA)")
plt.tight_layout()
figures["06_trend_strength_ma"] = fig

# 7) Z-score
fig, ax = plt.subplots(figsize=(12, 6))
z_window = 60
mr = log_returns.mean(axis=1)
z = (mr - mr.rolling(z_window).mean()) / mr.rolling(z_window).std()
x_days = np.arange(len(z))
ax.plot(x_days, z.values)
ax.axhline(0)
ax.axhline(2, linestyle="--")
ax.axhline(-2, linestyle="--")
ax.set_title("Z-score of Market Returns")
plt.tight_layout()
figures["07_market_zscore"] = fig

# 8) Rolling Autocorr vs Window
fig, ax = plt.subplots(figsize=(14, 5))
target = market_returns
target_line = mean_rolling_autocorr(target)
ax.plot(target_line.index, target_line.values)
ax.axhline(0)
ax.set_title("Rolling Autocorrelation vs Window")
plt.tight_layout()
figures["08_autocorr_vs_window"] = fig

# 9) Cross-sectional Avg Vol by Day
fig, ax = plt.subplots(figsize=(10,6))
vol_by_day = rolling_vol.mean(axis=1)
ax.hist(vol_by_day.dropna(), bins=60, edgecolor="black", alpha=0.7)
ax.set_title("Cross-Sectional Avg Rolling Vol (by day)")
plt.tight_layout()
figures["09_cross_sectional_vol_distribution"] = fig

# 10) Avg Vol by Stock
fig, ax = plt.subplots(figsize=(10,6))
vol_by_stock = rolling_vol.mean(axis=0)
ax.hist(vol_by_stock.dropna(), bins=30, edgecolor="black", alpha=0.7)
ax.set_title("Avg Rolling Vol (by stock)")
plt.tight_layout()
figures["10_avg_vol_distribution"] = fig

# 11A) AR(1) Scatter
fig, ax = plt.subplots(figsize=(7, 6))
x = market_returns.iloc[:-1].values
y = market_returns.iloc[1:].values
ax.scatter(x, y, alpha=0.3)
ax.set_title("Next-day vs Same-day Returns")
plt.tight_layout()
figures["11_market_nextday_scatter"] = fig

# 11C) AR(1) phi Distribution
phis = []
for col in log_returns.columns:
    phi, _ = fit_ar1(log_returns[col])
    phis.append(phi)

fig, ax = plt.subplots(figsize=(9, 5))
ax.hist([p for p in phis if np.isfinite(p)], bins=25, edgecolor="black")
ax.set_title("Distribution of AR(1) phi")
plt.tight_layout()
figures["13_ar1_phi_distribution"] = fig

# ───────────────────────────────────────────────────────────────────────
# Save All Plots
# ───────────────────────────────────────────────────────────────────────
OUTPUT_DIR = "plots"
os.makedirs(OUTPUT_DIR, exist_ok=True)

for name, fig in figures.items():
    fig.savefig(os.path.join(OUTPUT_DIR, f"{name}.png"), dpi=200, bbox_inches="tight")

plt.show()
