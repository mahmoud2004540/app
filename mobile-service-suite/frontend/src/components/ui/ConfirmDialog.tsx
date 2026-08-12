import { AlertTriangle } from 'lucide-react';
import { Modal } from './Modal';
import { Button } from './Button';
import { useI18n } from '../../i18n/I18nProvider';

interface ConfirmDialogProps {
  open: boolean;
  title?: string;
  message: string;
  detail?: string;
  onConfirm: () => void;
  onCancel: () => void;
}

/** Confirmation gate shown before every sensitive/destructive operation. */
export function ConfirmDialog({
  open,
  title,
  message,
  detail,
  onConfirm,
  onCancel,
}: ConfirmDialogProps): JSX.Element {
  const { t } = useI18n();
  return (
    <Modal open={open} onClose={onCancel} title={title ?? t('confirm.title')}>
      <div className="flex gap-3">
        <AlertTriangle className="mt-0.5 shrink-0 text-status-warning" size={20} />
        <div>
          <p className="text-sm text-slate-700 dark:text-slate-200">{message}</p>
          {detail && (
            <p className="mt-1 break-all font-mono text-xs text-slate-500 dark:text-slate-400">
              {detail}
            </p>
          )}
        </div>
      </div>
      <div className="mt-5 flex justify-end gap-2">
        <Button variant="secondary" onClick={onCancel}>
          {t('common.cancel')}
        </Button>
        <Button onClick={onConfirm}>{t('common.confirm')}</Button>
      </div>
    </Modal>
  );
}
