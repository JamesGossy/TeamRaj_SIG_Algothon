# Team RAJ 🚀  
**SIG Algothon 2025 — Strategy, Research, and Insights**

> This repository contains my research notes, analysis plots, and algorithm submission(s) for the SIG Algothon.  
> It is written both as a post-mortem and as a reference for anyone learning systematic trading or competition-style quantitative research.

---

## Introduction

Hi — I’m James, an engineering student at Monash University with a strong interest in quantitative finance.

This report documents:
- how I explored the market data,
- the hypotheses I tested,
- which strategies were viable (and which were not),
- what was implemented in the final algorithm,
- what worked / didn’t work,
- and what I learned from the process.

The emphasis throughout is on **robustness**, **risk awareness**, and **avoiding overfitting**, rather than maximizing in-sample performance.

---

## About the SIG Algothon

**SIG Algothon** is an algorithmic trading competition where participants build bots to trade instruments in a simulated market environment under realistic constraints.

---

## Environment Assumptions

- **Instruments:**  
  50 synthetic instruments in a simulated trading universe, indexed from 0 to 49.

- **Time period & frequency:**  
  Daily price data spanning several years (~1500 observations).  
  On each trading day *t*, the algorithm receives the full price history from day 0 to *t*.  
  Final evaluation is performed on unseen future data from the same universe.

- **Execution model:**  
  Market-style execution at the most recent available price.  
  Trades are executed based on the **difference** between the previous day’s position and the newly requested position.

- **Costs:**  
  Fixed commission of **5 basis points (0.0005)** applied to total dollar volume traded.  
  No explicit bid–ask spread or slippage is modelled beyond this.

- **Constraints:**  
  - Long and short positions are allowed  
  - Maximum position size of **±$10,000 per instrument** at trade time  
  - Temporary breaches due to price movements are allowed but must be corrected the following day  
  - Positions are integer numbers of shares  
  - Positions are automatically clipped by the evaluation engine if limits are exceeded

- **Objective metric:**  

  **Score = mean(P&L) − 0.1 × std(P&L)**  

  where P&L is computed over the evaluation period on unseen data.

---

# 1) Market Analysis

## 1.0 Strategy Feasibility Screening

Before developing specific trading strategies, I first assessed which approaches were compatible with the data resolution, execution model, and constraints of the competition. Several common strategy classes were evaluated and explicitly excluded or de-emphasized.

### Excluded: Market Making
Market making relies on intraday price dynamics, bid–ask spreads, and order book information.  
Given that the dataset consists solely of daily close prices with no microstructure data, market making strategies were deemed infeasible and excluded.

### Excluded: Pure Arbitrage
Classic arbitrage strategies require deterministic pricing relationships, cross-venue discrepancies, or known conversion mechanics.  
Due to the absence of intraday prices, cross-product constraints, or explicit pricing rules in the simulation, no persistent arbitrage opportunities were identified.

### De-emphasized: Machine Learning
Machine learning models were explored, but the relatively small sample size (~1500 daily observations) and low signal-to-noise ratio made reliable generalization difficult.  
In most cases, ML-based models failed to outperform simpler baselines after costs and constraints, and were therefore not used in the final strategy.

---

## 1.1 Pairs Trading — Viability Analysis

Pairs trading is a **relative-value** strategy. Instead of predicting whether the market will go up or down, it looks for two stocks that move closely together. If their prices temporarily diverge, the strategy bets that they will revert back to their usual relationship.

To assess whether this was viable, I first examined the cross-asset correlation structure.

<p align="center">
  <img src="plots/01_correlation_matrix.png" width="500">
</p>

<p align="center">
  <em>Figure 1. Correlation matrix of the 50 stocks. Off-diagonal values are uniformly low, indicating weak cross-asset relationships.</em>
</p>

### What This Graph Shows

The plot above is a **correlation matrix** of the 50 stocks.

- Each square represents the correlation between a pair of stocks.
- Red along the diagonal simply shows that each stock is perfectly correlated with itself (correlation = 1).
- The off-diagonal squares represent how strongly different stocks move together.
- Darker blue colours indicate low or near-zero correlation.

