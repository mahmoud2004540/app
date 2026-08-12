import type { ToolKind } from '@shared/types/tool';

/** How a tool's presence/version is detected. */
export type ToolDetect =
  | { type: 'cli'; binary: string; versionArg: string }
  | { type: 'external' };

export interface ToolInfo {
  key: string;
  name: string;
  vendor: string;
  kind: ToolKind;
  supportedBrands: string[];
  description: string;
  url: string;
  detect: ToolDetect;
}

/**
 * Static catalog of tools the suite can detect and launch. External commercial
 * tools are launched from the technician's own installed copy — the suite never
 * bundles, integrates, or circumvents any licensing (see docs/SECURITY.md).
 * New tools are added here as data (Modular Architecture).
 */
export const TOOL_CATALOG: readonly ToolInfo[] = [
  {
    key: 'adb',
    name: 'ADB',
    vendor: 'Google',
    kind: 'cli',
    supportedBrands: ['all'],
    description: 'Android Debug Bridge command-line tool.',
    url: 'https://developer.android.com/tools/releases/platform-tools',
    detect: { type: 'cli', binary: 'adb', versionArg: 'version' },
  },
  {
    key: 'fastboot',
    name: 'Fastboot',
    vendor: 'Google',
    kind: 'cli',
    supportedBrands: ['all'],
    description: 'Bootloader-mode flashing tool.',
    url: 'https://developer.android.com/tools/releases/platform-tools',
    detect: { type: 'cli', binary: 'fastboot', versionArg: '--version' },
  },
  {
    key: 'platform-tools',
    name: 'Android Platform Tools',
    vendor: 'Google',
    kind: 'cli',
    supportedBrands: ['all'],
    description: 'The official adb/fastboot bundle.',
    url: 'https://developer.android.com/tools/releases/platform-tools',
    detect: { type: 'cli', binary: 'adb', versionArg: 'version' },
  },
  {
    key: 'odin',
    name: 'Odin',
    vendor: 'Samsung (third-party tool)',
    kind: 'external',
    supportedBrands: ['samsung'],
    description: 'Samsung firmware flashing tool (Download mode).',
    url: 'https://odindownload.com/',
    detect: { type: 'external' },
  },
  {
    key: 'miflash',
    name: 'Mi Flash',
    vendor: 'Xiaomi',
    kind: 'external',
    supportedBrands: ['xiaomi'],
    description: 'Xiaomi fastboot flashing tool.',
    url: 'https://xiaomiflashtool.com/',
    detect: { type: 'external' },
  },
  {
    key: 'qfil',
    name: 'QFIL / QPST',
    vendor: 'Qualcomm',
    kind: 'external',
    supportedBrands: ['qualcomm'],
    description: 'Qualcomm Flash Image Loader for EDL flashing.',
    url: 'https://qpsttool.com/',
    detect: { type: 'external' },
  },
  {
    key: 'spflash',
    name: 'SP Flash Tool',
    vendor: 'MediaTek',
    kind: 'external',
    supportedBrands: ['mediatek'],
    description: 'MediaTek Smart Phone Flash Tool.',
    url: 'https://spflashtool.com/',
    detect: { type: 'external' },
  },
  {
    key: 'researchdownload',
    name: 'ResearchDownload',
    vendor: 'Unisoc',
    kind: 'external',
    supportedBrands: ['unisoc'],
    description: 'Unisoc (Spreadtrum) firmware download tool.',
    url: 'https://spdflashtool.com/',
    detect: { type: 'external' },
  },
  {
    key: 'upgradedownload',
    name: 'UpgradeDownload',
    vendor: 'Unisoc',
    kind: 'external',
    supportedBrands: ['unisoc'],
    description: 'Unisoc upgrade/download flashing tool.',
    url: 'https://spdflashtool.com/',
    detect: { type: 'external' },
  },
  {
    key: 'hisuite',
    name: 'HiSuite',
    vendor: 'Huawei',
    kind: 'external',
    supportedBrands: ['huawei', 'honor'],
    description: 'Huawei device management and backup suite.',
    url: 'https://consumer.huawei.com/en/support/hisuite/',
    detect: { type: 'external' },
  },
];
