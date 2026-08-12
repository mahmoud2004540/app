import { describe, it, expect } from 'vitest';
import { parseFastbootDevices, parseFastbootVar } from '@backend/services/fastboot/parsers';

describe('fastboot parsers', () => {
  it('parses `fastboot devices` ids', () => {
    expect(parseFastbootDevices('SER123\tfastboot\nSER456\tfastboot\n')).toEqual([
      'SER123',
      'SER456',
    ]);
  });

  it('reads a variable from bootloader-prefixed output', () => {
    const out = '(bootloader) unlocked: yes\nOKAY [  0.001s]\nfinished. total time: 0.002s';
    expect(parseFastbootVar(out, 'unlocked')).toBe('yes');
  });

  it('reads a variable without the bootloader prefix', () => {
    expect(parseFastbootVar('product: star2lte', 'product')).toBe('star2lte');
  });

  it('returns undefined for a missing variable', () => {
    expect(parseFastbootVar('unlocked: no', 'product')).toBeUndefined();
  });
});
