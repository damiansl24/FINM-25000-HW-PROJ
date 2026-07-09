# ML Trading Signal with Alpaca (Paper Trading Only)

A machine-learning trading signal built on **Alpaca** market data. It downloads 5
years of daily OHLCV, engineers the technical indicators from the assignment,
compresses them with **PCA**, trains a **Random Forest** to predict next-day
direction, backtests the signal against buy-and-hold, and submits
**paper-trading** orders through Alpaca.

> ⚠️ **PAPER TRADING ONLY — NO REAL MONEY IS USED.** Every order is routed to
> Alpaca's paper endpoint (`https://paper-api.alpaca.markets`).

## Project layout

```
.
├── src/                     reusable modules
│   ├── config.py            strategy parameters & output paths
│   ├── get_keys.py          load Alpaca paper keys from .env
│   ├── data_loader.py       Alpaca 5y daily OHLCV -> DataFrame
│   ├── indicators.py        the assignment's indicators (14 feature columns)
│   ├── strategies.py        standardize -> PCA(>=80%) -> Random Forest -> signal
│   ├── backtester.py        long-only, no-leverage backtest + trade log
│   ├── metrics.py           Total Return, CAGR, Sharpe, Sortino, Max DD, Win Rate
│   └── plotting.py          equity / drawdown / PCA-variance / signal charts
├── scripts/
│   ├── run_backtest.py      train + backtest + charts (saves the model)
│   └── run_paper_trade.py   submit a paper order from the latest signal
├── run_all.py               one command: backtest, then (optionally) paper trade
└── output/                  generated charts, CSVs, model, logs (git-ignored)
```

Dependencies and Alpaca keys are shared from the **repo root** (parent
`requirements.txt` and `.env`), the same way `hw2/` works.

## Indicators used

Exactly the set the assignment lists — one feature column each (14 total):

- **Trend:** SMA, EMA, MACD, ADX
- **Momentum:** RSI, Stochastic (%K), Williams %R
- **Volatility:** Bollinger Bands (%B), ATR
- **Volume:** OBV, CMF
- **Extras:** log returns, rolling mean, rolling std

## Setup

Dependencies and keys come from the **repo root**, exactly like `hw2/`.

```bash
# 1. from the repo root, install shared dependencies
pip install -r requirements.txt        # or:  uv pip install -r requirements.txt

# 2. keys live in the repo-root .env (create it if it doesn't exist yet)
cp .env.example .env                    # Windows:  copy .env.example .env
#    APCA_API_KEY_ID=your_paper_key_id
#    APCA_API_SECRET_KEY=your_paper_secret_key
```

This homework adds two packages the earlier homeworks didn't need — make sure the
**root `requirements.txt`** includes them:

```
scikit-learn
joblib
```

Get free paper keys from the **Paper Trading** dashboard at
[alpaca.markets](https://alpaca.markets) → **Generate New Keys**.

## Run it

```bash
# Full backtest + charts + metrics (saves output/model.joblib)
python scripts/run_backtest.py NVDA

# Submit a paper trade from the latest signal
python scripts/run_paper_trade.py            # acts on today's real signal
python scripts/run_paper_trade.py --demo     # forces one BUY so a trade shows for the video

# Or do both in one command
python run_all.py NVDA --demo
```

Outputs land in `output/`: `model.joblib`, `backtest_<TICKER>.csv`,
`trades_<TICKER>.csv`, `paper_trade.log`, and `output/charts/*.png`
(equity curve, drawdown, PCA variance, signal overlay).

## How the signal works

1. Build the 14 technical features from daily OHLCV.
2. Chronological 70/30 train/test split (no shuffling — it's a time series).
3. Standardize features, fit PCA on the training set, keep enough components to
   explain **≥80%** of variance.
4. Random Forest predicts **P(next-day return > 0)**.
5. **Long** when P > 0.60, otherwise **flat**. The backtest holds the position on
   the bar *after* the signal, so there's no look-ahead. All results are reported
   on the **out-of-sample** test window.

## Video checklist (3–6 min)

- [ ] `python scripts/run_backtest.py <TICKER>` running end-to-end
- [ ] The charts: **equity curve**, **drawdown**, **PCA variance**
- [ ] The printed **backtest results / metrics table**
- [ ] `python scripts/run_paper_trade.py --demo` printing the **signal + order**
- [ ] Your **Alpaca paper dashboard** with the executed trade / position
- [ ] You saying: **"This is paper trading only — no real money is used."**

> **Video:** _add your unlisted YouTube link here_

## Notes

- Free Alpaca data uses the **IEX** feed (`ALPACA_DATA_FEED=iex`, the default).
  Set `sip` only if you have a paid data subscription.
- Educational project, not investment advice. A backtest does not predict future
  returns. Nothing here touches real money — all orders go to the paper endpoint.