In this matrix, almost all off-diagonal values are light blue. The strongest pairwise correlation is only around **0.1**, which is very low.

### Why This Matters for Pairs Trading

Pairs trading relies on finding two assets that:

1. Move closely together (high correlation), and  
2. Have a stable long-term relationship (often tested with cointegration).

If two stocks barely move together in the first place, there is no meaningful spread relationship to exploit. Small, unstable correlations suggest:

- No strong common drivers between assets.
- No persistent relative pricing relationship.
- High likelihood that any apparent relationship is just noise.

Without strong and stable co-movement, any spread constructed between two stocks would behave more like random noise than a mean-reverting signal.

### Conclusion

Because the correlation structure showed **uniformly low cross-asset correlations**, there were no clear candidate pairs worth pursuing.

Given this, I decided not to proceed with deeper analysis such as formal cointegration testing. The data did not provide a strong enough foundation to justify further research into pairs trading, so this approach was excluded from the final algorithm.

---

## 1.2 Momentum

Momentum assumes that assets with strong recent performance continue to outperform over a given horizon (and weak performers continue to lag). In this market, the key question was whether returns showed enough short-term persistence to make momentum signals meaningful, rather than pure noise.

<p align="center">
  <img src="plots/04_cumulative_returns.png" width="520">
</p>

<p align="center">
  <em>Figure 2. Cumulative returns of the 50 stocks (grey) with an equal-weight “market” index in red, rebased to 100. Individual names diverge substantially over time, while the index is smoother and often drifts sideways.</em>
</p>

### Cross-sectional behaviour

Figure 2 shows that while the equal-weight index does not exhibit a strong, sustained trend over the full period, individual stocks spread out widely. This indicates meaningful dispersion in performance across names and suggests the market experiences periods where moves are directional, even if the long-run index level is relatively flat.

To test whether directional moves tend to persist, I examined the autocorrelation of daily market returns.

<p align="center">
  <img src="plots/05_market_acf.png" width="520">
</p>

<p align="center">
  <em>Figure 3. Autocorrelation function (ACF) of daily returns for the equal-weight market index. Lag 1 is strongly positive (around ~0.4) and exceeds the confidence band, indicating short-horizon return persistence.</em>
</p>

### Market-level momentum looks real

The market index shows clear positive autocorrelation at short lags (strongest at lag 1, still positive at lag 2). In practical terms, this implies that recent market direction carries information for the next one to two trading days, which is consistent with **short-horizon momentum**.

### But per-stock momentum is weak / inconsistent

Even when we explicitly look for the **stocks with the strongest rolling autocorrelation**, the effect is much smaller and far less stable than the market index.

<p align="center">
  <img src="plots/20A_stock_rolling_acf_lag1_top2.png" width="720">
</p>

<p align="center">
  <em>Figure 3A. Rolling 100-day lag-1 autocorrelation for the top 2 highest-ACF stocks. These are the “best case” names for single-stock momentum.</em>
</p>

- The top two stocks’ rolling lag-1 ACF spends a lot of time near **0 to 0.15**, occasionally spiking above **0.2**, and sometimes turning negative.
- Compared with the market’s lag-1 ACF (≈ **0.4**), even the *best* single-name momentum is substantially weaker.

For contrast, the bottom-ACF stocks show that negative autocorrelation exists, but it also isn’t clean or persistent:

<p align="center">
  <img src="plots/20B_stock_rolling_acf_lag1_bottom2.png" width="720">
</p>

<p align="center">
  <em>Figure 3B. Rolling 100-day lag-1 autocorrelation for the bottom 2 lowest-ACF stocks. These names skew negative on average, but still exhibit unstable swings and occasional spikes.</em>
</p>

### Conclusion

- **Momentum exists primarily at a market-wide level.** The index shows strong short-lag persistence (lag-1 ACF ~0.4).
- **Momentum is not reliably tradable per-stock.** Even the top-ACF stocks have much weaker and less stable autocorrelation than the market proxy.
- Practically, this pushed momentum usage toward **market regime / exposure filters**, rather than a “rank stocks by momentum and buy winners” approach.

---

## 1.3 Mean Reversion

