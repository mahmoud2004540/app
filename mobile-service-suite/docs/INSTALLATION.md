# Installation

## Requirements

- **Node.js** ≥ 18 and npm
- A desktop OS (Windows / macOS / Linux) to run the Electron app
  (type-checking, linting and tests also run headless / in CI)
- Later phases additionally use **ADB**, **Fastboot**, and **Python 3** for
  device operations

## Developer setup

```bash
git clone <repository-url>
cd mobile-service-suite
npm install
```

Verify the toolchain:

```bash
npm run typecheck   # strict TypeScript, no emit
npm run lint        # ESLint
npm test            # Vitest
```

Run the app during development (needs a display):

```bash
npm run dev
```

This starts the Vite dev server for the renderer and launches Electron pointed
at it, with hot reload.

## Production build

```bash
npm run build       # builds renderer (Vite) + main process (tsc)
```

A signed Windows installer (`MobileServiceSuite.exe`) with desktop shortcut,
Start-menu entry, uninstaller and auto-update is produced by the packaging
pipeline added in **PHASE 19**.
