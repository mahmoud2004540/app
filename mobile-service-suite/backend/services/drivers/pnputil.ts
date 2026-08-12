export interface PnpDriverEntry {
  publishedName: string;
  originalName: string;
  provider: string;
  className: string;
  version: string;
}

/**
 * Parse the output of `pnputil /enum-drivers` (Windows). Entries are separated by
 * blank lines; each has `Field Name : value` lines (localized field labels vary,
 * so we match on the stable English labels).
 */
export function parsePnpUtilDrivers(output: string): PnpDriverEntry[] {
  const blocks = output.split(/\r?\n\s*\r?\n/);
  const entries: PnpDriverEntry[] = [];

  for (const block of blocks) {
    const get = (label: RegExp): string => {
      const m = label.exec(block);
      return m && m[1] !== undefined ? m[1].trim() : '';
    };
    const publishedName = get(/Published Name\s*:\s*(.+)/i);
    const provider = get(/Provider Name\s*:\s*(.+)/i);
    const className = get(/Class Name\s*:\s*(.+)/i);
    const version = get(/Driver Version\s*:\s*(.+)/i);
    const originalName = get(/Original Name\s*:\s*(.+)/i);

    if (publishedName || provider || originalName) {
      entries.push({ publishedName, originalName, provider, className, version });
    }
  }
  return entries;
}

/**
 * Return the version of the first entry matching any of the given substrings
 * (case-insensitive) against provider/class/original name, or null if none.
 */
export function matchDriver(entries: PnpDriverEntry[], needles: string[]): string | null {
  const lowered = needles.map((n) => n.toLowerCase());
  for (const entry of entries) {
    const haystack = `${entry.provider} ${entry.className} ${entry.originalName}`.toLowerCase();
    if (lowered.some((n) => haystack.includes(n))) {
      return entry.version || 'installed';
    }
  }
  return null;
}
