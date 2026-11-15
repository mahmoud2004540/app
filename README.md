# Trading Deals Bot

A Python bot that scans crypto, stock and forex markets, scores trade setups with automated technical analysis, and sends the best ones to Telegram. Works as a command-line tool, a Telegram bot, or a scheduled GitHub Actions job with no server.

[العربية](README.ar.md)

> ⚠️ Educational project. This is automated technical analysis, not financial advice. Trading involves real risk.

## Features

- **Three markets**: crypto (BTC-USD…), stocks (AAPL…), forex (EURUSD=X…)
- **Technical analysis**: EMA 9/21/50 trend, RSI, MACD, momentum, volume flow
- **Large-money detection**: flags unusual inflows (MFI + abnormal volume) and explains why
- **Trend-aware scoring**: each setup gets a 0–100 confidence score and never bets against a strong trend
- **Risk management**: entry, stop-loss, target and risk/reward from volatility (ATR); position size from a fixed % risk per trade
- **Higher-timeframe confirmation** and a minimum-confidence filter for cleaner signals
- **Backtesting**: win rate, profit factor and total return in R multiples on historical data
- **Multi-school confluence analysis** for a single asset (technical, price structure, volume, quantitative, sentiment) with a minimum 1:2 risk/reward gate
- **Live prices without API keys**: Coinbase for crypto with Yahoo Finance fallback; Yahoo Finance for stocks and forex
- **Telegram alerts every 4 hours** via GitHub Actions, with the token stored as an encrypted secret

## Quick start

Python 3.10+

```bash
pip install -r requirements.txt

python cli.py                                   # best crypto setups, 1h
python cli.py --market stocks --timeframe 1d --top 5
python cli.py --market all --direction buy
python analyze.py --symbol BTC-USD --market crypto --timeframe 1h
python backtest.py --market crypto
python demo.py                                  # offline demo with synthetic data
```

| Option | Values | Default |
|---|---|---|
| `--market, -m` | crypto · stocks · forex · all | crypto |
| `--source, -s` | yfinance · binance | yfinance |
| `--timeframe, -t` | 1m · 5m · 15m · 1h · 1d | 1h |
| `--top, -n` | number | 5 |
| `--direction, -d` | any · buy · sell | any |

## Telegram

**Without a server (GitHub Actions):** create a bot with @BotFather, get your chat ID from @userinfobot, add `TELEGRAM_TOKEN` and `TELEGRAM_CHAT_ID` as repository secrets, then run the *deals digest* workflow from the Actions tab. The schedule is the `cron` line in `.github/workflows/deals-digest.yml`.

**As an interactive bot:**

```bash
cp .env.example .env      # set TELEGRAM_TOKEN
./run_bot.sh
```

Commands: `/best crypto 1h`, `/crypto`, `/stocks`, `/forex`, `/best all`, `/buy crypto`.

Also ships with a `Dockerfile` and `Procfile` for Railway, Render or any VPS.

## How scoring works

Each symbol gets bullish and bearish points from trend (EMA order, highest weight), RSI read in the direction of the trend, MACD, momentum and volume. Final score = bull − bear (positive = buy, negative = sell). Stop-loss and target are ATR multiples, configurable in `deals_bot/analyzer.py`. Watchlists and risk settings live in `config.py`.

## Project structure

```
cli.py              command-line interface
telegram_bot.py     Telegram interface
analyze.py          confluence analysis
backtest.py         backtesting
config.py           watchlists and settings
deals_bot/
  indicators.py     technical indicators (pure Python)
  analyzer.py       scoring engine
  providers.py      market data (yfinance / Binance / Coinbase)
  formatter.py      output formatting
tests/              offline tests
```

## Tests

```bash
pip install pytest
pytest -q
```

Tests use synthetic data and need no internet connection.
