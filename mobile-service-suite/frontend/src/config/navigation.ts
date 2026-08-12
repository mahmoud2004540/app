import {
  LayoutDashboard,
  Smartphone,
  TerminalSquare,
  Rocket,
  HardDriveDownload,
  Wrench,
  Cable,
  ShieldCheck,
  DatabaseBackup,
  ClipboardList,
  ScrollText,
  FileText,
  Settings,
  type LucideIcon,
} from 'lucide-react';
import type { TranslationKey } from '../i18n/keys';

export interface NavItem {
  readonly id: string;
  readonly path: string;
  readonly labelKey: TranslationKey;
  readonly icon: LucideIcon;
  /** Roadmap phase that delivers the full page (used by the WIP placeholder). */
  readonly phase: number;
}

export interface NavGroup {
  readonly labelKey: TranslationKey;
  readonly items: readonly NavItem[];
}

/** Single source of truth: both the Sidebar and the Router are generated from this. */
export const NAV_GROUPS: readonly NavGroup[] = [
  {
    labelKey: 'nav.group.overview',
    items: [
      { id: 'dashboard', path: '/', labelKey: 'nav.dashboard', icon: LayoutDashboard, phase: 3 },
      { id: 'devices', path: '/devices', labelKey: 'nav.devices', icon: Smartphone, phase: 5 },
    ],
  },
  {
    labelKey: 'nav.group.operations',
    items: [
      { id: 'adb', path: '/adb', labelKey: 'nav.adb', icon: TerminalSquare, phase: 6 },
      { id: 'fastboot', path: '/fastboot', labelKey: 'nav.fastboot', icon: Rocket, phase: 7 },
      {
        id: 'firmware',
        path: '/firmware',
        labelKey: 'nav.firmware',
        icon: HardDriveDownload,
        phase: 11,
      },
      { id: 'tools', path: '/tools', labelKey: 'nav.tools', icon: Wrench, phase: 9 },
      { id: 'drivers', path: '/drivers', labelKey: 'nav.drivers', icon: Cable, phase: 8 },
    ],
  },
  {
    labelKey: 'nav.group.management',
    items: [
      {
        id: 'protection',
        path: '/protection',
        labelKey: 'nav.protection',
        icon: ShieldCheck,
        phase: 12,
      },
      { id: 'backup', path: '/backup', labelKey: 'nav.backup', icon: DatabaseBackup, phase: 13 },
      {
        id: 'repair-sessions',
        path: '/repair-sessions',
        labelKey: 'nav.repairSessions',
        icon: ClipboardList,
        phase: 14,
      },
    ],
  },
  {
    labelKey: 'nav.group.system',
    items: [
      { id: 'logs', path: '/logs', labelKey: 'nav.logs', icon: ScrollText, phase: 15 },
      { id: 'reports', path: '/reports', labelKey: 'nav.reports', icon: FileText, phase: 16 },
      { id: 'settings', path: '/settings', labelKey: 'nav.settings', icon: Settings, phase: 17 },
    ],
  },
];

/** Flat list of every navigable item (used by the Router). */
export const NAV_ITEMS: readonly NavItem[] = NAV_GROUPS.flatMap((group) => group.items);
