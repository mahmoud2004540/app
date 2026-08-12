/** All translation keys used by the UI. Keeping them in a union gives us
 *  compile-time safety: a missing key in any locale is a type error. */
export const TRANSLATION_KEYS = [
  'app.tagline',
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
  'topbar.searchPlaceholder',
  'topbar.notifications',
  'topbar.toggleTheme',
  'topbar.language',
  'topbar.noDevice',
  'page.wipTitle',
  'page.wipBody',
  'common.phase',
] as const;

export type TranslationKey = (typeof TRANSLATION_KEYS)[number];

/** A locale dictionary must provide every key. */
export type Dictionary = Record<TranslationKey, string>;
