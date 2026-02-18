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

# Per-stock rolling vol (for cross-sectional views) – now 100-day
ROLL_WINDOW = 100
rolling_vol = log_returns.rolling(window=ROLL_WINDOW).std() * np.sqrt(252)

# Market proxy: equal-weight index
market_returns = log_returns.mean(axis=1).dropna()
market_price = df.mean(axis=1)
market_rebased = market_price / market_price.iloc[0] * 100

# Market rolling volatility (time-series regime measure) – now 100-day
market_rolling_vol = market_returns.rolling(ROLL_WINDOW).std() * np.sqrt(252)

# ───────────────────────────────────────────────────────────────────────
# Helpers
# ───────────────────────────────────────────────────────────────────────
def mean_rolling_autocorr(series: pd.Series, max_window: int = 100, lag: int = 1) -> pd.Series:
    """For a range of window sizes, compute the mean lag-k autocorr over the series."""
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

def rolling_autocorr_ts(series: pd.Series, window: int, lag: int = 1) -> pd.Series:
    """Time-series of rolling lag-k autocorrelation (used for regime detection)."""
    s = series.dropna().astype(float)
    x = s
    y = s.shift(lag)
    return x.rolling(window).corr(y)

def finite_vals(arr: np.ndarray) -> np.ndarray:
    vals = np.asarray(arr).ravel()
    return vals[np.isfinite(vals)]

def fwd_cum_return(r: pd.Series, k: int) -> pd.Series:
    """k-day forward cumulative return of a daily return series."""
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

def per_stock_autocorr(df_returns: pd.DataFrame, lag: int) -> pd.Series:
    """Per-stock autocorrelation of returns at a given lag."""
    acf = df_returns.apply(lambda s: s.dropna().autocorr(lag=lag))
    acf = acf.replace([np.inf, -np.inf], np.nan).dropna()
    return acf

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
ax.set_xlabel("Stock index")
ax.set_ylabel("Stock index")
plt.tight_layout()
figures["01_correlation_matrix"] = fig

# 2) Histogram of Log Returns
fig, ax = plt.subplots(figsize=(10, 6))
ax.hist(finite_vals(log_returns.to_numpy()), bins=100, edgecolor="black", alpha=0.7)
ax.set_title("Distribution of Log Returns")
ax.set_xlabel("Log return")
ax.set_ylabel("Frequency")
plt.tight_layout()
figures["02_log_return_hist"] = fig

# 3) Histogram of Rolling Volatility (per-stock) – 100D
fig, ax = plt.subplots(figsize=(10, 6))
ax.hist(finite_vals(rolling_vol.to_numpy()), bins=100, edgecolor="black", alpha=0.7)
ax.set_title("Distribution of Rolling Volatility (100-Day)")
ax.set_xlabel("100D annualised volatility")
ax.set_ylabel("Frequency")
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
ax.set_xlabel("Day")
ax.set_ylabel("Rebased price (index = 100)")
plt.tight_layout()
figures["04_cumulative_returns"] = fig

# 5) Market ACF
fig, ax = plt.subplots(figsize=(10, 6))
if not market_returns.empty:
    sm.graphics.tsa.plot_acf(market_returns, lags=20, ax=ax)
ax.set_title("ACF of Market Returns")
ax.set_xlabel("Lag")
ax.set_ylabel("Autocorrelation")
plt.tight_layout()
figures["05_market_acf"] = fig

# 6) Trend Strength (Market vs MA)
fig, ax = plt.subplots(figsize=(12, 6))
ma_window = 100
market_ma = market_rebased.rolling(ma_window).mean()
x_days = np.arange(len(market_rebased))
ax.plot(x_days, market_rebased.values, label="Market (rebased)")
ax.plot(x_days, market_ma.values, label=f"MA-{ma_window}")
ax.legend()
ax.set_title("Trend Strength (Market vs MA)")
ax.set_xlabel("Day")
ax.set_ylabel("Rebased price (index = 100)")
plt.tight_layout()
figures["06_trend_strength_ma"] = fig

# 7) Z-score of Market Returns
fig, ax = plt.subplots(figsize=(12, 6))
z_window = 60
mr = log_returns.mean(axis=1)
z = (mr - mr.rolling(z_window).mean()) / mr.rolling(z_window).std()
x_days = np.arange(len(z))
ax.plot(x_days, z.values)
ax.axhline(0, color="black", linewidth=1)
ax.axhline(2, linestyle="--", color="grey")
ax.axhline(-2, linestyle="--", color="grey")
ax.set_title("Z-score of Market Returns")
ax.set_xlabel("Day")
ax.set_ylabel("Z-score")
plt.tight_layout()
figures["07_market_zscore"] = fig

# 8) Cross-sectional Avg Vol by Day – from 100D vol
fig, ax = plt.subplots(figsize=(10, 6))
vol_by_day = rolling_vol.mean(axis=1)
ax.hist(vol_by_day.dropna(), bins=60, edgecolor="black", alpha=0.7)
ax.set_title("Cross-Sectional Avg Rolling Vol (by day)")
ax.set_xlabel("100D annualised volatility (cross-sectional mean)")
ax.set_ylabel("Frequency")
plt.tight_layout()
figures["09_cross_sectional_vol_distribution"] = fig

