import { useCallback, useState, type ReactNode } from 'react';
import { RefreshCw, Rocket } from 'lucide-react';
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
  message: string;
  detail: string;
  run: () => Promise<void>;
}

type AnyResult = Result<unknown>;

function resultText(res: AnyResult): string {
  if (!res.ok) return res.error;
  const v = res.value;
  if (typeof v === 'string') return v;
  if (Array.isArray(v)) return v.join('\n');
  if (v && typeof v === 'object') {
    return Object.entries(v as Record<string, unknown>)
      .map(([k, val]) => `${k}: ${String(val)}`)
      .join('\n');
  }
  return String(v);
}

const inputClass =
  'w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm outline-none focus:border-brand-400 dark:border-surface-border dark:bg-surface-overlay dark:text-slate-100';

export function FastbootPage(): JSX.Element {
  const { t } = useI18n();
  const bridge = typeof window !== 'undefined' ? window.mss : undefined;
  const fb = bridge?.fastboot;

  const [devices, setDevices] = useState<string[]>([]);
  const [serial, setSerial] = useState('');
  const [varName, setVarName] = useState('unlocked');
  const [partition, setPartition] = useState('');
  const [lines, setLines] = useState<ConsoleLine[]>([]);
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState<PendingAction | null>(null);

  const append = useCallback((label: string, ok: boolean, text: string) => {
    setLines((prev) => [{ id: prev.length + 1, ok, label, text }, ...prev].slice(0, 100));
  }, []);
  const note = useCallback((label: string, text: string) => append(label, false, text), [append]);

  const refresh = useCallback(async () => {
    if (!fb) {
      note('refresh', 'IPC bridge unavailable — open inside the desktop app.');
      return;
    }
    setBusy(true);
    try {
      const res = await fb.devices();
      if (res.ok) {
        setDevices(res.value);
        if (res.value[0]) setSerial((cur) => cur || res.value[0]!);
        append('devices', true, res.value.length ? res.value.join('\n') : t('adb.noDevices'));
      } else {
        append('devices', false, res.error);
      }
    } finally {
      setBusy(false);
    }
  }, [fb, append, note, t]);

  const execute = useCallback(
    async (label: string, op: () => Promise<AnyResult>) => {
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

  /** confirmKey: undefined = run now; otherwise route through ConfirmDialog. */
  const run = useCallback(
    (
      label: string,
      op: () => Promise<AnyResult>,
      confirmKey?: 'confirm.sensitive' | 'confirm.destructive',
      detail = '',
    ) => {
      if (!fb) {
        note(label, 'IPC bridge unavailable — open inside the desktop app.');
        return;
      }
      if (!serial) {
        note(label, t('adb.selectFirst'));
        return;
      }
      const task = (): Promise<void> => execute(label, op);
      if (confirmKey) setPending({ message: t(confirmKey), detail, run: task });
      else void task();
    },
    [fb, serial, note, t, execute],
  );

  return (
    <div className="mx-auto max-w-6xl space-y-5">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-500/10 text-brand-600 dark:bg-brand-500/15 dark:text-brand-200">
          <Rocket size={22} />
        </div>
        <h1 className="text-2xl font-semibold">{t('nav.fastboot')}</h1>
      </div>

      <Card className="flex flex-wrap items-center gap-3">
        <label className="text-sm text-slate-500 dark:text-slate-400" htmlFor="fb-device">
          {t('adb.selectDevice')}
        </label>
        <select
          id="fb-device"
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
        <Group titleKey="fastboot.group.info">
          <input
            aria-label={t('fastboot.varName')}
            placeholder={t('fastboot.varName')}
            value={varName}
            onChange={(e) => setVarName(e.target.value)}
            className={inputClass}
          />
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={() => run('getvar', () => fb!.getVar(serial, varName))}>
              {t('fastboot.getVar')}
            </Button>
            <Button variant="ghost" onClick={() => run('getvar all', () => fb!.getAllVars(serial))}>
              {t('fastboot.getAllVars')}
            </Button>
          </div>
        </Group>

        <Group titleKey="fastboot.group.power">
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => run('reboot', () => fb!.reboot(serial, 'system'), 'confirm.sensitive', 'reboot')}>
              {t('fastboot.rebootSystem')}
            </Button>
            <Button
              variant="secondary"
              onClick={() => run('reboot', () => fb!.reboot(serial, 'bootloader'), 'confirm.sensitive', 'bootloader')}
            >
              {t('fastboot.rebootBootloader')}
            </Button>
            <Button
              variant="secondary"
              onClick={() => run('reboot', () => fb!.reboot(serial, 'recovery'), 'confirm.sensitive', 'recovery')}
            >
              {t('fastboot.rebootRecovery')}
            </Button>
            <Button
              variant="secondary"
              onClick={() => run('reboot', () => fb!.reboot(serial, 'fastboot'), 'confirm.sensitive', 'fastbootd')}
            >
              {t('fastboot.rebootFastboot')}
            </Button>
          </div>
        </Group>

        <Group titleKey="fastboot.group.lock">
          <div className="flex flex-wrap gap-2">
            <Button
              onClick={() => run('unlock', () => fb!.unlock(serial), 'confirm.destructive', 'flashing unlock')}
            >
              {t('fastboot.unlock')}
            </Button>
            <Button
              variant="secondary"
              onClick={() => run('lock', () => fb!.lock(serial), 'confirm.destructive', 'flashing lock')}
            >
              {t('fastboot.lock')}
            </Button>
          </div>
        </Group>

        <Group titleKey="fastboot.group.partitions">
          <input
            aria-label={t('fastboot.partition')}
            placeholder={t('fastboot.partition')}
            value={partition}
            onChange={(e) => setPartition(e.target.value)}
            className={inputClass}
          />
          <div className="flex flex-wrap gap-2">
            <Button
              onClick={() =>
                run('erase', () => fb!.erase(serial, partition), 'confirm.destructive', `erase ${partition}`)
              }
            >
              {t('fastboot.erase')}
            </Button>
            <Button
              variant="secondary"
              onClick={() =>
                void (async () => {
                  const img = await bridge?.dialog.openFile([
                    { name: 'Image', extensions: ['img', 'bin'] },
                  ]);
                  if (img)
                    run('flash', () => fb!.flash(serial, partition, img), 'confirm.destructive', `flash ${partition} ← ${img}`);
                })()
              }
            >
              {t('fastboot.flash')}
            </Button>
          </div>
        </Group>
      </div>

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
        message={pending?.message ?? ''}
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

function Group({
  titleKey,
  children,
}: {
  titleKey: TranslationKey;
  children: ReactNode;
}): JSX.Element {
  const { t } = useI18n();
  return (
    <Card>
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
        {t(titleKey)}
      </h2>
      <div className="space-y-3">{children}</div>
    </Card>
  );
}
