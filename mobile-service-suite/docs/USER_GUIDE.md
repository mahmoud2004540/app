# User Guide

> This guide grows with each phase. As of **PHASE 1**, the application is a
> foundation only — the screens below describe the planned experience.

## Overview

Mobile Service Suite is organized around a left **sidebar**:

- **Dashboard** — connected device overview and quick actions
- **Devices** — detection and detailed device information
- **ADB** — Android Debug Bridge operations
- **Fastboot** — bootloader-mode operations
- **Firmware** — import, verify and manage firmware
- **Tools** — detect and launch external tools (Odin, Mi Flash, QFIL, …)
- **Drivers** — check and manage USB/ADB/Fastboot drivers
- **Protection** — FRP / account-lock **diagnostics** and official recovery
  guidance
- **Backup** — contacts, SMS, media and supported app data
- **Repair Sessions** — per-customer repair records
- **Logs** — searchable audit log of every operation
- **Reports** — generate PDF repair reports
- **Settings** — language (Arabic / English / Italian), theme, paths

## Safety

Every destructive action (erase, unlock, flash, uninstall) requires an explicit
confirmation. The suite never bypasses account protection — it detects it and
points you to the official recovery process. See
[`SECURITY.md`](SECURITY.md).

## Getting started (developers)

See [`INSTALLATION.md`](INSTALLATION.md).
