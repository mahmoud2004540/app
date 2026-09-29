# ROADMAP.md

Mapped from the master platform prompt onto **existing** `app` (signal bot).  
Phase numbers below are **this project’s** phases, not a promise that an exchange ships in weeks.

Status key: `done` = already in repo · `next` = Phase 1 after approval · `later` · `gated` (legal/security)

| Master prompt phase | Mapping | Status |
|---|---|---|
| Foundation | Docs, flags, connector interface, env contract | next |
| Authentication | Telegram identity allowlist + optional multi-chat | later |
| Database | SQLite then Postgres journal | later |
| Wallet/Ledger | Paper ledger with Decimal first; custody gated | later / gated |
| Market data | Unify providers | next–later |
| Trading engine | Keep analysis; live orders via official exchange APIs only | later |
| Trading UI | Improve dashboard; Next.js terminal later | later |
| WebSocket | Not required for Telegram digest | later |
| Risk engine | Extract `risk_engine` + kill switch | later |
| Admin | Ops commands + Actions; full admin panel later | later |
| AI | Current scanners stay analysis-only | done / harden |
| Backtesting | `backtest.py` exists | done / improve |
| Copy trading | gated | gated |
| Security hardening | secrets already external; add allowlist + audit | next–later |
| Production deploy | Actions + Docker today; not “production exchange” | partial |

## Phase 1 — Foundation (after your approval)

Goal: freeze architecture, add extension points, **zero change to signal math**.

1. Feature flags in env (`FEATURE_PAPER`, `FEATURE_ICT`, `FEATURE_LIVE_BROKER=off`).
2. `deals_bot/connectors.py` protocol wrapping current providers (read-only).
3. Expand `.env.example` (token, chat id, flags) — no secrets in git.
4. Link README to ARCHITECTURE / ROADMAP / SECURITY.
5. Tests that flags default to current behavior.

No database migration. No API rewrite. No fake production balances.

## Later phases (not started)

- Phase 2: Telegram user allowlist, command rate limit, structured errors.
- Phase 3: persist journal in SQLite; keep JSON import.
- Phase 4: Decimal paper ledger + reconciliation job vs fills file.
- Phase 5: official-API live broker behind `FEATURE_LIVE_BROKER`, user keys hashed, withdraw permission off.
- Phase 6+: web terminal, multi-user, copy trading — only with compliance layer.

Do not advance a phase while the previous one is broken.
