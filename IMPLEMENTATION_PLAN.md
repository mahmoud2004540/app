# IMPLEMENTATION PLAN

## CURRENT SYSTEM

Python signal bot: market fetch → indicators → scored setups (trend / ICT / confluence) → Telegram + paper JSON journal. GitHub Actions for schedules. Docker runs `telegram_bot.py`. Proven connectivity: `@Bighotwelcome_bot` → private chat Mahmoud (diag message_id 508, 2026-09-29).

## PROBLEMS

See ARCHITECTURE.md. Headline: the master prompt is an exchange; the repo is an advisory bot. Rewriting would delete a backtested engine.

## TARGET ARCHITECTURE

Option A: keep `deals_bot` as the analysis layer. Add flags, connector interface, later DB/paper ledger. Live custody and matching are gated.

## PHASE 1 (awaiting approval)

**Goal:** Foundation only. Do not change `TREND_*` / ICT thresholds.

### Files to change (proposed)

| File | Change |
|---|---|
| `.env.example` | Document flags + `TELEGRAM_CHAT_ID` |
| `config.py` | Read feature flags from env; defaults = current behavior |
| `deals_bot/connectors.py` | **new** read-only protocol + adapters over existing providers |
| `deals_bot/providers.py` | Call adapters internally or re-export (no fetch behavior change) |
| `README.md` | Link architecture docs; keep educational disclaimer |
| `tests/test_feature_flags.py` | **new** defaults on |
| `ARCHITECTURE.md` `ROADMAP.md` `SECURITY.md` | added this commit |

### Database changes

None.

### API changes

None. No REST yet.

### Security considerations

- Flags default off for anything live.
- Still no keys in git.
- Analysis remains non-authoritative for funds.

### Test plan

- Existing `pytest -q` must stay green.
- New tests: flags default preserve `ALERT_ONLY` / paper paths.
- No live network required.

## After approval

Implement Phase 1 on `docs/platform-architecture` (or a `feat/foundation` follow-up), then PR into `main`.
