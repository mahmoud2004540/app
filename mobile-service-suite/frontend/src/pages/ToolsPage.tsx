import { useCallback, useEffect, useState } from 'react';
import {
  Wrench,
  RefreshCw,
  Play,
  FolderOpen,
  FolderCog,
  BadgeCheck,
  ExternalLink,
  ShieldCheck,
} from 'lucide-react';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { StatusPill, type StatusTone } from '../components/ui/StatusPill';
import { useI18n } from '../i18n/I18nProvider';
import type { TranslationKey } from '../i18n/keys';
import type { ToolStatus } from '@shared/types/tool';

function statusView(t: ToolStatus): { tone: StatusTone; key: TranslationKey } {
  if (t.installed === 'yes') return { tone: 'good', key: 'drivers.statusInstalled' };
  if (t.installed === 'no') return { tone: 'neutral', key: 'drivers.statusNotInstalled' };
  return { tone: 'neutral', key: 'drivers.statusUnknown' };
}

export function ToolsPage(): JSX.Element {
  const { t } = useI18n();
  const bridge = typeof window !== 'undefined' ? window.mss : undefined;

  const [tools, setTools] = useState<ToolStatus[]>([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');

  const refresh = useCallback(async () => {
    if (!bridge) return;
    setLoading(true);
    try {
      const report = await bridge.tools.list();
      setTools(report.tools);
    } finally {
      setLoading(false);
    }
  }, [bridge]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const openUrl = (url: string): void => {
    if (bridge) void bridge.system.openExternal(url);
    else if (typeof window !== 'undefined') window.open(url, '_blank', 'noopener');
  };

  const changePath = useCallback(
    async (key: string) => {
      if (!bridge) return;
      const picked = await bridge.dialog.openFile([{ name: 'Executable', extensions: ['exe', ''] }]);
      if (!picked) return;
      const res = await bridge.tools.setPath(key, picked);
      setMessage(res.ok ? `${key}: ${picked}` : `${key}: ${res.error}`);
      await refresh();
    },
    [bridge, refresh],
  );

  const run = useCallback(
    async (key: string) => {
      if (!bridge) return;
      const res = await bridge.tools.launch(key);
      setMessage(res.ok ? `${key}: launched` : `${key}: ${res.error}`);
    },
    [bridge],
  );

  const checkVersion = useCallback(
    async (key: string) => {
      if (!bridge) return;
      const res = await bridge.tools.checkVersion(key);
      setMessage(res.ok ? `${key}: v${res.value}` : `${key}: ${res.error}`);
      await refresh();
    },
    [bridge, refresh],
  );

  return (
    <div className="mx-auto max-w-6xl space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-500/10 text-brand-600 dark:bg-brand-500/15 dark:text-brand-200">
          <Wrench size={22} />
        </div>
        <div className="flex-1">
          <h1 className="text-2xl font-semibold">{t('nav.tools')}</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">{t('tools.subtitle')}</p>
        </div>
        <Button variant="secondary" onClick={() => void refresh()} disabled={loading}>
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          {t('adb.refresh')}
        </Button>
      </div>

      <div className="flex items-start gap-3 rounded-xl border border-status-info/30 bg-status-info/10 p-4 text-sm text-slate-700 dark:text-slate-200">
        <ShieldCheck className="mt-0.5 shrink-0 text-status-info" size={18} />
        <p>{t('tools.launcherNote')}</p>
      </div>

      {message && (
        <div className="rounded-lg bg-slate-900 px-3 py-2 font-mono text-xs text-slate-200">
          {message}
        </div>
      )}

      {tools.length === 0 && !loading ? (
        <Card>
          <p className="text-sm text-slate-500 dark:text-slate-400">{t('tools.needsApp')}</p>
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {tools.map((tool) => {
            const status = statusView(tool);
            return (
              <Card key={tool.key} className="flex flex-col gap-3">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="font-semibold">{tool.name}</h3>
                      <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-slate-500 dark:bg-surface-overlay dark:text-slate-400">
                        {tool.kind}
                      </span>
                    </div>
                    <p className="text-xs text-slate-500 dark:text-slate-400">
                      {tool.vendor}
                      {tool.version ? ` · v${tool.version}` : ''}
                    </p>
                  </div>
                  <StatusPill tone={status.tone}>{t(status.key)}</StatusPill>
                </div>

                <div className="flex flex-wrap gap-1">
                  {tool.supportedBrands.map((b) => (
                    <span
                      key={b}
                      className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-500 dark:bg-surface-overlay dark:text-slate-400"
                    >
                      {b}
                    </span>
                  ))}
                </div>

                {tool.kind === 'external' && (
                  <p className="truncate font-mono text-xs text-slate-500 dark:text-slate-400">
                    {t('tools.path')}: {tool.path ?? t('tools.notSet')}
                  </p>
                )}

                <div className="mt-auto flex flex-wrap gap-2">
                  {tool.kind === 'external' ? (
                    <>
                      <Button onClick={() => void run(tool.key)}>
                        <Play size={15} />
                        {t('tools.run')}
                      </Button>
                      <Button variant="secondary" onClick={() => void changePath(tool.key)}>
                        <FolderCog size={15} />
                        {t('tools.changePath')}
                      </Button>
                      <Button variant="ghost" onClick={() => bridge && void bridge.tools.openFolder(tool.key)}>
                        <FolderOpen size={15} />
                        {t('tools.openFolder')}
                      </Button>
                    </>
                  ) : (
                    <Button variant="secondary" onClick={() => void checkVersion(tool.key)}>
                      <BadgeCheck size={15} />
                      {t('tools.checkVersion')}
                    </Button>
                  )}
                  <Button variant="ghost" onClick={() => openUrl(tool.url)}>
                    <ExternalLink size={15} />
                    {t('tools.official')}
                  </Button>
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
