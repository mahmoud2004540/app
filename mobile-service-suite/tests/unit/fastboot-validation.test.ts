import { describe, it, expect } from 'vitest';
import {
  isFastbootRebootTarget,
  isValidPartition,
  isValidSerial,
  isValidVarName,
} from '@backend/services/fastboot/validation';
import { parseFastbootVars } from '@backend/services/fastboot/parsers';

describe('fastboot validation', () => {
  it('accepts valid reboot targets', () => {
    expect(isFastbootRebootTarget('bootloader')).toBe(true);
    expect(isFastbootRebootTarget('fastboot')).toBe(true);
    expect(isFastbootRebootTarget('edl')).toBe(false);
  });

  it('validates partitions', () => {
    expect(isValidPartition('boot')).toBe(true);
    expect(isValidPartition('userdata')).toBe(true);
    expect(isValidPartition('../etc')).toBe(false);
    expect(isValidPartition('')).toBe(false);
  });

  it('validates serials and var names', () => {
    expect(isValidSerial('FB123')).toBe(true);
    expect(isValidSerial('bad serial')).toBe(false);
    expect(isValidVarName('unlocked')).toBe(true);
    expect(isValidVarName('current-slot')).toBe(true);
    expect(isValidVarName('bad name!')).toBe(false);
  });
});

describe('parseFastbootVars', () => {
  it('parses getvar all output into a map', () => {
    const out = [
      '(bootloader) product: star2lte',
      '(bootloader) unlocked: yes',
      '(bootloader) version-bootloader: G1',
      'OKAY [  0.010s]',
      'finished. total time: 0.011s',
    ].join('\n');
    expect(parseFastbootVars(out)).toEqual({
      product: 'star2lte',
      unlocked: 'yes',
      'version-bootloader': 'G1',
    });
  });
});
