import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import statsmodels.api as sm

# ─── Dataset paths (relative filenames) ─────────────────────────────────────────
datasets = {
    "2022": ["2022_prices1.txt", "2022_prices2.txt"],
    "2023": "2023_prices.txt",
    "2024": "2024_prices.txt",
    "2025": "prices.txt",
}

# ─── Part 1: Scaled Mean Series for 2022–2025 ────────────────────────────────────
scaled_series = {}

# 2022: average the two halves first
series_list = []
for path in datasets["2022"]:
    data = np.loadtxt(path)
    data = data.reshape(1, -1) if data.ndim == 1 else data
    mean_by_day = data.mean(axis=0) if data.shape[0] == 50 else data.mean(axis=1)
    series_list.append(mean_by_day)
min_len = min(len(s) for s in series_list)
avg_2022 = sum(s[:min_len] for s in series_list) / len(series_list)
mn, mx = avg_2022.min(), avg_2022.max()
scaled_series["2022"] = 1 + (avg_2022 - mn) * 99 / (mx - mn)

# 2023–2025 individually
for year in ["2023", "2024", "2025"]:
    data = np.loadtxt(datasets[year])
    data = data.reshape(1, -1) if data.ndim == 1 else data
    mean_by_day = data.mean(axis=0) if data.shape[0] == 50 else data.mean(axis=1)
    mn, mx = mean_by_day.min(), mean_by_day.max()
    scaled_series[year] = 1 + (mean_by_day - mn) * 99 / (mx - mn)

# Plot scaled series
plt.figure(figsize=(12, 6))
for name, series in scaled_series.items():
    plt.plot(series, label=name)
plt.xlabel("Day Index")
plt.ylabel("Scaled Mean Price (1–100)")
plt.title("Daily Mean Instrument Price (Scaled 1–100) for 2022–2025")
plt.legend()
plt.grid(True, linestyle="--", linewidth=0.5, alpha=0.3)
plt.tight_layout()
plt.show()


# ─── Part 2: ARIMA Forecast for 2025 Daily Mean ─────────────────────────────────
# Load 2025 data
arr = np.loadtxt(datasets["2025"])
if arr.shape[0] == 50:
    arr = arr.T  # ensure rows=days, cols=instruments

# Compute daily mean
daily_mean = pd.Series(arr.mean(axis=1), name='MeanPrice')

# Fit ARIMA(1,1,1)
model = sm.tsa.ARIMA(daily_mean, order=(1,1,1))
fit = model.fit()

# Forecast next 250 days with 95% CI
steps = 250
fc = fit.get_forecast(steps=steps)
mean_fc = fc.predicted_mean
ci = fc.conf_int(alpha=0.05)
lower = ci.iloc[:,0].astype(float).values
upper = ci.iloc[:,1].astype(float).values
idx_fc = np.arange(len(daily_mean), len(daily_mean) + steps)

# Plot historical + forecast + CI
plt.figure(figsize=(12, 6))
plt.plot(daily_mean.index, daily_mean, label='Historical', color='black')
plt.plot(idx_fc, mean_fc, label='Forecast', color='blue', linestyle='--')
plt.fill_between(idx_fc, lower, upper, color='blue', alpha=0.2, label='95% CI')
plt.xlabel("Day Index")
plt.ylabel("Daily Mean Price")
plt.title("ARIMA(1,1,1) Forecast of 2025 Daily Mean Price")
plt.legend()
plt.grid(True, linestyle="--", linewidth=0.5)
plt.tight_layout()
plt.show()
