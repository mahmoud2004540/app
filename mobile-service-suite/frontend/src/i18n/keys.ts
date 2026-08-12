/** All translation keys used by the UI. Keeping them in a union gives us
 *  compile-time safety: a missing key in any locale is a type error. */
export const TRANSLATION_KEYS = [
  'app.tagline',
  // Navigation
  'nav.dashboard',
  'nav.devices',
  'nav.adb',
  'nav.fastboot',
  'nav.firmware',
  'nav.tools',
  'nav.drivers',
  'nav.protection',
  'nav.backup',
  'nav.repairSessions',
  'nav.logs',
  'nav.reports',
  'nav.settings',
  'nav.group.overview',
  'nav.group.operations',
  'nav.group.management',
  'nav.group.system',
  // Top bar
  'topbar.searchPlaceholder',
  'topbar.notifications',
  'topbar.toggleTheme',
  'topbar.language',
  'topbar.noDevice',
  // Generic page placeholder
  'page.wipTitle',
  'page.wipBody',
  'common.phase',
  // Dashboard — sections & states
  'dash.deviceOverview',
  'dash.deviceInformation',
  'dash.protectionStatus',
  'dash.quickActions',
  'dash.connected',
  'dash.notConnected',
  'dash.connectPrompt',
  'dash.detect',
  'dash.detecting',
  'dash.recheck',
  'dash.checklistTitle',
  'dash.check.usbCable',
  'dash.check.usbPort',
  'dash.check.drivers',
  'dash.check.adb',
  'dash.check.fastboot',
  'dash.previewNote',
  // Device information fields
  'device.brand',
  'device.model',
  'device.imei',
  'device.serial',
  'device.android',
  'device.build',
  'device.cpu',
  'device.ram',
  'device.storage',
  'device.battery',
  'device.usbMode',
  // Protection / connection status labels
  'status.adb',
  'status.fastboot',
  'status.bootloader',
  'status.oemLock',
  'status.frp',
  // Status values
  'status.connected',
  'status.disconnected',
  'status.locked',
  'status.unlocked',
  'status.protected',
  'status.unprotected',
  'status.unknown',
  // Quick-action-only labels (others reuse nav.*)
  'action.detect',
  'action.deviceInfo',
  'action.restore',
] as const;

export type TranslationKey = (typeof TRANSLATION_KEYS)[number];

/** A locale dictionary must provide every key. */
export type Dictionary = Record<TranslationKey, string>;