Mean reversion assumes that large moves tend to be followed by a pullback toward an anchor (a rolling mean, long-run average, or some notion of “fair value”). In this market, the key viability question was whether returns exhibit **negative** short-horizon dependence (bounce-back), either at the market level or consistently across individual names.

<p align="center">
  <img src="plots/11_market_nextday_scatter.png" width="520">
</p>

<p align="center">
  <em>Figure X. Next-day returns versus same-day returns for the equal-weight market. The fitted slope is positive (about 0.43), indicating continuation rather than reversal at a one-day horizon.</em>
</p>

### Market-level behaviour: continuation dominates

Figure X directly tests a simple mean-reversion premise: “after an up day, expect a down day” and vice versa. The relationship is clearly **positive**, not negative. This implies that, on average, daily market moves tend to **persist** into the next day rather than snap back. A naive mean reversion rule that fades yesterday’s move would therefore be fighting the dominant short-horizon structure in the data.

<p align="center">
  <img src="plots/12_market_bounceback_extremes.png" width="520">
</p>

<p align="center">
  <em>Figure Y. Average forward cumulative market returns after extreme days defined by a rolling z-score threshold (|z| &gt; 2). Post-extreme performance is directionally consistent with the initial move across multiple horizons.</em>
</p>

### Extremes do not reliably snap back

A common mean reversion variant is to fade “extreme” days, expecting them to be overreactions. Figure Y tests exactly that by conditioning on large positive and negative shocks. The results show **directional follow-through** rather than clean reversals: after strongly positive days, average forward returns remain positive, and after strongly negative days, forward returns remain negative across 1 to 5 day horizons. This is the opposite of what a robust short-horizon mean reversion edge would require.

<p align="center">
  <img src="plots/13_ar1_phi_distribution.png" width="520">
</p>

<p align="center">
  <em>Figure Z. Distribution of AR(1) coefficients across individual stocks. Most names cluster near zero with a slight positive bias, and only a minority show negative coefficients consistent with short-horizon mean reversion.</em>
</p>

### Cross-sectional evidence: weak and inconsistent mean reversion

Figure Z shows how much each stock’s return today depends on its return yesterday.

- If the AR(1) coefficient (φ) is **positive**, the stock tends to continue in the same direction (momentum).
- If φ is **negative**, the stock tends to reverse direction (mean reversion).
- If φ is **close to zero**, yesterday’s move has little to no predictive power.

In the graph, most stocks cluster near zero with a slight positive tilt. This means:

- There is no strong universal mean-reversion effect.
- A small amount of short-term continuation is present in some names.
- Any mean-reversion strategy would need to be selective rather than applied broadly.

### Conclusion

Across both the market proxy and the cross-section, the diagnostics do not support **simple daily mean reversion** as a primary edge. One-day dynamics show continuation, “extreme” moves tend to follow through, and single-name short-horizon mean reversion appears weak and inconsistent. Any mean reversion approach in this environment would need to be highly selective (instrument-level selection or specialised triggers) rather than applied as a universal fade rule.

---

## 1.4 Volatility & Regimes

This section looks at how the market’s volatility and short-term return behaviour change over time, and what that tells us about different regimes.

---

### 1.4.1 Overall level of volatility

First I looked at the distribution of rolling volatility across all stocks and days.

<p align="center">
  <img src="plots/03_rolling_vol_hist.png" width="520">
</p>

<p align="center">
  <em>Figure 4. Histogram of 100-day annualised volatility for all stock–day pairs.</em>
</p>

**How to read it**

- Each bar counts how many observations had a given 100-day volatility level.
- Most observations sit between roughly **8% and 22%** annualised volatility.
- The shape is not a single sharp peak – there are several “humps”, which suggests the market moves through quieter and busier periods.

So the universe is not extremely wild, but volatility is clearly **not constant**.

---

### 1.4.2 Volatility across days and across stocks

Next I checked how volatility changes **over time** (market-wide) and **between stocks**.

<p align="center">
  <img src="plots/09_cross_sectional_vol_distribution.png" width="520">
</p>

<p align="center">
  <em>Figure 5. Distribution of cross-sectional average 100-day volatility (average across all stocks per day).</em>
</p>

<p align="center">
  <img src="plots/10_avg_vol_distribution.png" width="520">
