# Team RAJ 🚀  
**SIG Algothon 2025 - Strategy, Research, and Insights**

> This repository contains our research notes, analysis plots, and algorithm submission(s) for the SIG Algothon.  
> It’s written as a post-mortem and as a reference for anyone learning systematic trading or competition-style quant research.

---

## Team

We competed as **Team RAJ**:

<p align="center">
  <img src="images/james_goss.jpeg" width="520" />
</p>

<p align="center">
  <em> James Goss </em>
</p>

---

## Introduction

Hi, we’re Team RAJ. We’re engineering students at Monash, and we’re interested in quantative trading.

This repo is our write-up from **SIG Algothon 2025**. It includes:
- the key plots we used to understand the dataset,
- the strategy ideas we tested (and what we killed early),
- what we actually submitted,
- and what we learned from the process.

We tried to keep the focus on things that should hold up outside of one lucky backtest:
- being honest about what the data supports,
- keeping costs and constraints front-of-mind,
- and avoiding overfitting.

---

## Introduction to the Algothon

Here’s the setup the competition uses:

- **Universe:** 50 synthetic stocks (0–49), daily prices (~1500 days).
- **Info available:** on day *t* we only see prices up to day *t* (no future data).
- **Trading:** each day we output target share positions; the sim trades from yesterday’s position to the new one at the latest price.
- **Costs & limits:** 5 bps commission on dollars traded, and a ±$10,000 notional cap per stock (integer shares, clipped if exceeded).
- **Score:** rewards steady P&L, not just big swings:  
  **Score = mean(P&L) − 0.1 × std(P&L)**

---

# 1) Market Analysis

## 1.0 Strategy Feasibility Screening

Before building strategies, we first checked what was even realistic with daily prices + commission + position caps. A lot of “standard” ideas don’t survive this setup.

### Excluded: Market Making
Market making needs intraday moves, spreads, and order book info.  
We only had daily close prices, so market making wasn’t feasible.

### Excluded: Pure Arbitrage
Classic arbitrage needs a clear pricing rule, conversions, or cross-venue differences.  
None of that existed in this simulation, and we didn’t find anything close to risk-free.

### De-emphasized: Machine Learning
We explored ML, but the dataset is small (~1500 days) and noisy.  
Most ML approaches didn’t beat simple baselines after costs, so we didn’t use them in the final strategy.

---

## 1.1 Pairs Trading - Viability Analysis

Pairs trading is a **relative-value** strategy. Instead of predicting whether the market will go up or down, it looks for two stocks that move closely together. If their prices split apart, the strategy bets they come back together.

To see if that was even possible, we started by checking cross-asset correlation.

<p align="center">
  <img src="plots/01_correlation_matrix.png" width="500">
</p>

<p align="center">
  <em>Figure 1. Correlation matrix of the 50 stocks. Off-diagonal values are uniformly low, meaning weak cross-asset relationships.</em>
</p>

### What this graph shows

- Each square is the correlation between two stocks.
- The diagonal is red because each stock is perfectly correlated with itself.
- Everything off-diagonal is mostly near zero.

The strongest correlation we saw was only around **0.1**, which is very low.

### Why this matters

Pairs trading needs strong and stable co-movement. If stocks don’t move together, there’s no reliable “spread” to trade, it just looks like noise.

### Conclusion

Because cross-asset correlations were uniformly weak, we didn’t pursue pairs trading further (no cointegration testing, no spread models). It didn’t look like the dataset supported it.

---

## 1.2 Momentum

Momentum means: if something has been going up recently, it keeps going up (for a bit), and vice versa.

We first looked at cumulative returns to see whether the universe had meaningful trends.

<p align="center">
  <img src="plots/04_cumulative_returns.png" width="520">
</p>

<p align="center">
  <em>Figure 2. Cumulative returns of the 50 stocks (grey) with an equal-weight “market” index in red (rebased to 100).</em>
</p>

This plot shows big dispersion across stocks, while the index is smoother and often drifts sideways. That suggested any clean “stock picking” momentum might be hard, but market-level behaviour could still exist.