# 9) Avg Vol by Stock – from 100D vol
fig, ax = plt.subplots(figsize=(10, 6))
vol_by_stock = rolling_vol.mean(axis=0)
ax.hist(vol_by_stock.dropna(), bins=30, edgecolor="black", alpha=0.7)
ax.set_title("Avg Rolling Vol (by stock)")
ax.set_xlabel("Average 100D annualised volatility")
ax.set_ylabel("Frequency")
plt.tight_layout()
figures["10_avg_vol_distribution"] = fig

# 10) AR(1) Scatter (market continuation vs reversal)
fig, ax = plt.subplots(figsize=(7, 6))
x = market_returns.iloc[:-1].values
y = market_returns.iloc[1:].values
ax.scatter(x, y, alpha=0.3)
ax.set_xlabel("Return_t")
ax.set_ylabel("Return_{t+1}")
ax.set_title("Next-day vs Same-day Returns (Market)")
plt.tight_layout()
figures["11_market_nextday_scatter"] = fig

# ───────────────────────────────────────────────────────────────────────
# Volatility & Regime Plots
# ───────────────────────────────────────────────────────────────────────

# Regime thresholds for volatility – based on 100D market_rolling_vol
vol_low, vol_high = np.nanpercentile(market_rolling_vol.dropna(), [20, 80])

# 11) Market Rolling Volatility with Regime Bands – 100D
fig, ax = plt.subplots(figsize=(12, 6))
t_idx = np.arange(len(market_rolling_vol))
ax.plot(t_idx, market_rolling_vol.values, label="100D rolling vol")
ax.axhline(vol_low, linestyle="--", color="green", label="Low-vol threshold (20th pct)")
ax.axhline(vol_high, linestyle="--", color="red", label="High-vol threshold (80th pct)")
ax.set_title("Market Rolling Volatility (100D) & Regime Thresholds")
ax.set_xlabel("Day")
ax.set_ylabel("Annualised volatility")
ax.legend()
plt.tight_layout()
figures["15_market_rolling_vol_regimes"] = fig

# 12) Rolling Autocorrelation for separate lags (1, 2, 5, 10) — MARKET
acf_window = 100
lags = [1, 2, 5, 10]
acf_sig = 2.0 / np.sqrt(acf_window)  # rough significance band

for lag in lags:
    roll_acf_k = rolling_autocorr_ts(market_returns, window=acf_window, lag=lag)

    fig, ax = plt.subplots(figsize=(12, 6))
    x_days = np.arange(len(roll_acf_k))
    ax.plot(x_days, roll_acf_k.values, label=f"Lag {lag}")
    ax.axhline(0.0, color="black", linewidth=1)

    ax.axhline(acf_sig, linestyle="--", color="red", label="Momentum threshold")
    ax.axhline(-acf_sig, linestyle="--", color="green", label="Mean-reversion threshold")

    ax.set_title(f"Rolling Autocorrelation of Market Returns (lag={lag}, window={acf_window})")
    ax.set_xlabel("Day")
    ax.set_ylabel("Autocorrelation")
    ax.legend()
    plt.tight_layout()
    figures[f"16_market_rolling_acf_lag{lag}"] = fig

# 13) Distribution of AR(1) phi (single-name behaviour)
phis = []
for col in log_returns.columns:
    phi, _ = fit_ar1(log_returns[col])
    phis.append(phi)

fig, ax = plt.subplots(figsize=(9, 5))
ax.hist([p for p in phis if np.isfinite(p)], bins=25, edgecolor="black")
ax.set_title("Distribution of AR(1) phi")
ax.set_xlabel("AR(1) phi")
ax.set_ylabel("Frequency")
plt.tight_layout()
figures["13_ar1_phi_distribution"] = fig

# ───────────────────────────────────────────────────────────────────────
# ADDITIONAL PLOTS (KEEPING 19 + REWORKING 20, REMOVING 17 + 18)
# ───────────────────────────────────────────────────────────────────────

# C) Rolling 100D volatility over time for top-2 most volatile and top-2 least volatile
#    (based on avg 100D rolling vol)
vol_by_stock = rolling_vol.mean(axis=0).replace([np.inf, -np.inf], np.nan).dropna()
most_vol_stocks = vol_by_stock.nlargest(2).index.tolist()
least_vol_stocks = vol_by_stock.nsmallest(2).index.tolist()

sel_vol = most_vol_stocks + least_vol_stocks
if len(sel_vol) > 0:
    fig, ax = plt.subplots(figsize=(12, 6))
    x_days = np.arange(len(rolling_vol))
    for col in sel_vol:
        ax.plot(x_days, rolling_vol[col].values, label=col)
    ax.set_title("Rolling 100D Volatility Over Time — Top 2 Most vs Top 2 Least Volatile Stocks")
    ax.set_xlabel("Day")
    ax.set_ylabel("Annualised volatility (100D rolling)")
    ax.legend()
    plt.tight_layout()
    figures["19_rolling_volatility_extremes_timeseries"] = fig

