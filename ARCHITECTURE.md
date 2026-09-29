# ARCHITECTURE.md — Trading Deals Bot → Platform Path

**Platform working name:** Deals Bot / `@Bighotwelcome_bot`  
**Repository:** `mahmoud2004540/app`  
**Date:** 2026-09-29  
**Rule:** do not destroy existing work. This document maps *what exists* to *what the master platform prompt asks for*, without rewriting the engine.

---

## CURRENT SYSTEM

The repository is **not** an exchange. It is a **signal + paper-trading system**:

1. Fetch market data (Coinbase / Yahoo Finance / Binance public APIs).
2. Score setups with technical + ICT + confluence + risk rules (thresholds measured by backtest).
3. Send the best setups to Telegram (GitHub Actions cron + optional long-running bot).
4. Optionally simulate fills in a local paper account (`journal/paper_account.json`).

### Stack

| Layer | Actual |
|---|---|
| Language | Python 3.10+ / 3.11 |
| UI | Telegram commands + `dashboard.html` / `dashboard.py` |
| Data | `yfinance`, Coinbase public REST, Binance public REST |
| Persistence | JSON / JSONL under `journal/` (no PostgreSQL, no Prisma, no Redis) |
| Auth | Telegram token + chat id in GitHub Secrets / `.env` |
| Compute | GitHub Actions workflows + local CLI + Docker (`telegram_bot.py`) |
| Tests | `pytest` under `tests/` (offline synthetic + some live-marked) |

### Runtime surfaces

| Entry | Role |
|---|---|
| `cli.py` | Rank deals from CLI |
| `telegram_bot.py` | Interactive Telegram (`/best`, `/crypto`, `/stocks`, `/forex`, `/buy`) |
| `send_digest.py` | Scheduled digest / entry alerts |
| `ict_bot.py` | ICT / smart-money scanner |
| `paper_bot.py` | Paper account loop |
| `analyze.py` | Single-symbol confluence report |
| `backtest.py` | Historical strategy measurement |
| `dashboard.py` | Local HTML dashboard |
| `.github/workflows/*` | digest, watcher, ICT, paper, report, telegram-diag |

### Engine (`deals_bot/`)

- `providers.py` — market data connectors (not a unified exchange interface yet)
- `indicators.py` — EMA/SMA/RSI/MACD/ATR/volume/stoch/MFI (pure Python)
- `analyzer.py` — classic scoring
- `strategy.py` — measured trend-pullback path (score ≥85, EMA200, MACD, fib 0.5–0.786, vol surge, RR 1.5)
- `ict.py` — ICT scanner
- `confluence.py` — multi-school vote
- `risk_engine.py` — position size / portfolio constraints
- `paper_trading.py` + `journal.py` — simulated book, not a ledger
- `formatter.py` — Telegram / CLI text

### What already matches parts of the master prompt

- Multi-market scan (crypto + stocks + forex)
- AI-style **analysis layer** with reasons, invalidation, confidence (not auto-execution of live funds)
- Backtest + paper trading
- Risk sizing (`RISK_PER_TRADE`, correlation filter, streak warning)
- Kill-adjacent flags (`ALERT_ONLY`, feature-like config in `config.py`)
- Educational disclaimer (no 100% / zero-loss claims)
- Secrets not committed (`.env.example` only; Actions secrets)

### What is explicitly **not** present

Matching engine, double-entry ledger, hot/cold wallets, deposits, withdrawals, user accounts, KYC, admin RBAC, Next.js terminal, WebSocket fan-out, fees/VIP, copy trading, social trading, API keys for third-party trading, HSM/KMS.

---

## PROBLEMS

