# Architecture

Mobile Service Suite follows **Clean Architecture** with a **Modular** brand
system, a **Service Layer**, and the **Repository Pattern**.

## Layers

```
┌─────────────────────────────────────────────────────────────┐
│ frontend/  React renderer (UI)                               │  Presentation
├─────────────────────────────────────────────────────────────┤
│ electron/  Main process + secure preload (IPC bridge)        │  Platform
├─────────────────────────────────────────────────────────────┤
│ core/application/   use-cases, services, ModuleRegistry      │  Application
│ core/domain/        entities, repository & service interfaces │  Domain
├─────────────────────────────────────────────────────────────┤
│ backend/            SQLite repositories, ADB/Fastboot adapters│  Infrastructure
│ modules/            pluggable brand & platform modules        │
│ tools/  drivers/    external tool + driver integrations       │
└─────────────────────────────────────────────────────────────┘
        shared/  constants & types used by every layer
```

### Dependency rule

Dependencies point **inward**. `core/domain` depends on nothing but `shared`.
`core/application` depends on `core/domain`. Infrastructure (`backend`,
`modules`, `tools`) depends on the domain interfaces — never the reverse. The UI
and infrastructure are interchangeable details behind the domain contracts.

## Key abstractions (defined in PHASE 1)

| Abstraction | File | Purpose |
| ----------- | ---- | ------- |
| `IRepository<T,Id>` | `core/domain/repositories/IRepository.ts` | Generic persistence contract (Repository Pattern) |
| `IDeviceDetectionService` | `core/domain/services/IDeviceDetectionService.ts` | Service Layer contract for device detection |
| `IBrandModule` | `core/domain/services/IBrandModule.ts` | Contract every pluggable brand/platform module implements |
| `ModuleRegistry` | `core/application/services/ModuleRegistry.ts` | Runtime registry — the extension point for new brands/tools |
| `Result<T,E>` | `shared/types/result.ts` | Explicit success/failure across service & IPC boundaries |
| `Device` | `core/domain/entities/Device.ts` | Central domain entity |

## Extensibility

To support a new brand or tool:

1. Create a module under `modules/<brand>/` that exports an object implementing
   `IBrandModule`.
2. Register it with the `ModuleRegistry` at startup.

No core files change. The smart tool recommendation engine (PHASE 22) simply
asks the registry which module matches a detected device.

## Security boundary

The renderer is fully isolated: `contextIsolation: true`, `sandbox: true`,
`nodeIntegration: false`. It talks to the main process only through the typed,
allow-listed bridge exposed in `electron/preload.ts`. See
[`SECURITY.md`](SECURITY.md).
