# Security & Ethics

## Ethical scope (non-negotiable)

Mobile Service Suite is a **diagnostic and workflow** tool for legitimate repair
work. It **does not** implement, bundle, or automate any of the following:

- FRP (Factory Reset Protection) bypass
- Google / Samsung / Xiaomi accounts or Huawei ID removal or bypass
- Apple Activation Lock bypass

For protected devices the suite **detects and reports** the protection state and
then guides the technician to the **official** recovery / proof-of-ownership
process provided by the device vendor. This is the only supported path.

The suite never stores Google, Apple, bank, or private account passwords.

## Application security

- **Context isolation** — the renderer runs isolated from Node.js.
- **Sandbox** — the renderer process is sandboxed.
- **No node integration** in the renderer.
- **Typed IPC allow-list** — the renderer can only call the specific channels
  exposed in `electron/preload.ts`; it never receives raw `ipcRenderer`.
- **Content Security Policy** — no remote scripts, styles, or network origins.
- **Input validation & command sanitization** — every ADB/Fastboot/tool command
  is validated before execution (implemented with those features in later
  phases).
- **Confirmation dialogs** for every destructive operation (erase, unlock,
  flash, uninstall).
- **Role-based permissions** — Admin / Technician / Viewer (PHASE 18).
- **Audit logging** of every operation (PHASE 15).
- **Encrypted storage** for sensitive local data (PHASE 13/17).

## Reporting

Security concerns should be reported to the project maintainers before public
disclosure.