1. **Product mismatch.** Master prompt describes a licensed-style exchange. This repo is a research/signal bot. Treating it as an exchange on day one would destroy working signal code.
2. **Single-user delivery.** One `TELEGRAM_CHAT_ID`. No multi-user auth, sessions, or RBAC.
3. **No durable database.** JSON files race under concurrent Actions; no ACID, no audit ledger.
4. **No financial custody.** Paper balances are files. There is no wallet, no private-key architecture — and there must not be keys in git.
5. **Connectors are ad-hoc.** Coinbase/Yahoo/Binance helpers are not a single `ExchangeConnector` interface (`getTicker`, `createOrder`, …).
6. **Telegram interactive bot ≠ scheduled digest.** `telegram_bot.py` is a thin CLI wrapper; production alerts live in Actions + `send_digest.py`. Two personalities.
7. **Observability is logs-only.** No metrics, tracing, health endpoint, reconciliation job.
8. **Security surface is small but real.** Token in env is correct; there is no rate-limit on incoming Telegram commands; no allowlist beyond chat id in scheduled jobs; public repo means strategy parameters are public.
9. **Legal/compliance.** Building deposits/withdrawals/matching implies financial services licensing. Software existence ≠ legal permission to operate an exchange.
10. **Floating point.** Python `float` is used in analysis. Fine for signals; not acceptable for a real ledger (need `Decimal`).

---

## TARGET ARCHITECTURE

Grow **around** the existing engine. Do not replace `deals_bot/` with a greenfield NestJS rewrite.

```
                    ┌─────────────────────────────┐
                    │  Delivery                   │
                    │  Telegram / CLI / Dashboard │
                    └─────────────┬───────────────┘
                                  │
                    ┌─────────────┴───────────────┐
                    │  Analysis Layer (KEEP)      │
                    │  deals_bot/*  strategy/ICT  │
                    │  NO fund movement           │
                    └─────────────┬───────────────┘
                                  │ recommendations only
          ┌──────────────────────┼───────────────────────┐
          ┴                       ┴                       ┴
   Paper Broker             Live Broker*            Admin/Ops
   (existing journal)       Exchange connectors     Kill switch
                            official APIs only      feature flags
```

*Live broker is **optional, later, feature-flagged**, user-held exchange API keys (hashed), never custody of user crypto in v1–v6.

### Proposed modules (incremental)

| Module | When | Notes |
|---|---|---|
| Analysis service | now | current `deals_bot` |
| Feature flags | Phase 1 | env + `config.py` already partial |
| Connector interface | Phase 1–2 | wrap existing providers |
| SQLite/Postgres journal | Phase 3 | replace JSON when paper races appear |
| User/session (Telegram identity) | Phase 2 | still not a full website |
| Risk + kill switch service | Phase 4 | extract from config/strategy |
| Web terminal (Next.js) | much later | only after API exists |
| Custody / matching / KYC | **out of scope until legal review** | Compliance Configuration Layer first |

### Option A vs Option B

**Option A — Signal platform (recommended now)**  
Keep Python engine. Add API + flags + connector interface + better journal + web dashboard later. Users trade on Binance/Bybit themselves (or paper).  
Trade-offs: no in-house matching; fastest path; lowest legal risk; preserves backtested strategy.

**Option B — Full exchange**  
NestJS + Postgres + Redis + matching + wallets.  
Trade-offs: 12–24+ months, custody risk, licensing, would freeze signal work. Rejected until Option A is stable and a compliance review exists.

**Decision:** Option A. Master-prompt exchange items stay on the roadmap as *gated* phases, not Phase 1 code.

---

## SECURITY MODEL

- Secrets only in GitHub Actions Secrets / host env / future Secrets Manager.
- Analysis layer cannot call withdraw / transfer.
- Client (Telegram user text) never sets balances or permissions.
- AI / scanner output is advisory; paper or live execution goes through an explicit broker adapter with limits + kill switch.
- Do not claim production-ready until pentest, load test, reconciliation, DR, and legal review exist.

See `SECURITY.md`.

---

## SCALING STRATEGY

Today: one Actions runner every N minutes scanning Coinbase universe (~hundreds of pairs) is enough for one user.

Next steps if users grow:

1. Cache OHLCV (Redis or on-disk parquet) instead of refetching every job.
2. Split scan shards by symbol range.
3. Move digest from Actions to a small always-on worker only if latency requires it.
4. Introduce Postgres when more than one actor writes the journal.

---

## MIGRATION PLAN

1. Document (this file + ROADMAP + SECURITY) — **this commit**.
2. Phase 1 Foundation: flags, connector protocol, env contract, no behavior change to signals.
3. Only then Auth / DB / wallet-shaped modules, each behind flags.
4. Never force-push; feature branches; `feat:` / `docs:` / `security:` commits.
