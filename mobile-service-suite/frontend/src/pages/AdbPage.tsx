import { useCallback, useState, type ReactNode } from 'react';
import { RefreshCw, TerminalSquare } from 'lucide-react';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { ConfirmDialog } from '../components/ui/ConfirmDialog';
import { useI18n } from '../i18n/I18nProvider';
import type { TranslationKey } from '../i18n/keys';
import type { Result } from '@shared/types/result';

interface ConsoleLine {
  id: number;
  ok: boolean;
  label: string;
  text: string;
}

interface PendingAction {
  detail: string;
  run: () => Promise<void>;
}

type StringResult = Result<string> | Result<string[]>;

function resultText(res: StringResult): string {
  if (res.ok) return Array.isArray(res.value) ? res.value.join('\n') : res.value;
  return res.error;
}

export function AdbPage(): JSX.Element {
  const { t } = useI18n();
  const bridge = typeof window !== 'undefined' ? window.mss : undefined;

  const [devices, setDevices] = useState<string[]>([]);
  const [serial, setSerial] = useState('');
  const [hostPort, setHostPort] = useState('');
  const [pkg, setPkg] = useState('');
  const [shellCmd, setShellCmd] = useState('');
  const [remotePath, setRemotePath] = useState('/sdcard/');
  const [lines, setLines] = useState<ConsoleLine[]>([]);
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState<PendingAction | null>(null);

  const append = useCallback((label: string, ok: boolean, text: string) => {
    setLines((prev) => [{ id: prev.length + 1, ok, label, text }, ...prev].slice(0, 100));
  }, []);

  const note = useCallback(
    (label: string, text: string) => append(label, false, text),
    [append],
  );

  const refresh = useCallback(async () => {
    if (!bridge) {
      note('refresh', 'IPC bridge unavailable — open inside the desktop app.');
      return;
    }
    setBusy(true);
    try {
      const result = await bridge.detectDevices();
      const ids = result.devices.map((d) => d.id);
      setDevices(ids);
      if (ids[0]) setSerial((cur) => cur || ids[0]!);
      append('detect', true, ids.length ? ids.join('\n') : t('adb.noDevices'));
    } finally {
      setBusy(false);
    }
  }, [bridge, append, note, t]);

  /** Execute an operation, appending its result to the console. */
  const execute = useCallback(
    async (label: string, op: () => Promise<StringResult>) => {
      setBusy(true);
      try {
        const res = await op();
        append(label, res.ok, resultText(res));
      } catch (e) {
        append(label, false, e instanceof Error ? e.message : String(e));
      } finally {
        setBusy(false);
      }
    },
    [append],
  );

  /** Run now, or route through the confirmation dialog when sensitive. */
  const run = useCallback(
    (label: string, detail: string, op: () => Promise<StringResult>, sensitive: boolean) => {
      if (!bridge) {
        note(label, 'IPC bridge unavailable — open inside the desktop app.');
        return;
      }
      if (!serial) {
        note(label, t('adb.selectFirst'));
        return;
      }
      const task = (): Promise<void> => execute(label, op);
      if (sensitive) setPending({ detail, run: task });
      else void task();
    },
    [bridge, serial, note, t, execute],
  );

  const adb = bridge?.adb;

  return (
    <div className="mx-auto max-w-6xl space-y-5">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-500/10 text-brand-600 dark:bg-brand-500/15 dark:text-brand-200">
          <TerminalSquare size={22} />
        </div>
        <h1 className="text-2xl font-semibold">{t('nav.adb')}</h1>
      </div>

      {/* Device selector */}
      <Card className="flex flex-wrap items-center gap-3">
        <label className="text-sm text-slate-500 dark:text-slate-400" htmlFor="adb-device">
          {t('adb.selectDevice')}
        </label>
        <select
          id="adb-device"
          value={serial}
          onChange={(e) => setSerial(e.target.value)}
          className="min-w-48 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm dark:border-surface-border dark:bg-surface-overlay dark:text-slate-100"
        >
          <option value="">{devices.length ? '—' : t('adb.noDevices')}</option>
          {devices.map((id) => (
            <option key={id} value={id}>
              {id}
            </option>
          ))}
        </select>
        <Button variant="secondary" onClick={() => void refresh()} disabled={busy}>
          <RefreshCw size={16} className={busy ? 'animate-spin' : ''} />
          {t('adb.refresh')}
        </Button>
      </Card>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        {/* Connection */}
        <Group titleKey="adb.group.connection">
          <input
            aria-label={t('adb.hostPort')}
            placeholder={t('adb.hostPort')}
            value={hostPort}
            onChange={(e) => setHostPort(e.target.value)}
            className={inputClass}
          />
          <div className="flex gap-2">
            <Button
              variant="secondary"
              onClick={() => run('connect', hostPort, () => adb!.connect(hostPort), false)}
            >
              {t('adb.connect')}
            </Button>
            <Button
              variant="secondary"
              onClick={() =>
                run('disconnect', hostPort || 'all', () => adb!.disconnect(hostPort || undefined), false)
              }
            >
              {t('adb.disconnect')}
            </Button>
          </div>
        </Group>

        {/* Power — sensitive */}
        <Group titleKey="adb.group.power">
          <div className="flex flex-wrap gap-2">
            <Button
              onClick={() => run('reboot', 'reboot system', () => adb!.reboot(serial, 'system'), true)}
            >
              {t('adb.rebootSystem')}
            </Button>
            <Button
              variant="secondary"
              onClick={() =>
                run('reboot', 'reboot recovery', () => adb!.reboot(serial, 'recovery'), true)
              }
            >
              {t('adb.rebootRecovery')}
            </Button>
            <Button
              variant="secondary"
              onClick={() =>
                run('reboot', 'reboot bootloader', () => adb!.reboot(serial, 'bootloader'), true)
              }
            >
              {t('adb.rebootBootloader')}
            </Button>
          </div>
        </Group>

        {/* Applications */}
        <Group titleKey="adb.group.apps">
          <input
            aria-label={t('adb.packageName')}
            placeholder={t('adb.packageName')}
            value={pkg}
            onChange={(e) => setPkg(e.target.value)}
            className={inputClass}
          />
          <div className="flex flex-wrap gap-2">
            <Button
              onClick={() =>
                void (async () => {
                  const apk = await bridge?.dialog.openFile([{ name: 'APK', extensions: ['apk'] }]);
                  if (apk) run('install', apk, () => adb!.install(serial, apk), true);
                })()
              }
            >
              {t('adb.install')}
            </Button>
            <Button
              variant="secondary"
              onClick={() => run('uninstall', pkg, () => adb!.uninstall(serial, pkg), true)}
            >
              {t('adb.uninstall')}
            </Button>
            <Button
              variant="ghost"
              onClick={() => run('packages', '', () => adb!.listPackages(serial), false)}
            >
              {t('adb.listPackages')}
            </Button>
          </div>
        </Group>

        {/* Files */}
        <Group titleKey="adb.group.files">
          <input
            aria-label={t('adb.remotePath')}
            placeholder={t('adb.remotePath')}
            value={remotePath}
            onChange={(e) => setRemotePath(e.target.value)}
            className={inputClass}
          />
          <div className="flex flex-wrap gap-2">
            <Button
              onClick={() =>
                void (async () => {
                  const local = await bridge?.dialog.openFile();
                  if (local) run('push', `${local} → ${remotePath}`, () => adb!.push(serial, local, remotePath), true);
                })()
              }
            >
              {t('adb.push')}
            </Button>
            <Button
              variant="secondary"
              onClick={() =>
                void (async () => {
                  const local = await bridge?.dialog.saveFile('pulled-file');
                  if (local) run('pull', `${remotePath} → ${local}`, () => adb!.pull(serial, remotePath, local), false);
                })()
              }
            >
              {t('adb.pull')}
            </Button>
          </div>
        </Group>

        {/* Diagnostics */}
        <Group titleKey="adb.group.diagnostics" className="lg:col-span-2">
          <input
            aria-label={t('adb.shellCommand')}
            placeholder={t('adb.shellCommand')}
            value={shellCmd}
            onChange={(e) => setShellCmd(e.target.value)}
            className={inputClass}
          />
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => run('shell', shellCmd, () => adb!.shell(serial, shellCmd), true)}>
              {t('adb.shell')}
            </Button>
            <Button
              variant="secondary"
              onClick={() => run('logcat', '', () => adb!.logcat(serial, 200), false)}
            >
              {t('adb.logcat')}
            </Button>
            <Button
              variant="secondary"
              onClick={() =>
                void (async () => {
                  const dest = await bridge?.dialog.saveFile('screenshot.png');
                  if (dest) run('screenshot', dest, () => adb!.screenshot(serial, dest), false);
                })()
              }
            >
              {t('adb.screenshot')}
            </Button>
            <Button
              variant="ghost"
              onClick={() =>
                run('info', '', () => adb!.shell(serial, 'getprop ro.build.fingerprint'), false)
              }
            >
              {t('adb.deviceInfo')}
            </Button>
          </div>
        </Group>
      </div>

      {/* Console */}
      <Card>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
            {t('adb.console')}
          </h2>
          <Button variant="ghost" onClick={() => setLines([])}>
            {t('common.clear')}
          </Button>
        </div>
        <div className="max-h-80 overflow-y-auto rounded-lg bg-slate-900 p-3 font-mono text-xs text-slate-200">
          {busy && <div className="text-brand-300">{t('adb.running')}</div>}
          {lines.length === 0 && !busy ? (
            <div className="text-slate-500">{t('adb.consoleEmpty')}</div>
          ) : (
            lines.map((line) => (
              <div key={line.id} className="whitespace-pre-wrap border-b border-white/5 py-1">
                <span className={line.ok ? 'text-status-good' : 'text-status-error'}>
                  {line.ok ? '✓' : '✗'} [{line.label}]
                </span>{' '}
                {line.text}
              </div>
            ))
          )}
        </div>
      </Card>

      <ConfirmDialog
        open={pending !== null}
        message={t('confirm.sensitive')}
        detail={pending?.detail ?? ''}
        onCancel={() => setPending(null)}
        onConfirm={() => {
          const task = pending?.run;
          setPending(null);
          if (task) void task();
        }}
      />
    </div>
  );
}

const inputClass =
  'w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm outline-none focus:border-brand-400 dark:border-surface-border dark:bg-surface-overlay dark:text-slate-100';

function Group({
  titleKey,
  children,
  className = '',
}: {
  titleKey: TranslationKey;
  children: ReactNode;
  className?: string;
}): JSX.Element {
  const { t } = useI18n();
  return (
    <Card className={className}>
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
        {t(titleKey)}
      </h2>
      <div className="space-y-3">{children}</div>
    </Card>
  );
}
