# Troubleshooting

## Setup / build

**`npm install` fails behind a proxy or offline**
Ensure network access to the npm registry. Native modules used in later phases
(e.g. SQLite) require build tools on some platforms.

**`npm run dev` shows a blank window or exits immediately**
`npm run dev` needs a graphical display. In headless environments (CI,
containers) use `npm run typecheck` and `npm test` instead.

**Type errors after adding a file**
Confirm the file lives under a path included by `tsconfig.json` and uses the
`@core` / `@shared` / `@modules` / `@frontend` aliases rather than long relative
paths.

## Device connectivity (later phases)

The Dashboard's "device not detected" panel will walk through:

- USB cable check
- USB port check
- Driver check
- ADB check
- Fastboot check

These live diagnostics are implemented starting in PHASE 5.

## Reporting a problem

Open an issue with: OS + version, Node version (`node -v`), the command you ran,
and the full error output.
