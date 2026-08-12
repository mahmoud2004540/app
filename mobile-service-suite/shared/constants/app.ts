/**
 * Application-wide constants shared between the Electron main process,
 * the React renderer, and the core/domain layers.
 */
export const APP = {
  NAME: 'Mobile Service Suite',
  SHORT_NAME: 'MSS',
  VERSION: '0.1.0',
  DESCRIPTION:
    'Professional desktop suite for mobile phone repair technicians.',
} as const;

/** Supported UI languages (implemented progressively in later phases). */
export const SUPPORTED_LOCALES = ['en', 'ar', 'it'] as const;
export type Locale = (typeof SUPPORTED_LOCALES)[number];

/** User roles used by the permission system (PHASE 17/18). */
export const USER_ROLES = ['admin', 'technician', 'viewer'] as const;
export type UserRole = (typeof USER_ROLES)[number];

/** Health / status levels used across diagnostics and logs. */
export const STATUS_LEVELS = ['good', 'warning', 'error', 'info'] as const;
export type StatusLevel = (typeof STATUS_LEVELS)[number];

/**
 * Brand modules the suite is designed to support. Each maps to a module under
 * /modules and can be added without changing the core system (Modular Architecture).
 */
export const SUPPORTED_BRANDS = [
  'samsung',
  'xiaomi',
  'huawei',
  'honor',
  'oppo',
  'realme',
  'oneplus',
  'vivo',
  'tecno',
  'infinix',
  'itel',
  'motorola',
  'google',
  'sony',
  'nokia',
] as const;
export type SupportedBrand = (typeof SUPPORTED_BRANDS)[number];

/** Chipset platform modules. */
export const SUPPORTED_PLATFORMS = ['qualcomm', 'mediatek', 'unisoc'] as const;
export type SupportedPlatform = (typeof SUPPORTED_PLATFORMS)[number];
