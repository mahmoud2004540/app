import { describe, it, expect } from 'vitest';
import {
  isRebootTarget,
  isSafeShellCommand,
  isValidHostPort,
  isValidPackageName,
  isValidSerial,
} from '@backend/services/adb/validation';

describe('adb validation', () => {
  it('accepts valid reboot targets only', () => {
    expect(isRebootTarget('system')).toBe(true);
    expect(isRebootTarget('recovery')).toBe(true);
    expect(isRebootTarget('bootloader')).toBe(true);
    expect(isRebootTarget('edl')).toBe(false);
  });

  it('validates serials', () => {
    expect(isValidSerial('ABC123')).toBe(true);
    expect(isValidSerial('192.168.1.5:5555')).toBe(true);
    expect(isValidSerial('bad serial!')).toBe(false);
    expect(isValidSerial('')).toBe(false);
  });

  it('validates package names', () => {
    expect(isValidPackageName('com.example.app')).toBe(true);
    expect(isValidPackageName('notapackage')).toBe(false);
    expect(isValidPackageName('1.bad.start')).toBe(false);
  });

  it('validates host:port', () => {
    expect(isValidHostPort('192.168.1.10:5555')).toBe(true);
    expect(isValidHostPort('device.local:5037')).toBe(true);
    expect(isValidHostPort('nohost')).toBe(false);
  });

  it('rejects unsafe shell commands', () => {
    expect(isSafeShellCommand('getprop ro.product.model')).toBe(true);
    expect(isSafeShellCommand('rm -rf / ; reboot')).toBe(false);
    expect(isSafeShellCommand('cat x | nc host')).toBe(false);
    expect(isSafeShellCommand('   ')).toBe(false);
  });
});
