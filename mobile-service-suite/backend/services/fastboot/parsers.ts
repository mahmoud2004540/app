/** Parse the ids from `fastboot devices` output. Lines look like `SERIAL\tfastboot`. */
export function parseFastbootDevices(stdout: string): string[] {
  return stdout
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.length > 0)
    .map((line) => (line.split(/\s+/)[0] ?? '').trim())
    .filter((id) => id.length > 0);
}

/**
 * Extract a variable value from `fastboot getvar <name>` output. Fastboot writes
 * to stderr, in lines shaped like `(bootloader) unlocked: yes` or `unlocked: yes`.
 */
export function parseFastbootVar(output: string, name: string): string | undefined {
  const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const re = new RegExp(`(?:\\(bootloader\\)\\s*)?${escaped}:\\s*(.+)`, 'i');
  for (const raw of output.split(/\r?\n/)) {
    const match = re.exec(raw.trim());
    if (match && match[1] !== undefined) return match[1].trim();
  }
  return undefined;
}