</p>

<p align="center">
  <em>Figure 6. Distribution of average 100-day volatility by stock.</em>
</p>

**What they show**

- **By day (Figure 5)**: the cross-sectional average volatility moves around, but the spread is fairly tight. On most days, the “typical” stock is in a similar volatility band.
- **By stock (Figure 6)**: some names are much more volatile than others over the full sample. There is a clear range from steady stocks to very jumpy ones.

This tells us two things:

1. There is a **market-level volatility state** that slowly changes over time.
2. There is stable **cross-sectional dispersion**, with some stocks naturally riskier than others.

---

### 1.4.3 Volatility regimes over time

To see how volatility evolves, I looked at a **100-day rolling volatility** of the equal-weight index and marked simple low- and high-volatility bands.

<p align="center">
  <img src="plots/15_market_rolling_vol_regimes.png" width="720">
</p>

<p align="center">
  <em>Figure 7. 100-day rolling volatility of the equal-weight index, with 20th and 80th percentile lines.</em>
</p>

**Reading the graph**

- The blue line is the 100-day rolling volatility.
- The green dashed line marks the **20th percentile** (low-vol threshold).
- The red dashed line marks the **80th percentile** (high-vol threshold).

When the blue line is near the green line, the market is in a **calmer regime**. When it is near or above the red line, the market is in a **high-vol regime**.

The plot shows that:

- Volatility clusters: once the market is calm or noisy, it tends to stay that way for a while.
- The range of volatility is not extreme, but the difference between low and high regimes is still meaningful.

---

### 1.4.4 Volatility is very much per-stock

A key practical finding was that volatility is not just a “market regime” variable — it is **highly cross-sectional**.

<p align="center">
  <img src="plots/19_rolling_volatility_extremes_timeseries.png" width="900">
</p>

<p align="center">
  <em>Figure 7A. Rolling 100-day annualised volatility for the top 2 most volatile vs top 2 least volatile stocks.</em>
</p>

- The most volatile names sit around roughly **~0.19 to 0.25** annualised vol.
- The least volatile names sit around roughly **~0.06 to 0.08** annualised vol.
- Importantly, this gap is *persistent* — the “high vol” stocks remain high, and the “low vol” stocks remain low.

**Implication:** any strategy that sizes positions uniformly across names is implicitly taking much larger risk in the high-vol stocks. This strongly supports **volatility scaling / risk targeting per instrument** (and explains why naive equal-size signals often get dominated by a small subset of names).

---

### 1.4.5 Short-term autocorrelation: momentum vs mean reversion

Volatility alone does not tell us the direction of returns. To see whether short-term moves tend to **continue** (momentum) or **reverse** (mean reversion), I looked at **rolling autocorrelation** of the market index at different lags.

For each lag, I computed the autocorrelation over a rolling 100-day window:

- Values **above zero** mean that returns tend to have the **same sign** as in the past (momentum).
- Values **below zero** mean that returns tend to have the **opposite sign** (mean reversion).

The red line is a rough **momentum threshold**; the green line is a **mean-reversion threshold**.

#### Lag 1

<p align="center">
  <img src="plots/16_market_rolling_acf_lag1.png" width="720">
</p>

<p align="center">
  <em>Figure 8. 100-day rolling lag-1 autocorrelation of index returns.</em>
</p>

- The blue line is **almost always positive**.
- For long stretches it stays above the red momentum threshold.
- It rarely comes close to the green mean-reversion line.

This means that, day-to-day, the index shows **strong short-term momentum**.

#### Lag 2

<p align="center">
  <img src="plots/16_market_rolling_acf_lag2.png" width="720">
</p>

<p align="center">
  <em>Figure 9. 100-day rolling lag-2 autocorrelation of index returns.</em>
</p>

- Lag-2 autocorrelation is also usually positive.
- It spends a fair amount of time at or above the momentum threshold, although values are smaller than for lag-1.

So momentum carries some information over **two days**, but weakens compared with lag-1.

#### Lag 5

<p align="center">
  <img src="plots/16_market_rolling_acf_lag5.png" width="720">
</p>

<p align="center">
  <em>Figure 10. 100-day rolling lag-5 autocorrelation of index returns.</em>