To test market-level momentum directly, we looked at autocorrelation of daily market returns.

<p align="center">
  <img src="plots/05_market_acf.png" width="520">
</p>

<p align="center">
  <em>Figure 3. Autocorrelation of daily returns for the equal-weight market index. Lag 1 is strongly positive (~0.4).</em>
</p>

### Market-level momentum looks real
Lag-1 is strongly positive, and lag-2 is still positive. In normal language: yesterday’s direction often carries into today (especially over 1–2 days).

### But per-stock momentum is weak / inconsistent
Even the “best” single names weren’t close to the market’s persistence.

<p align="center">
  <img src="plots/20A_stock_rolling_acf_lag1_top2.png" width="720">
</p>

<p align="center">
  <em>Figure 4. Rolling 100-day lag-1 autocorrelation for the top 2 highest-ACF stocks.</em>
</p>

<p align="center">
  <img src="plots/20B_stock_rolling_acf_lag1_bottom2.png" width="720">
</p>

<p align="center">
  <em>Figure 5. Rolling 100-day lag-1 autocorrelation for the bottom 2 lowest-ACF stocks.</em>
</p>

### Conclusion
- Momentum exists mainly at a **market-wide** level.
- Single-stock momentum is weaker and unstable.
- That pushed us toward a market regime / exposure approach, not “rank stocks and buy winners.”

---

## 1.3 Mean Reversion

Mean reversion means: after a big move, price tends to snap back.

A simple test is: do up days tend to be followed by down days (and vice versa)?

<p align="center">
  <img src="plots/11_market_nextday_scatter.png" width="520">
</p>

<p align="center">
  <em>Figure 6. Next-day returns vs same-day returns for the equal-weight market. The relationship is positive (continuation), not negative (reversal).</em>
</p>

This was the opposite of what we want for daily mean reversion: the market tended to **continue**, not bounce back.

We also tested “extreme day” bounce-backs.

<p align="center">
  <img src="plots/12_market_bounceback_extremes.png" width="520">
</p>

<p align="center">
  <em>Figure 7. Average forward returns after extreme days (|z| &gt; 2). Extreme moves tended to follow through more than they snapped back.</em>
</p>

And finally we checked per-stock short-horizon behaviour.

<p align="center">
  <img src="plots/13_ar1_phi_distribution.png" width="520">
</p>

<p align="center">
  <em>Figure 8. Distribution of AR(1) coefficients across stocks. Most are near zero with a slight positive bias.</em>
</p>

### Conclusion
Simple daily mean reversion didn’t look like a strong edge here. If mean reversion exists, it’s not consistent enough to be a main strategy.

---

## 1.4 Volatility & Regimes

This section is about how “noisy” the market is, and how that changes across time and across stocks.

### 1.4.1 Overall volatility level

<p align="center">
  <img src="plots/03_rolling_vol_hist.png" width="520">
</p>

<p align="center">
  <em>Figure 9. Histogram of 100-day annualised volatility across all stock–day pairs.</em>
</p>

Most observations sit roughly between **8% and 22%** annualised volatility, and the distribution has multiple humps, volatility clearly changes over time.

---

### 1.4.2 Volatility across days and across stocks

<p align="center">
  <img src="plots/09_cross_sectional_vol_distribution.png" width="520">
</p>

<p align="center">
  <em>Figure 10. Distribution of cross-sectional average 100-day volatility (average across all stocks per day).</em>
</p>

<p align="center">
  <img src="plots/10_avg_vol_distribution.png" width="520">
</p>

<p align="center">
  <em>Figure 11. Distribution of average 100-day volatility by stock.</em>
</p>

Takeaway:
- Volatility changes over time (market regime),
- but some stocks are *always* much riskier than others (cross-sectional risk).

---

### 1.4.3 Volatility regimes over time

<p align="center">
  <img src="plots/15_market_rolling_vol_regimes.png" width="720">
</p>

<p align="center">
  <em>Figure 12. 100-day rolling volatility of the equal-weight index with low/high bands (20th and 80th percentiles).</em>
</p>

