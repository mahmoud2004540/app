# SECURITY.md

## Current posture

| Control | State |
|---|---|
| Telegram token / chat id | GitHub Secrets + `.env` (not in source) |
| Private keys / wallet seed | **Not present** — do not add plaintext keys |
| Password hashing | N/A (no user DB) |
| TLS | Telegram + HTTPS public market APIs |
| Client trust | Telegram text is only a command; balances are not client-set |
| Audit | Actions logs + `journal/*.jsonl` |
| Dependency scan | Not automated |
| Claimed production-ready exchange | **No** |

## Threats that matter today

1. Leaked `TELEGRAM_TOKEN` → attacker impersonates `@Bighotwelcome_bot`.
2. Wrong `TELEGRAM_CHAT_ID` → signals go to another chat (already seen operationally).
3. Public strategy parameters → copycats; not a secret, but don’t put live API keys in the same repo.
4. Prompt injection via market names is low risk; still validate market/timeframe enums (`telegram_bot.py` already does).
5. Supply-chain: pin Actions versions; don’t curl-pipe install.

## Rules (from master prompt — adopted)

- Do not store API keys, JWT secrets, DB passwords, or private keys in git.
- Do not let the client control financial state.
- Do not give AI/scanner withdraw or ledger-write rights.
- Do not use fake deposits/balances/trades in any path marketed as live.
- Money / wallet / withdrawal / live trading / admin features are **critical**: tests + validation required.
- Do not call the product production-ready until security audit, pentest, load test, financial reconciliation, DR, legal review, and infra review exist.

## Phase 1 security work (after approval)

- Document secret names in `.env.example` only.
- Keep `FEATURE_LIVE_BROKER` default off.
- No new endpoints that accept user_id / balance from the client.

## Future (not Phase 1)

- Telegram allowlist + rate limit
- Hashed exchange API secrets (withdraw disabled by default)
- Structured audit log
- Dependabot + SAST in Actions
- Kill switch restricted to ops
