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
  <em>Figure 3. Autocorrelation function (ACF) of daily returns for the equal-weight market index. Lag 1 and lag 2 are strongly positive and exceed the confidence band, indicating short-horizon return persistence.</em>
</p>

### Evidence for short-horizon momentum

The ACF in Figure 3 shows clear positive autocorrelation at the first few lags, with lag 1 around 0.4 and lag 2 around 0.2 to 0.25. Both exceed the confidence band, supporting the presence of statistically meaningful short-term persistence in market returns.

In practical terms, this implies that recent market direction carries information for the next one to two trading days, which is consistent with short-horizon momentum. The effect appears concentrated in the earliest lags, so momentum signals based on recent history (days to a couple of weeks) are more justified by these diagnostics than long-horizon trend-following.

### Conclusion

Overall, the market structure suggested momentum was viable, but primarily as a short-horizon effect. Individual stocks showed large dispersion over time, and the equal-weight market returns displayed strong positive autocorrelation at early lags. This supported focusing momentum research on short lookback windows that align with where persistence was most visible.

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

In simple terms: yesterday’s move usually doesn’t strongly predict today’s move — and when it does, it slightly favors continuation rather than reversal.

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

### 1.4.4 Short-term autocorrelation: momentum vs mean reversion

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

### 1.4.6 Conclusions on volatility and regimes

Putting all of this together:

1. **Volatility varies over time.**  
   The index 100-day volatility moves between low and high bands, forming clear volatility regimes. Volatility also clusters: calm periods and noisy periods tend to come in blocks rather than switching every few days.

2. **Stocks have different baseline risk.**  
   Some names are naturally more volatile than others. Treating all stocks as if they have the same risk would be misleading.

3. **Short-term momentum is strongest at very short lags.**  
   The rolling autocorrelation plots show clear positive dependence at 1–2 day lags. By 5–10 days, the signal is much weaker and often indistinguishable from noise.

4. **Mean reversion is not a dominant feature at daily horizons.**  
   Autocorrelation is rarely strongly negative, either for the index or across individual stocks. There are no long periods where the market consistently shows strong bounce-back behaviour.

5. **Regimes can be described by both volatility and autocorrelation.**  
   - A **high-vol, positive-autocorrelation** regime looks like a strong trend with large swings.  
   - A **low-vol, positive-autocorrelation** regime is calmer but still directional.  
   - Periods where autocorrelation is near zero look more like **noise-dominated** markets, where simple directional bets are harder to justify.

These observations suggest that any strategy in this universe should:

- be aware that **risk changes over time**,  
- respect the fact that **short-term momentum exists but fades quickly**, and  
- be cautious about relying on **daily mean reversion**, which is weak and inconsistent in the data.


---

# 2) Algorithm Analysis

## 2.1 Final Strategy Overview

- **Core edges:**  
  Single-asset mean reversion combined with regime filters

- **Execution style:**  
  Daily market execution with full position rebalancing

- **Risk management:**  
  Position caps, volatility scaling, and regime-based exposure reduction

- **Fail-safes:**  
  Position clipping awareness, conservative defaults, and cooldown logic

---

## 2.2 Signal Construction
For each signal:
- inputs and preprocessing
- mathematical definition
- parameter choices
- intuition for why it should work in this environment

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
