/** Input validation & sanitization for ADB operations (security boundary). */

export const REBOOT_TARGETS = ['system', 'recovery', 'bootloader'] as const;
export type RebootTarget = (typeof REBOOT_TARGETS)[number];

export function isRebootTarget(value: string): value is RebootTarget {
  return (REBOOT_TARGETS as readonly string[]).includes(value);
}

/** Serials are alphanumeric plus a small set of separators (incl. host:port). */
export function isValidSerial(serial: string): boolean {
  return /^[A-Za-z0-9][A-Za-z0-9:._-]{0,127}$/.test(serial);
}

/** Android application id, e.g. com.example.app. */
export function isValidPackageName(pkg: string): boolean {
  return /^[a-zA-Z][a-zA-Z0-9_]*(\.[a-zA-Z][a-zA-Z0-9_]*)+$/.test(pkg);
}

/** host:port target for `adb connect`. */
export function isValidHostPort(value: string): boolean {
  return /^[A-Za-z0-9.-]+:\d{1,5}$/.test(value);
}

/**
 * A shell command is rejected if empty or if it contains characters that could
 * chain or redirect on the host side. Commands still run in the device shell,
 * but we refuse obviously dangerous shell metacharacters as defence in depth.
 */
export function isSafeShellCommand(command: string): boolean {
  const trimmed = command.trim();
  if (trimmed.length === 0 || trimmed.length > 512) return false;
  return !/[;&|`$><\n\r]/.test(trimmed);
}
