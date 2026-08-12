// @vitest-environment node
import { describe, it, expect } from 'vitest';
import { DeviceDetectionService } from '@backend/services/detection/DeviceDetectionService';
import type { CommandResult, CommandRunner } from '@backend/services/process/CommandRunner';

/** Test double that returns canned output keyed by the joined command+args. */
class FakeRunner implements CommandRunner {
  constructor(private readonly table: Record<string, CommandResult>) {}
  run(command: string, args: string[]): Promise<CommandResult> {
    const key = [command, ...args].join(' ');
    return Promise.resolve(this.table[key] ?? { code: null, stdout: '', stderr: 'ENOENT' });
  }
}

const ok = (stdout: string, stderr = ''): CommandResult => ({ code: 0, stdout, stderr });

describe('DeviceDetectionService', () => {
  it('reports both tools missing when nothing is installed', async () => {
    const service = new DeviceDetectionService(new FakeRunner({}));
    const result = await service.detect();
    expect(result.adbAvailable).toBe(false);
    expect(result.fastbootAvailable).toBe(false);
    expect(result.devices).toEqual([]);
  });

  it('detects and enriches a ready ADB device', async () => {
    const runner = new FakeRunner({
      'adb version': ok('Android Debug Bridge version 1.0.41'),
      'fastboot --version': { code: null, stdout: '', stderr: 'ENOENT' },
      'adb devices': ok('List of devices attached\nSER123\tdevice\n'),
      'adb -s SER123 shell getprop': ok(
        [
          '[ro.product.brand]: [samsung]',
          '[ro.product.model]: [SM-G991B]',
          '[ro.build.version.release]: [13]',
          '[ro.serialno]: [SER123]',
          '[ro.boot.flash.locked]: [1]',
          '[sys.oem_unlock_allowed]: [0]',
        ].join('\n'),
      ),
      'adb -s SER123 shell dumpsys battery': ok('  level: 77\n'),
      'adb -s SER123 shell cat /proc/meminfo': ok('MemTotal: 8000000 kB\n'),
    });

    const result = await new DeviceDetectionService(runner).detect();
    expect(result.adbAvailable).toBe(true);
    expect(result.fastbootAvailable).toBe(false);
    expect(result.devices).toHaveLength(1);

    const device = result.devices[0]!;
    expect(device.transport).toBe('adb');
    expect(device.state).toBe('device');
    expect(device.brand).toBe('samsung');
    expect(device.model).toBe('SM-G991B');
    expect(device.androidVersion).toBe('13');
    expect(device.batteryPercent).toBe(77);
    expect(device.totalRamKb).toBe(8000000);
    expect(device.bootloaderUnlocked).toBe('no'); // flash.locked = 1 → locked
    expect(device.oemUnlockAllowed).toBe('no');
    expect(device.frpState).toBe('unknown'); // diagnosed, never bypassed
  });

  it('reports an unauthorized ADB device without probing it', async () => {
    const runner = new FakeRunner({
      'adb version': ok('adb'),
      'fastboot --version': { code: null, stdout: '', stderr: '' },
      'adb devices': ok('List of devices attached\nZZ9\tunauthorized\n'),
    });
    const result = await new DeviceDetectionService(runner).detect();
    expect(result.devices).toEqual([{ id: 'ZZ9', transport: 'adb', state: 'unauthorized' }]);
  });

  it('detects a fastboot device and reads unlocked state', async () => {
    const runner = new FakeRunner({
      'adb version': { code: null, stdout: '', stderr: '' },
      'fastboot --version': ok('fastboot version 34.0.0'),
      'fastboot devices': ok('FB123\tfastboot\n'),
      'fastboot -s FB123 getvar unlocked': ok('', '(bootloader) unlocked: yes'),
      'fastboot -s FB123 getvar product': ok('', '(bootloader) product: star2lte'),
    });
    const result = await new DeviceDetectionService(runner).detect();
    expect(result.fastbootAvailable).toBe(true);
    const device = result.devices[0]!;
    expect(device.transport).toBe('fastboot');
    expect(device.bootloaderUnlocked).toBe('yes');
    expect(device.model).toBe('star2lte');
  });
});