# D) Rolling 100D ACF over time for lag 1,2,5,10
#    Split into TWO plots per lag: (Top-2 Highest ACF) and (Bottom-2 Lowest ACF)
for lag in [1, 2, 5, 10]:
    acf = per_stock_autocorr(log_returns, lag=lag)
    if acf.empty:
        continue

    top2_names = acf.nlargest(2).index.tolist()
    bot2_names = acf.nsmallest(2).index.tolist()

    # --- Top 2 plot
    fig, ax = plt.subplots(figsize=(12, 6))
    for col in top2_names:
        roll_acf = rolling_autocorr_ts(log_returns[col], window=acf_window, lag=lag)
        ax.plot(np.arange(len(roll_acf)), roll_acf.values, label=col)
    ax.axhline(0.0, color="black", linewidth=1)
    ax.axhline(acf_sig, linestyle="--", color="red", label="Momentum threshold")
    ax.axhline(-acf_sig, linestyle="--", color="green", label="Mean-reversion threshold")
    ax.set_title(f"Rolling {acf_window}D Autocorrelation — Lag {lag}\nTop 2 Highest ACF Stocks")
    ax.set_xlabel("Day")
    ax.set_ylabel("Rolling autocorrelation (log returns)")
    ax.legend()
    plt.tight_layout()
    figures[f"20A_stock_rolling_acf_lag{lag}_top2"] = fig

    # --- Bottom 2 plot
    fig, ax = plt.subplots(figsize=(12, 6))
    for col in bot2_names:
        roll_acf = rolling_autocorr_ts(log_returns[col], window=acf_window, lag=lag)
        ax.plot(np.arange(len(roll_acf)), roll_acf.values, label=col)
    ax.axhline(0.0, color="black", linewidth=1)
    ax.axhline(acf_sig, linestyle="--", color="red", label="Momentum threshold")
    ax.axhline(-acf_sig, linestyle="--", color="green", label="Mean-reversion threshold")
    ax.set_title(f"Rolling {acf_window}D Autocorrelation — Lag {lag}\nBottom 2 Lowest ACF Stocks")
    ax.set_xlabel("Day")
    ax.set_ylabel("Rolling autocorrelation (log returns)")
    ax.legend()
    plt.tight_layout()
    figures[f"20B_stock_rolling_acf_lag{lag}_bottom2"] = fig


# ───────────────────────────────────────────────────────────────────────
# Lead-Lag Hypothesis Testing
# ───────────────────────────────────────────────────────────────────────
max_lag = 5
lead_lag_results = []

# Calculate correlation between Market(t) and Stock_i(t + lag)
for col in log_returns.columns:
    stock_series = log_returns[col]
    for lag in range(-max_lag, max_lag + 1):
        # positive lag means market leads stock
        corr = market_returns.corr(stock_series.shift(-lag))
        lead_lag_results.append({'Stock': col, 'Lag': lag, 'Correlation': corr})

lead_lag_df = pd.DataFrame(lead_lag_results)

# Pivot for heatmap: Rows = Lags, Columns = Stocks
lead_lag_pivot = lead_lag_df.pivot(index='Lag', columns='Stock', values='Correlation')

fig, ax = plt.subplots(figsize=(14, 6))
im = ax.imshow(lead_lag_pivot, cmap="RdYlGn", aspect='auto', origin='lower',
               extent=[0, len(df.columns), -max_lag, max_lag])

fig.colorbar(im, label="Correlation with Market")
ax.set_yticks(range(-max_lag, max_lag + 1))
ax.axhline(0, color='black', linewidth=2, linestyle='-') # Contemporaneous line
ax.set_title("Lead-Lag Heatmap: Market(t) vs Stock(t + Lag)\nPositive Lag = Market Leads Stock")
ax.set_ylabel("Lag (Days)")
ax.set_xlabel("Stock Index")

# Add a summary line plot of the average cross-correlation across all stocks
fig2, ax2 = plt.subplots(figsize=(10, 6))
avg_lead_lag = lead_lag_pivot.mean(axis=1)
ax2.plot(avg_lead_lag.index, avg_lead_lag.values, marker='o', linewidth=2)
ax2.axhline(0, color='black', alpha=0.3)
ax2.axvline(0, color='red', linestyle='--', label='Contemporaneous')
ax2.set_title("Average Cross-Correlation: Market vs. Universe")
ax2.set_xlabel("Lag (Days: Positive = Market Leads)")
ax2.set_ylabel("Average Correlation")
ax2.legend()
ax2.grid(True, alpha=0.3)

figures["21_lead_lag_heatmap"] = fig
figures["22_avg_lead_lag_profile"] = fig2

# ───────────────────────────────────────────────────────────────────────
# Save All Plots
# ───────────────────────────────────────────────────────────────────────
OUTPUT_DIR = "plots"
os.makedirs(OUTPUT_DIR, exist_ok=True)

for name, fig in figures.items():
    fig.savefig(os.path.join(OUTPUT_DIR, f"{name}.png"), dpi=200, bbox_inches="tight")

# plt.show()
