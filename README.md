# Team RAJ 🚀
**SIG Algothon 2025 — Strategy, Code, and Insights**

> This repository contains my research notes, analysis plots, and trading algorithm submission(s) for the SIG Algothon.  
> It’s written as both a post-mortem and a reference for anyone learning systematic trading / competition-style quant.

---

## Introduction
Hi — I’m James engineering student at Monash University with a keen interest in quantative finance.  
This report documents:
- how I explored the market data,
- the hypotheses I tested,
- what I implemented in the final algorithm,
- what worked / didn’t work,
- and what I learned.

---

## About the SIG Algothon
**SIG Algothon** is an algorithmic trading competition where participants build bots to trade one or more instruments in a simulated (or curated) market environment.

### Environment assumptions (fill this in)
- **Instruments:** <e.g. N stocks / ETFs / synthetic products>
- **Time period & frequency:** <e.g. daily / minute bars, #days>
- **Execution model:** <e.g. market orders only / limit orders / mid-price fills>
- **Costs:** <e.g. spreads, fees, slippage assumptions>
- **Constraints:** <position limits, leverage, risk limits>
- **Objective metric:** <PnL, Sharpe, drawdown-adjusted score, leaderboard metric>

---

# 1) Market Analysis

## 1.1 Pairs-Trading
Pairs trading is a **relative-value** strategy: instead of predicting direction, it trades the **spread** between two related assets.

What I looked for:
- correlation / co-movement stability
- cointegration tests (optional)
- spread stationarity checks
- mean-reversion speed (half-life)

What I plotted / computed:
- rolling correlation
- spread (price_A − β·price_B) and z-score
- entry/exit threshold backtests
- sensitivity to window lengths and β estimation

**Key takeaway:** <what you found>

---

## 1.2 Momentum
Momentum assumes recent winners keep winning (and losers keep losing) over a horizon.

What I tested:
- simple time-series momentum: sign(rolling return)
- moving average crossover signals
- breakout rules
- momentum performance by regime (volatility / correlation / trend)

**Key takeaway:** <what you found>

---

## 1.3 Mean-Reversion
Mean reversion assumes prices (or spreads) revert toward an anchor (MA / VWAP / “fair value proxy”).

What I tested:
- z-score reversion around rolling mean
- EMA-based deviation triggers
- autocorrelation of returns (including random baselines)
- reversion speed vs. transaction costs

**Key takeaway:** <what you found>

---

## 1.4 Volatility & Regimes
Volatility and correlation often define *regimes* where strategies behave differently.

Signals I used / explored:
- rolling volatility (annualized)
- rolling average pairwise correlation (market “synchronization”)
- trend filter (price vs long MA)
- distribution shifts (fat tails, skew)

How I used regimes:
- switch parameters (thresholds, position sizes)
- turn strategies on/off
- reduce risk in “stress” regimes

**Key takeaway:** <what you found>

---

## 1.5 Arbitrage
In competition settings, “arbitrage” often means **structural** or **synthetic** mispricing.

Examples (fill in what applies):
- basket vs constituents
- cross-venue / cross-product pricing constraints
- deterministic pricing rules / conversions / fees
- predictable spreads from the sim mechanics

**Key takeaway:** <what you found>

---

## 1.6 Machine Learning
ML is only useful if it:
1) generalizes out-of-sample, and  
2) beats simpler baselines after costs and constraints.

What I tried:
- feature set: <returns, vol, momentum, spreads, regime flags>
- models: <linear, logistic, tree-based, etc.>
- validation: walk-forward / time-series split
- calibration: probability thresholds and action mapping

**Key takeaway:** <what you found>

---

# 2) Algorithm Analysis

## 2.1 Final Strategy Overview
High-level summary of the final bot:
- **Core edge(s):** <e.g. mean reversion in spreads + regime filter>
- **Execution style:** <market/limit, when/how you trade>
- **Risk management:** <position limits, stop logic, scaling>
- **Fail-safes:** <data missing handling, cooldowns, max trades/day>

---

## 2.2 Signal Construction
Describe each signal:
- inputs
- formula
- parameters (windows, thresholds)
- why it should work in this environment

---

## 2.3 Portfolio Construction & Risk
- position sizing rules
- exposure caps
- diversification logic
- drawdown controls (if used)

---

## 2.4 Backtesting Methodology
- how you simulated fills
- how you included costs
- walk-forward / train-test splits
- why you trust the results

---

## 2.5 Parameter Selection & Robustness
- grid search ranges
- stability checks (flat “good regions” > sharp peaks)
- ablation: what happens if you remove each component

---

## 2.6 Results Snapshot
- leaderboard score / rank (if shareable)
- PnL curves (in/out-of-sample)
- Sharpe / max drawdown / hit rate
- where strategy made / lost money

---

# 3) Learning
What I learned during the algothon:
- **Technical:** <data cleaning, backtesting pitfalls, etc.>
- **Quant intuition:** <what signals were real vs noise>
- **Process:** <what I’d do earlier next time>

Biggest mistakes:
- <mistake 1>
- <mistake 2>

What I’d do differently:
- <improvement 1>
- <improvement 2>

---

# 4) Conclusion
- **What worked best:** <short bullet list>
- **What didn’t work:** <short bullet list>
- **Final takeaways:** <short bullet list>
- **Future work:** <ideas to explore>

---

## Repository Structure