Volatility clusters. Calm periods stay calm for a while, and noisy periods stay noisy for a while.

---

### 1.4.4 Volatility is very stock-specific

<p align="center">
  <img src="plots/19_rolling_volatility_extremes_timeseries.png" width="900">
</p>

<p align="center">
  <em>Figure 13. Rolling 100-day volatility for the top 2 most volatile vs top 2 least volatile stocks.</em>
</p>

The high-vol stocks stayed high-vol and the low-vol stocks stayed low-vol. This is why volatility scaling mattered so much.

---

### 1.4.5 Short-term autocorrelation over time (market)

<p align="center">
  <img src="plots/16_market_rolling_acf_lag1.png" width="720">
</p>

<p align="center">
  <em>Figure 14. Rolling 100-day lag-1 autocorrelation of index returns.</em>
</p>

<p align="center">
  <img src="plots/16_market_rolling_acf_lag2.png" width="720">
</p>

<p align="center">
  <em>Figure 15. Rolling 100-day lag-2 autocorrelation of index returns.</em>
</p>

<p align="center">
  <img src="plots/16_market_rolling_acf_lag5.png" width="720">
</p>

<p align="center">
  <em>Figure 16. Rolling 100-day lag-5 autocorrelation of index returns.</em>
</p>

<p align="center">
  <img src="plots/16_market_rolling_acf_lag10.png" width="720">
</p>

<p align="center">
  <em>Figure 17. Rolling 100-day lag-10 autocorrelation of index returns.</em>
</p>

Takeaway:
- Momentum is strongest at **1–2 day** horizons.
- By 5–10 days it mostly fades toward noise.

---

### 1.4.6 Lead–Lag structure (Market vs Stocks)

<p align="center">
  <img src="plots/21_lead_lag_heatmap.png" width="900">
</p>

<p align="center">
  <em>Figure 18. Lead–lag heatmap: correlation between Market(t) and Stock(t + lag). Strongest structure is at lag 0.</em>
</p>

<p align="center">
  <img src="plots/22_avg_lead_lag_profile.png" width="720">
</p>

<p align="center">
  <em>Figure 19. Average lead–lag profile across the universe. Peak at lag 0, quick decay as |lag| increases.</em>
</p>

Conclusion: lead–lag wasn’t a strong “predictive” edge. Most of the relationship is same-day co-movement.

---

### 1.4.7 Summary of what the market analysis told us

- The strongest signal was **market-level momentum** (short horizon).
- Mean reversion wasn’t consistent at the daily level.
- Cross-asset structure was weak, so pairs ideas didn’t look viable.
- Risk was dominated by **volatility differences between stocks**, so sizing mattered a lot.

---

# 2) Algorithm Analysis

This section explains what we submitted, how we tested it, how we picked parameters, and what the results looked like. The theme is: keep it simple, testable, and hard to overfit.

---

## 2.1 Final Strategy Overview

Our final submission is a **market (index) momentum strategy** with **volatility-scaled sizing**.

In plain terms:

- Build an **equal-weight market index** from the 50 instruments.
- Measure whether the index has been moving up or down over a short window (lookback).
- If the move is strong enough (passes a threshold), take exposure:
  - market up → go **long**
  - market down → go **short**
  - small / noisy move → stay **flat**
- Size each instrument using realised volatility, so risk isn’t dominated by a few wild stocks.
- Enforce constraints (±$10k cap, integer shares, clipping).

---

## 2.2 Trading Analysis (Example Trace: Stock 38)

<p align="center">
  <img src="plots/stock_38_trade_trace.png" width="900">
</p>

<p align="center">
  <em>Figure 20. Stock 38 trade trace: price + trades, equity curve (gross vs net), and position held.</em>
</p>

What we wanted to see:
- positions held in blocks (not constant flipping),
- costs clearly visible (gross vs net gap),
- churn mainly happening when the signal is choppy (and that’s where we lose).

---

## 2.3 Backtesting Methodology

We started with the standard evaluator most teams used (`eval.py` style). We didn’t rewrite the evaluator, we extended the same logic to run **walk-forward testing** and basic robustness checks.

