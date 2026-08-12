# Mobile Service Suite

A professional cross-platform **desktop application for mobile phone repair
technicians**. It brings device detection, ADB/Fastboot management, firmware,
drivers, external tools, backup, protection **diagnostics**, repair sessions,
logs and reports together in one interface.

> **Ethics & scope:** This suite **diagnoses** device protection (FRP, factory
> reset protection, account locks) and guides technicians to the **official**
> account-recovery / proof-of-ownership paths. It does **not** implement or
> bundle any bypass of FRP, Google/Samsung/Xiaomi/Huawei accounts, or Apple
> Activation Lock. See [`docs/SECURITY.md`](docs/SECURITY.md).

## Status

| Phase | Description | State |
| ----- | ----------- | ----- |
| **PHASE 1** | Project Setup | ✅ complete |
| **PHASE 2** | Electron + React shell | ✅ complete |
| **PHASE 3** | Dashboard | ✅ complete |
| **PHASE 4** | SQLite database | ✅ complete |
| **PHASE 5** | USB / device detection | ✅ complete |
| **PHASE 6** | ADB Manager | ✅ complete |
| **PHASE 7** | Fastboot Manager | ✅ complete |
| **PHASE 8** | Driver Manager | ✅ complete |
| **PHASE 9** | Tool Manager | ✅ complete |
| **PHASE 10** | Brand Modules | ✅ complete |
| PHASE 11 | Firmware Manager | ⏳ pending |
| … | (see the development prompt) | ⏳ pending |

PHASE 1 delivered the tooling foundation and architecture skeleton (Electron +
React + TypeScript strict, Tailwind, Vite, ESLint, Prettier, Vitest, and the
Clean/Modular layers). PHASE 2 adds the running application shell: hash-based
routing, the sidebar + top-bar layout over all 13 sections, dark/light theming,
and a three-language i18n system (English / Arabic with RTL / Italian). PHASE 3
builds the main **Dashboard**: device overview, information grid, protection &
status panel (ADB / Fastboot / Bootloader / OEM Lock / FRP — reported only),
quick actions, and a connection checklist for the no-device state. It runs
against a swappable `useDeviceStatus` hook; live ADB/Fastboot detection arrives
in PHASE 5. PHASE 4 adds the **SQLite persistence layer** (better-sqlite3): a
forward-only migration runner, the full 11-table schema (users, devices,
repair_sessions, tools, drivers, firmwares, operations, logs, backups, reports,
settings), and typed repositories (Repository Pattern) exposed through an
`AppDatabase` facade. PHASE 5 adds **live device detection**: ADB and Fastboot
clients over a testable `CommandRunner` abstraction, pure output parsers, and a
`DeviceDetectionService` that probes USB and enriches devices (brand, model,
Android version, battery, RAM, bootloader/OEM state — FRP is diagnosed only).
It is wired to the Dashboard over the secure IPC bridge, degrading gracefully
when `adb`/`fastboot` are not installed. PHASE 6 adds the **ADB Manager** page:
reboot (system/recovery/bootloader), connect/disconnect, install/uninstall APK,
list packages, push/pull files, shell, logcat and screenshot — each input
validated in the service and every sensitive action gated behind a confirmation
dialog, with a live output console. PHASE 7 adds the **Fastboot Manager**: read
variables (single / all), reboot (system/bootloader/recovery/fastbootd), and the
destructive bootloader operations — unlock, lock, erase and flash — each behind
a strong confirmation. Bootloader lock state is changed only as an explicit
technician action; account protection is never bypassed. PHASE 8 adds the
**Driver Manager**: a data-driven catalog (ADB, Fastboot, Google USB, Samsung,
Qualcomm, MediaTek, Unisoc) with real installed-status detection via `pnputil`
on Windows, an "Open Device Manager" action, and official download links. The
suite never installs drivers automatically. PHASE 9 adds the **Tool Manager**: a
catalog of CLI and external tools (ADB, Fastboot, Odin, Mi Flash, QFIL, SP Flash
Tool, ResearchDownload, UpgradeDownload, HiSuite) with version detection, a
persisted per-tool path (SQLite `tools` table), and an External Tool Launcher
that runs the technician's own installed copy and records the launch — it never
bundles, modifies, or circumvents commercial software. PHASE 10 delivers the
**brand modules**: 15 brand + 3 chipset-platform modules under `modules/`, each
implementing `IBrandModule` and registered in the `ModuleRegistry` — proving the
extension point (a new brand is a data-only module, no core change). They power
the **smart tool recommendation** engine (`recommendToolsForDevice`), surfaced
as a "Recommended Tools" panel on the Dashboard. Other sections still show
placeholders.

## Technology stack

- **Electron** — desktop shell (secure: context isolation, sandbox, no node
  integration in the renderer)
- **React + TypeScript** (strict mode) — renderer UI
- **Vite** — renderer bundler / dev server
- **Tailwind CSS** — dark-first UI
- **Vitest + Testing Library** — tests
- **SQLite** — local persistence (added in PHASE 4)
- **ADB / Fastboot** and **Python** helpers — integrated in later phases

## Architecture

Clean Architecture + Modular Architecture with a Service Layer and the
Repository Pattern. See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

```
mobile-service-suite/
├── electron/     Electron main process + secure preload bridge
├── frontend/     React renderer (components, pages, hooks, styles)
├── core/         Domain + application layers (entities, interfaces, registry)
├── backend/      Infrastructure (SQLite repositories, services) — PHASE 4+
├── modules/      Pluggable brand & platform modules (Samsung, Xiaomi, …)
├── shared/       Constants & types shared across all layers
├── tools/        External-tool integrations (Odin, Mi Flash, QFIL, …)
├── drivers/      Driver metadata & checks
├── tests/        Unit & integration tests
├── docs/         Documentation
├── logs/ reports/ Runtime output (git-ignored)
```

New brands or tools are added by dropping a module under `modules/` and
registering it — **no changes to the core system are required**.

## Getting started

```bash
cd mobile-service-suite
npm install       # install dependencies
npm run typecheck # strict TypeScript check
npm test          # run the test suite
npm run dev       # launch the app (Electron + Vite) on a desktop machine
```

> `npm run dev` requires a desktop environment with a display. Type-checking,
> linting and tests run in any headless environment / CI.

## Documentation

- [Installation](docs/INSTALLATION.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Development](docs/DEVELOPMENT.md)
- [Security & ethics](docs/SECURITY.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [User guide](docs/USER_GUIDE.md)

## License

MIT
