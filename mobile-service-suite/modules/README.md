# Brand & Platform Modules

Each subdirectory is a **pluggable module** for a phone brand (Samsung, Xiaomi,
Huawei, …) or chipset platform (Qualcomm, MediaTek, Unisoc). A module exports an
object implementing [`IBrandModule`](../core/domain/services/IBrandModule.ts)
and is added to the app by registering it with the
[`ModuleRegistry`](../core/application/services/ModuleRegistry.ts).

Adding a new brand or tool **never requires changes to the core system** — this
is the Modular Architecture extension point.

Modules are implemented starting in **PHASE 10**. The directories are present
now so the structure and contracts are established from PHASE 1.
