import { Wrench } from 'lucide-react';
import { Card } from '../ui/Card';
import { useI18n } from '../../i18n/I18nProvider';
import { recommendToolsForDevice } from '@modules/registry';
import { toolDisplayName } from '@modules/toolNames';
import type { DeviceSnapshot } from '../../types/device';

/**
 * Smart tool recommendation panel — matches the connected device's brand and
 * chipset against the registered brand/platform modules (PHASE 10 / 22).
 */
export function RecommendedTools({ device }: { device: DeviceSnapshot }): JSX.Element {
  const { t } = useI18n();
  const rec = recommendToolsForDevice({ brand: device.brand, chipset: device.cpu });

  return (
    <Card>
      <div className="mb-3 flex items-center gap-2">
        <Wrench size={16} className="text-brand-500" />
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
          {t('dash.recommendedTools')}
        </h2>
      </div>

      <div className="mb-3 flex flex-wrap gap-2 text-xs text-slate-500 dark:text-slate-400">
        {rec.brand && (
          <span className="rounded-full bg-brand-500/10 px-2.5 py-1 text-brand-600 dark:text-brand-200">
            {rec.brand.displayName}
          </span>
        )}
        {rec.platform && (
          <span className="rounded-full bg-brand-500/10 px-2.5 py-1 text-brand-600 dark:text-brand-200">
            {rec.platform.displayName}
          </span>
        )}
      </div>

      <div className="flex flex-wrap gap-2">
        {rec.tools.map((key) => (
          <span
            key={key}
            className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 dark:border-surface-border dark:bg-surface-overlay dark:text-slate-200"
          >
            {toolDisplayName(key)}
          </span>
        ))}
      </div>
    </Card>
  );
}