</p>

- Around lag-5, the line is much closer to zero.
- It moves above and below zero and rarely touches the thresholds.

This suggests that by around **five days**, the clear memory in returns has faded. Momentum is weaker and less stable.

#### Lag 10

<p align="center">
  <img src="plots/16_market_rolling_acf_lag10.png" width="720">
</p>

<p align="center">
  <em>Figure 11. 100-day rolling lag-10 autocorrelation of index returns.</em>
</p>

- Lag-10 autocorrelation fluctuates around zero.
- It almost never reaches the momentum or mean-reversion thresholds.

This indicates **very little predictable structure** at this horizon – returns at a 10-day distance look close to independent.

---

### 1.4.6 Lead–Lag Structure (Market vs Stocks)

A natural follow-up question is whether the “market” moves first and individual stocks respond later (or vice versa). To test this, I computed cross-correlations between the equal-weight market return at time *t* and each stock return at time *(t + lag)*.

- **Positive lag** = the market leads the stock  
- **Negative lag** = the stock leads the market

<p align="center">
  <img src="plots/21_lead_lag_heatmap.png" width="900">
</p>

<p align="center">
  <em>Figure 12. Lead–lag heatmap: correlation between Market(t) and Stock(t + lag). The strongest structure is concentrated at lag 0.</em>
</p>

Two clear patterns show up:

1. **Contemporaneous correlation dominates (lag 0).**  
   There is a strong band at lag 0 across almost all stocks, meaning most names simply co-move with the market on the same day.

2. **Any predictive lead–lag signal is weak and inconsistent.**  
   There are occasional pockets where lag +1 looks stronger for specific stocks, but this is not uniform across the universe and is likely fragile.

Averaging across all stocks makes the picture even clearer:

<p align="center">
  <img src="plots/22_avg_lead_lag_profile.png" width="720">
</p>

<p align="center">
  <em>Figure 13. Average lead–lag profile (Market vs Universe). The peak is at lag 0; correlations decay quickly as |lag| increases.</em>
</p>

- The average correlation peaks at **lag 0 (~0.16)**.
- There is a smaller bump at **lag +1 (~0.08)** (market leading by 1 day), but it is much weaker than contemporaneous co-movement.
- Correlation decays quickly beyond 1–2 days in either direction.

**Conclusion:** lead–lag effects are not a strong, broad edge in this universe. The market and stocks mostly move together contemporaneously, which is more useful for risk/exposure control than for clean prediction.

---

### 1.4.7 Conclusions on volatility and regimes

Putting all of this together:

1. **Momentum is mostly market-wide, not per-stock.**  
   The market index has strong lag-1 autocorrelation (≈0.4), but even the top 2 per-stock ACF names have meaningfully lower and unstable autocorrelation. This implies momentum is more suitable as a **market exposure / regime filter** than as a single-stock selection signal.

2. **Volatility is very much per-stock.**  
   Some stocks are persistently ~3–4× more volatile than others (Figure 7A). Risk is dominated by which names you trade and how you size them, so per-stock volatility scaling is essential.

3. **Volatility varies over time as well.**  
   The index 100-day volatility moves between low and high bands, forming clear volatility regimes. Volatility also clusters: calm periods and noisy periods tend to come in blocks rather than switching every few days.

4. **Short-term momentum is strongest at very short lags.**  
   The rolling autocorrelation plots show clear positive dependence at 1–2 day lags. By 5–10 days, the signal is much weaker and often indistinguishable from noise.

5. **Mean reversion is not a dominant feature at daily horizons.**  
   Autocorrelation is rarely strongly negative at the market level, and per-stock mean reversion is inconsistent. There are no long periods where the market consistently shows strong bounce-back behaviour.

6. **Lead–lag is mostly contemporaneous.**  
   The heatmap and average profile show the strongest relationship at lag 0, with only modest lag ±1 effects. This is more useful for understanding market coupling than building robust predictive signals.

These observations suggest that any strategy in this universe should:

- be aware that **risk changes over time**,  
- respect the fact that **short-term market momentum exists but fades quickly**,  
- size carefully because **volatility is highly stock-specific**, and  
- be cautious about relying on **daily mean reversion** or **lead–lag prediction**, which are weak and inconsistent in the data.

