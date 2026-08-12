import { describe, it, expect } from 'vitest';
import {
  parseAdbDevices,
  parseBatteryLevel,
  parseGetprop,
  parseMemTotalKb,
} from '@backend/services/adb/parsers';

describe('adb parsers', () => {
  it('parses `adb devices`, skipping the header and blanks', () => {
    const out = [
      'List of devices attached',
      'ABC123\tdevice',
      'EMU-5554\tunauthorized',
      '',
    ].join('\n');
    expect(parseAdbDevices(out)).toEqual([
      { id: 'ABC123', state: 'device' },
      { id: 'EMU-5554', state: 'unauthorized' },
    ]);
  });

  it('returns an empty list when nothing is attached', () => {
    expect(parseAdbDevices('List of devices attached\n\n')).toEqual([]);
  });

  it('parses getprop key/value lines', () => {
    const out = '[ro.product.brand]: [samsung]\n[ro.build.version.release]: [13]\n[empty]: []';
    const props = parseGetprop(out);
    expect(props['ro.product.brand']).toBe('samsung');
    expect(props['ro.build.version.release']).toBe('13');
    expect(props['empty']).toBe('');
  });

  it('extracts the battery level from dumpsys', () => {
    expect(parseBatteryLevel('  AC powered: false\n  level: 87\n  scale: 100')).toBe(87);
    expect(parseBatteryLevel('no level here')).toBeUndefined();
  });

  it('extracts MemTotal in kB', () => {
    expect(parseMemTotalKb('MemTotal:        3899840 kB\nMemFree: 100 kB')).toBe(3899840);
    expect(parseMemTotalKb('garbage')).toBeUndefined();
  });
});
