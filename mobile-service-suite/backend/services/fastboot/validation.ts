/** Input validation & sanitization for Fastboot operations (security boundary). */

export const FASTBOOT_REBOOT_TARGETS = ['system', 'bootloader', 'recovery', 'fastboot'] as const;
export type FastbootRebootTarget = (typeof FASTBOOT_REBOOT_TARGETS)[number];

export function isFastbootRebootTarget(value: string): value is FastbootRebootTarget {
  return (FASTBOOT_REBOOT_TARGETS as readonly string[]).includes(value);
}

/** Same serial rule as ADB; duplicated to keep the modules independent. */
export function isValidSerial(serial: string): boolean {
  return /^[A-Za-z0-9][A-Za-z0-9:._-]{0,127}$/.test(serial);
}

/** Partition names: boot, system, userdata, vbmeta, recovery, … */
export function isValidPartition(partition: string): boolean {
  return /^[a-zA-Z0-9_]{1,32}$/.test(partition);
}

/** A getvar variable name (or 'all'). */
export function isValidVarName(name: string): boolean {
  return /^[\w.-]{1,64}$/.test(name);
}