### 2.3.1 The original `eval.py` (single run)

The baseline script:
- loads prices,
- steps forward day-by-day,
- calls `getMyPosition(history)` with no lookahead,
- clips positions to the ±$10k limit,
- charges 5 bps commission on traded dollar volume,
- records daily P&L and produces summary plots.

It can score the **last N days** or the **full dataset**, depending on `test_days`.  
The limitation is that it’s still **one window** (one slice of time).

### 2.3.2 What we added: walk-forward testing

Walk-forward testing repeats the evaluation across many consecutive time blocks:
- warm-up period,
- score a block,
- roll forward,
- score the next block,
- repeat.

This makes it much harder to fool ourselves with one lucky period.

### 2.3.3 Quick robustness checks

We also added a couple of cheap stress tests:
- **Noise test:** small random noise added to returns (checks fragility).
- **Shuffle/shift test:** break time alignment to ensure performance drops when structure is removed.

---

## 2.4 Parameter Selection & Robustness

The main knobs were:
1. lookback window,
2. threshold.

### 2.4.1 Parameter sweep (lookback vs threshold)

<p align="center">
  <img src="plots/parameter_sweep.png" width="950">
</p>

<p align="center">
  <em>Figure 21. Lookback vs threshold sweep. Green = good, red = bad.</em>
</p>

We chose settings from the middle of the “good region”, not the single best cell, because stability mattered more than squeezing out one extra in-sample point.

---

## 2.5 Results Snapshot

We competed as **team_raj** (shown as **Team Raj** on the official spreadsheets).

### Interim leaderboard
- **Rank:** 5th  
- **Score:** **19.77**

### Final general round leaderboard
- **Rank:** **4th**
- **Score:** **22.26**

### Thoughts on other teams’ results (and how much was variance)

- The top of the leaderboard was tight, small differences (or a few good/bad days) can move ranks.
- Teams above us likely did one extra thing really well: better turnover control, better sizing, better regime handling, or a small extra signal that didn’t add churn.
- Some standout scores could also be “right idea, right regime”. If the final window strongly favoured one style, that strategy looks amazing even if it’s less stable elsewhere.

---

# 3) Learnings

This competition was honestly a good reminder that most of the work in trading research is **eliminating bad ideas**, not finding fancy ones. The dataset looks simple (daily prices), but the constraints (costs + position caps + integer shares) make a lot of “textbook” strategies fall apart fast.

---

## 3.1 Technical Learnings

### Backtesting is easy to get wrong
Even with daily data, it’s very easy to accidentally introduce bugs that make results look way better than they should. The biggest things I had to stay on top of were:

- **No lookahead**: the bot must only see prices up to day *t* when deciding positions for day *t*.
- **Trading is on position changes**: costs come from **delta positions**, not from holding.
- **Position clipping matters**: the ±$10k cap interacts with price, so the share limit changes every day.

A strategy can look “stable” just because the evaluator silently clipped it into something else, or because the backtest is accidentally using tomorrow’s info. I found it was worth keeping the evaluator extremely simple and transparent.

### Turnover is the silent killer
Many strategies looked decent before costs and then became useless after commission. The best improvements I made weren’t about finding new signals, they were about reducing pointless trades:

- adding a **threshold** so the bot stays flat when the market move is tiny
- avoiding rapid flip-flopping in choppy periods
- accepting that “doing nothing” is often the best trade

### Risk is mostly a sizing problem
The volatility differences between stocks were huge and persistent. Without volatility scaling, a few high-vol names dominate the whole P&L (and dominate your drawdowns too). Vol scaling wasn’t just a “nice to have”, it was the difference between a strategy behaving sensibly vs being driven by a handful of instruments.

---

## 3.2 Quant / Market Learnings

### In this dataset, the best signal was the simplest one
From the market analysis, most of the structure was:

- weak pairwise correlation between stocks (pairs trading basically dead)
- weak and unstable single-stock momentum
- strong **market-level** short-horizon momentum (especially 1–2 day effects)

