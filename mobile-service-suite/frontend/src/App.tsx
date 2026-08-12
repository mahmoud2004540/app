import { useEffect, useState } from 'react';
import { APP } from '@shared/constants/app';
import type { AppInfo } from '../../electron/preload';

/**
 * PHASE 1 placeholder screen.
 *
 * Confirms the Electron ⇄ React ⇄ shared-core wiring works end to end. The full
 * dashboard, sidebar, and feature pages are built in later phases (PHASE 3+).
 */
export function App(): JSX.Element {
  const [info, setInfo] = useState<AppInfo | null>(null);

  useEffect(() => {
    // window.mss only exists inside Electron; fall back gracefully in the browser.
    if (typeof window !== 'undefined' && window.mss) {
      void window.mss.getAppInfo().then(setInfo);
    }
  }, []);

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 p-8">
      <header className="text-center">
        <h1 className="text-3xl font-bold tracking-tight text-brand-200">{APP.NAME}</h1>
        <p className="mt-2 text-slate-400">{APP.DESCRIPTION}</p>
      </header>

      <section className="w-full max-w-md rounded-xl border border-surface-border bg-surface-raised p-6 shadow-lg">
        <div className="flex items-center justify-between">
          <span className="text-sm text-slate-400">Version</span>
          <span className="font-mono text-slate-100">{info?.version ?? APP.VERSION}</span>
        </div>
        <div className="mt-3 flex items-center justify-between">
          <span className="text-sm text-slate-400">Status</span>
          <span className="rounded-full bg-status-good/15 px-3 py-1 text-xs font-medium text-status-good">
            {info?.phase ?? 'PHASE 1 — Project Setup'}
          </span>
        </div>
        <div className="mt-3 flex items-center justify-between">
          <span className="text-sm text-slate-400">IPC bridge</span>
          <span className="text-xs text-slate-300">
            {info ? 'connected' : 'browser preview (no Electron)'}
          </span>
        </div>
      </section>

      <footer className="text-xs text-slate-500">
        Foundation ready — device detection, ADB, Fastboot and tooling arrive in the next phases.
      </footer>
    </div>
  );
}
