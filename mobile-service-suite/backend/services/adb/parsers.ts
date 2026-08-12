export interface AdbDeviceLine {
  id: string;
  state: string;
}

/** Parse the output of `adb devices`. */
export function parseAdbDevices(stdout: string): AdbDeviceLine[] {
  return stdout
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.length > 0 && !/^list of devices attached/i.test(line))
    .map((line) => {
      const parts = line.split(/\s+/);
      return { id: parts[0] ?? '', state: parts[1] ?? 'unknown' };
    })
    .filter((d) => d.id.length > 0);
}

/** Parse `getprop` output lines of the form `[key]: [value]`. */
export function parseGetprop(stdout: string): Record<string, string> {
  const result: Record<string, string> = {};
  const re = /^\[([^\]]+)\]:\s*\[([^\]]*)\]$/;
  for (const raw of stdout.split(/\r?\n/)) {
    const match = re.exec(raw.trim());
    if (match) {
      const key = match[1];
      const value = match[2];
      if (key !== undefined && value !== undefined) result[key] = value;
    }
  }
  return result;
}

/** Extract the charge percentage from `dumpsys battery` output. */
export function parseBatteryLevel(stdout: string): number | undefined {
  const match = /^\s*level:\s*(\d+)\s*$/m.exec(stdout);
  if (!match || match[1] === undefined) return undefined;
  const level = Number.parseInt(match[1], 10);
  return Number.isNaN(level) ? undefined : level;
}

/** Extract MemTotal (in kB) from /proc/meminfo. */
export function parseMemTotalKb(stdout: string): number | undefined {
  const match = /^MemTotal:\s*(\d+)\s*kB/m.exec(stdout);
  if (!match || match[1] === undefined) return undefined;
  const kb = Number.parseInt(match[1], 10);
  return Number.isNaN(kb) ? undefined : kb;
}
