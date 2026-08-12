/** Display names for tool keys used in recommendations (shared, framework-free). */
export const TOOL_DISPLAY_NAMES: Record<string, string> = {
  adb: 'ADB',
  fastboot: 'Fastboot',
  odin: 'Odin',
  miflash: 'Mi Flash',
  qfil: 'QFIL / QPST',
  spflash: 'SP Flash Tool',
  researchdownload: 'ResearchDownload',
  upgradedownload: 'UpgradeDownload',
  hisuite: 'HiSuite',
};

export function toolDisplayName(key: string): string {
  return TOOL_DISPLAY_NAMES[key] ?? key;
}
