import { useNavigate } from 'react-router-dom';
import {
  RefreshCw,
  Info,
  TerminalSquare,
  Rocket,
  HardDriveDownload,
  Wrench,
  Cable,
  DatabaseBackup,
  Undo2,
  ClipboardList,
  ScrollText,
  FileText,
  type LucideIcon,
} from 'lucide-react';
import { Card } from '../ui/Card';
import { useI18n } from '../../i18n/I18nProvider';
import type { TranslationKey } from '../../i18n/keys';

interface QuickActionsProps {
  onDetect: () => void;
  detecting: boolean;
}

interface Action {
  labelKey: TranslationKey;
  icon: LucideIcon;
  to?: string;
  isDetect?: boolean;
}

const ACTIONS: readonly Action[] = [
  { labelKey: 'action.detect', icon: RefreshCw, isDetect: true },
  { labelKey: 'action.deviceInfo', icon: Info, to: '/devices' },
  { labelKey: 'nav.adb', icon: TerminalSquare, to: '/adb' },
  { labelKey: 'nav.fastboot', icon: Rocket, to: '/fastboot' },
  { labelKey: 'nav.firmware', icon: HardDriveDownload, to: '/firmware' },
  { labelKey: 'nav.drivers', icon: Cable, to: '/drivers' },
  { labelKey: 'nav.tools', icon: Wrench, to: '/tools' },
  { labelKey: 'nav.backup', icon: DatabaseBackup, to: '/backup' },
  { labelKey: 'action.restore', icon: Undo2, to: '/backup' },
  { labelKey: 'nav.repairSessions', icon: ClipboardList, to: '/repair-sessions' },
  { labelKey: 'nav.logs', icon: ScrollText, to: '/logs' },
  { labelKey: 'nav.reports', icon: FileText, to: '/reports' },
];

export function QuickActions({ onDetect, detecting }: QuickActionsProps): JSX.Element {
  const { t } = useI18n();
  const navigate = useNavigate();

  return (
    <Card>
      <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
        {t('dash.quickActions')}
      </h2>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
        {ACTIONS.map((action) => {
          const Icon = action.icon;
          const isBusy = action.isDetect && detecting;
          return (
            <button
              key={action.labelKey}
              type="button"
              disabled={isBusy}
              onClick={() => (action.isDetect ? onDetect() : action.to && navigate(action.to))}
              className={
                'flex flex-col items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-4 text-center text-xs font-medium text-slate-600 transition-colors hover:border-brand-300 hover:bg-brand-50 disabled:opacity-60 ' +
                'dark:border-surface-border dark:bg-surface-overlay dark:text-slate-300 dark:hover:border-brand-500/40 dark:hover:bg-surface-border'
              }
            >
              <Icon size={20} className={isBusy ? 'animate-spin text-brand-500' : 'text-brand-500'} />
              <span>{t(action.labelKey)}</span>
            </button>
          );
        })}
      </div>
    </Card>
  );
}