---

# 2) Algorithm Analysis

## 2.1 Final Strategy Overview

My final submission is a **market-directional momentum strategy** with **per-instrument volatility scaling**.

At a high level, it does two things:

1) **Decides market direction (risk-on / risk-off)** using short-horizon momentum of an equal-weight “index”.
2) **Allocates risk across the 50 instruments** by sizing each position inversely to its recent realized volatility (so high-vol names get smaller size, low-vol names get larger size).

This design directly matches what showed up in the data:

- **Momentum exists primarily at the market level** (index-level persistence is much cleaner than per-stock momentum).
- **Volatility is strongly cross-sectional** (some names are persistently 3–4× more volatile), so sizing must be risk-aware.

---

### Signal definition (index momentum)

Let:

- \( P_{i,t} \) be the price of instrument \( i \) on day \( t \)
- \( I_t = \frac{1}{N}\sum_{i=1}^N P_{i,t} \) be the equal-weight index proxy
- `LOOKBACK = 10`

Compute the index momentum:

\[
m_t = \frac{I_t}{I_{t-10}} - 1
\]

Apply a no-trade band (`THRESH = 0.002`):

- If \( |m_t| < 0.002 \) → **go flat** (all positions 0)
- Else:
  - If \( m_t > 0 \) → **direction = +1** (long bias)
  - If \( m_t < 0 \) → **direction = -1** (short bias)

So when the market proxy is trending up/down over ~2 weeks by more than 20 bps, the strategy takes a directional stance.

---

### Position sizing (volatility-scaled, per instrument)

For each instrument \( i \), estimate recent realized volatility from daily returns over `VOL_WINDOW = 10` days:

\[
\sigma_i = \mathrm{std}\left(r_{i,t-10:t-1}\right)
\quad\text{where}\quad
r_{i,t} = \frac{P_{i,t}}{P_{i,t-1}} - 1
\]

Then compute target shares:

\[
q_i = \left\lfloor \frac{\text{TARGET\_DOLLAR}}{P_{i,t}\cdot \sigma_i} \right\rfloor
\]

Interpretation:  
\(P\cdot\sigma\) is an estimate of **daily $-move per share**, so dividing a constant budget by this approximates **risk targeting** (roughly equalizing expected daily volatility contribution across names).

Finally:

- Clip to the hard per-instrument exposure cap \( |q_i \cdot P_{i,t}| \le 10000 \)
- Enforce at least 1 share for any non-zero position (to avoid “signal but 0 size” edge cases)
- Apply the global direction:

\[
\text{position}_i = \text{direction} \cdot q_i
\]

---

### Why this is robust (and intentionally “simple”)

- It uses **one primary edge** (market momentum) rather than mining weak cross-sectional structure.
- It includes a **no-trade zone** to reduce churn and commissions when the market is drifting.
- It uses **volatility-aware sizing** so a few noisy names don’t dominate risk and P\&L.
- It respects the environment’s key constraint: **±$10k per instrument** at trade time.


---

## 2.2 Trading Analysis

This section explains what trades the algorithm places, how to interpret them, and how to evaluate whether a “trade” was successful.

### 2.2.1 What counts as a trade in this environment?

The evaluation engine executes trades via **position changes**:

- Each day \(t\), the algo outputs a desired position vector \( \mathbf{q}_t \).
- The engine trades the delta:
  \[
  \Delta \mathbf{q}_t = \mathbf{q}_t - \mathbf{q}_{t-1}
  \]
- Commission is charged on total dollar volume traded:
  \[
  \text{commission}_t = \text{commRate} \cdot \sum_i \left| \Delta q_{i,t} \right| \cdot P_{i,t}
  \]
  with `commRate = 0.0005`.

So “a trade” isn’t a single buy/sell ticket — it’s the **lifecycle of a position** (enter → hold/resize → exit).

---

### 2.2.2 Lifecycle interpretation (LONG / SHORT / FLAT)

Because the strategy uses *one market direction signal*, each instrument is typically in one of three regimes:

- **LONG:** position \( q_i > 0 \)
- **SHORT:** position \( q_i < 0 \)
- **FLAT:** position \( q_i = 0 \)

