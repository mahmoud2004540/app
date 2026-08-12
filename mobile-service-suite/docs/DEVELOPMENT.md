# Development Guide

## Scripts

| Command | Description |
| ------- | ----------- |
| `npm run dev` | Run Vite + Electron together with hot reload (needs a display) |
| `npm run dev:renderer` | Run only the Vite dev server |
| `npm run build` | Build renderer + Electron main process |
| `npm run typecheck` | Strict TypeScript check (renderer + electron) |
| `npm run lint` | ESLint (`.ts`/`.tsx`, zero warnings allowed) |
| `npm run format` | Format with Prettier |
| `npm test` | Run the Vitest suite once |
| `npm run test:watch` | Watch-mode tests |
| `npm run test:coverage` | Tests with V8 coverage |

## Conventions

- **TypeScript strict mode** everywhere, including
  `noUncheckedIndexedAccess` and `exactOptionalPropertyTypes`.
- **Path aliases**: `@core/*`, `@shared/*`, `@modules/*`, `@frontend/*`
  (configured in `tsconfig.json`, `vite.config.ts`, and `vitest.config.ts`).
- The **domain layer never imports infrastructure**. Depend on interfaces in
  `core/domain`, implement them in `backend`/`modules`.
- Every phase must build, type-check, lint, and pass tests before the next
  phase begins.

## Phased delivery

Development follows the 19 phases in the project prompt. Each phase: explain →
create files → write code → install deps → run → test → fix → verify → continue.
The current phase is tracked in the README status table.

## Adding a brand module (example)

```ts
// modules/samsung/index.ts
import type { IBrandModule } from '@core/domain/services/IBrandModule';

export const samsungModule: IBrandModule = {
  id: 'samsung',
  displayName: 'Samsung',
  recommendedTools: ['odin'],
  matches: (v) => v.toLowerCase().includes('samsung'),
};
```

Then register it with the `ModuleRegistry` at startup. The core is untouched.
