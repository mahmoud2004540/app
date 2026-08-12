// @vitest-environment node
import { describe, it, expect } from 'vitest';
import { DriverManagerService } from '@backend/services/drivers/DriverManagerService';
import type { CommandResult, CommandRunner } from '@backend/services/process/CommandRunner';

class FakeRunner implements CommandRunner {
  constructor(private readonly table: Record<string, CommandResult>) {}
  run(command: string, args: string[]): Promise<CommandResult> {
    const key = [command, ...args].join(' ');
    return Promise.resolve(this.table[key] ?? { code: null, stdout: '', stderr: 'ENOENT' });
  }
}

const ok = (stdout = ''): CommandResult => ({ code: 0, stdout, stderr: '' });

describe('DriverManagerService', () => {
  it('marks pnputil drivers unknown/not-checkable off Windows', async () => {
    const runner = new FakeRunner({ 'adb version': ok(), 'fastboot --version': ok() });
    const report = await new DriverManagerService(runner, 'linux').list();
    expect(report.platform).toBe('linux');

    const adb = report.drivers.find((d) => d.key === 'adb')!;
    expect(adb.installed).toBe('yes');
    expect(adb.status).toBe('installed');

    const samsung = report.drivers.find((d) => d.key === 'samsung')!;
    expect(samsung.installed).toBe('unknown');
    expect(samsung.checkable).toBe(false);
  });

  it('detects vendor drivers via pnputil on Windows', async () => {
    const pnp = [
      'Published Name: oem1.inf',
      'Provider Name: SAMSUNG Electronics Co., Ltd.',
      'Class Name: Ports',
      'Driver Version: 05/10/2021 2.14.7.0',
    ].join('\n');
    const runner = new FakeRunner({
      'adb version': { code: null, stdout: '', stderr: '' },
      'fastboot --version': { code: null, stdout: '', stderr: '' },
      'pnputil /enum-drivers': ok(pnp),
    });

    const report = await new DriverManagerService(runner, 'win32').list();
    const samsung = report.drivers.find((d) => d.key === 'samsung')!;
    expect(samsung.installed).toBe('yes');
    expect(samsung.version).toBe('05/10/2021 2.14.7.0');

    const qualcomm = report.drivers.find((d) => d.key === 'qualcomm')!;
    expect(qualcomm.installed).toBe('no');
    expect(qualcomm.checkable).toBe(true);

    // ADB CLI missing → not installed.
    const adb = report.drivers.find((d) => d.key === 'adb')!;
    expect(adb.installed).toBe('no');
  });

  it('every catalog driver has an official https download url', async () => {
    const report = await new DriverManagerService(new FakeRunner({}), 'linux').list();
    for (const d of report.drivers) {
      expect(d.downloadUrl.startsWith('https://'), `${d.key} url`).toBe(true);
    }
  });
});