Once I accepted that, it made the “right” strategy direction way clearer: stop trying to be clever at the stock level and just trade the market regime carefully.

### Mean reversion wasn’t a free lunch
I expected at least some clean bounce-back after extreme moves, but the market more often showed **follow-through** rather than snapping back. That doesn’t mean mean reversion never works, it just wasn’t dominant at the daily horizon in this universe.

### Regimes matter more than indicators
The strategy didn’t fail because momentum “stopped existing”. It mostly failed in specific periods where the market got choppy and direction flipped often. So a lot of the edge comes from:

- recognising when conditions are good for the signal
- trading less when the regime is unclear

---

## 3.3 Process Learnings

### The fastest progress came from deleting ideas early
At the start I spent time exploring lots of different strategy styles. The turning point was getting ruthless about filtering:

- if a strategy didn’t survive costs, it was dead
- if it only worked in one small slice of time, it was suspicious
- if it needed heavy tuning, it was probably overfit

Once I started prioritising robustness over complexity, my iteration speed improved a lot.

### A small number of good plots beats “plot spam”
It’s really tempting to produce dozens of charts, but the most useful ones were the ones that directly answered a decision:

- “Is there any cross-asset structure?” (correlation matrix)
- “Is momentum real at the market level?” (market ACF / rolling ACF)
- “Does mean reversion actually show up?” (next-day scatter / bounceback extremes)
- “Is volatility mainly time-varying or stock-specific?” (vol distributions / extremes)

Everything else was mostly noise.

---

## 3.4 Biggest Mistakes

- **Over-testing fragile ideas early.**  
  I spent too long on strategies that were never going to survive the low-correlation structure and commission model.

- **Not focusing on churn control from day one.**  
  I initially treated costs as something to “add later”. In reality, costs decide what’s even feasible.

- **Trying to extract per-stock alpha in a market that didn’t support it.**  
  The data strongly suggested market-level structure was the main thing. I should’ve committed to that direction earlier.

---

## 3.5 What I’d Do Differently Next Time

- **Work backwards from the scoring function earlier.**  
  Since the score penalises volatility, I’d treat variance reduction and turnover reduction as first-class goals from the start.

- **Spend more time on “whipsaw damage control.”**  
  My strategy works well in clean regimes. The main weakness is chop. Next iteration I’d focus on better entry/exit smoothing (without increasing trading frequency).

- **Build a clearer “regime dashboard.”**  
  A few simple signals (volatility state, momentum strength, trend consistency) could make it easier to scale risk down when conditions are bad.

---

# 4) Conclusion

This Algothon ended up being less about inventing a fancy model and more about finding **one real edge** and making it **tradable under constraints**.

### What worked best
- Trading **market-level momentum** rather than trying to pick individual winners and losers.
- Using a **threshold** to avoid noise trading and reduce commission drag.
- Using **volatility scaling** so risk was spread more evenly across the universe.

### What didn’t work
- Cross-asset relative value ideas (pairs / cointegration), the correlation structure was simply too weak.
- Broad “fade extremes” mean reversion, the market often showed follow-through instead of snapping back.
- Anything that required frequent trading, costs quickly wiped out the edge.

### Final takeaway
In this environment, **robustness beats complexity**. The strategies that survive are the ones that:
- trade infrequently,
- size risk properly,
- and rely on structure that shows up repeatedly (not just once).

### Future work
If I were to iterate on this bot, I’d stay in the same general family (market regime + risk control) and focus on:
- better handling of choppy periods,
- more deliberate risk scaling across volatility regimes,
- and adding small, low-turnover “helper signals” (only if they improve stability without increasing churn).

---

## Repository Structure

- `main.py` - final submission bot (contains `getMyPosition`)
- `eval.py` - baseline evaluator (single run)
- `eval_full.py` - extended walk-forward + robustness tests
- `market_analyser.py` - plots to identify good strategies and eliminate weak ones
- `trade_analyser.py` - diagnostic tool to visualise the algorithm’s trades  
- `plots/` - research and diagnostics figures used in this write-up
- `images/` - team photos