In a single-stock view:

- A **red down-arrow** indicates an **entry into a short regime** (position becomes negative).
- A **green up-arrow** indicates an **entry into a long regime** (position becomes positive).
- When the position later returns to **0**, that is an **exit** from that regime — i.e., you’ve stopped shorting/longing that stock.

This is exactly how to read your plot: the bottom panel (position) is the ground truth.

---

### 2.2.3 Example: single-stock trace (signals + equity + position)

The figure below shows a 250-day window for **Stock 38**, highlighting:

- regime shading (green = long held, red = short held),
- entry markers,
- and the resulting gross vs net equity curve (commissions included).

<p align="center">
  <img src="plots/stock38_trade_trace.png" width="900">
</p>

<p align="center">
  <em>Figure 14. Stock 38 trade regimes (long/short/flat), entries/exits, and equity curve over the same window.</em>
</p>

Two important takeaways from this plot:

1) **Exiting to 0 means the trade is closed.**  
   Once the position returns to 0, that short/long “episode” is finished.

2) **Profit is not determined by entry/exit markers alone.**  
   Because sizing is volatility-scaled, the position can be **resized** while the direction stays the same (extra buys/sells inside the same regime). Those intermediate trades affect both P&L and commissions.

---

### 2.2.4 How to tell if a trade was profitable

Define a **trade episode** for a single stock as a maximal contiguous block of days where the position sign is constant and non-zero.

For one episode:

- Entry day: first day the position becomes non-zero (or flips sign)
- Exit day: day the position returns to 0 (or flips sign)

The simplest way to compute whether the episode made money is to compute **marked-to-market P&L across the holding window**, including commissions from the actual executed deltas.

For a single stock, gross P&L over time is driven by:

\[
\text{grossPnL} \approx \sum_{t \in \text{hold}} q_t \cdot (P_{t+1}-P_t)
\]

- If you are **long** (\(q_t>0\)), you profit when \(P\) rises.
- If you are **short** (\(q_t<0\)), you profit when \(P\) falls (because \(q_t(P_{t+1}-P_t)\) becomes positive when \(P_{t+1}<P_t\)).

Net episode P&L is:

\[
\text{netPnL} = \text{grossPnL} - \sum_{t \in \text{episode}} \text{commRate}\cdot |\Delta q_t|\cdot P_t
\]

So a “successful trade” is simply an episode with **netPnL > 0**.

In practice, the cleanest workflow is:

- detect each episode (enter → exit),
- compute:
  - episode duration
  - grossPnL, netPnL
  - max adverse excursion (MAE) / max favorable excursion (MFE)
  - hit-rate across episodes (how many net winners)

That’s what I used the single-stock analysis script for: turning regime flips into a concrete trade log with per-trade P&L.


---

## 2.3 Portfolio Construction & Risk
- position sizing rules
- exposure caps
- diversification logic
- drawdown and volatility controls

---

## 2.4 Backtesting Methodology
- execution assumptions
- transaction cost modelling
- walk-forward validation
- known sources of bias and mitigation

---

## 2.5 Parameter Selection & Robustness
- grid search ranges
- stability regions versus sharp optima
- ablation tests removing individual components

---

## 2.6 Results Snapshot
- leaderboard score / rank (if shareable)
- cumulative P&L curves
- drawdowns and volatility
- periods of strongest and weakest performance

---

# 3) Learnings

### Technical
- data handling and backtesting pitfalls
- cost sensitivity and turnover control

### Quant intuition
- where signal genuinely exists versus noise
- importance of regime awareness

### Process
- faster elimination of weak ideas
- earlier focus on robustness

**Biggest mistakes**
- <mistake 1>
- <mistake 2>

**What I’d do differently**
- <improvement 1>
- <improvement 2>

---

# 4) Conclusion

- **What worked best:**  
  Regime-filtered single-asset signals

- **What didn’t work:**  
  Cross-asset relative-value strategies in a low-correlation universe

- **Final takeaways:**  
  Robustness beats complexity; elimination is as important as discovery

- **Future work:**  
  Explore richer regime definitions and alternative anchoring mechanisms

---

## Repository Structure
<describe folders and files>
