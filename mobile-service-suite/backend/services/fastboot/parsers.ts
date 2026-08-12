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
 * Parse `fastboot getvar all` output into a map. Lines look like
 * `(bootloader) product: star2lte` on stderr.
 */
export function parseFastbootVars(output: string): Record<string, string> {
  const result: Record<string, string> = {};
  const re = /^(?:\(bootloader\)\s*)?([\w.-]+):\s*(.*)$/;
  for (const raw of output.split(/\r?\n/)) {
    const line = raw.trim();
    if (/^(okay|finished|waiting)/i.test(line)) continue;
    const match = re.exec(line);
    if (match) {
      const key = match[1];
      const value = match[2];
      if (key !== undefined && value !== undefined) result[key] = value.trim();
    }
  }
  return result;
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
