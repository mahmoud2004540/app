import type { CommandRunner } from '../process/CommandRunner';
import {
  parseAdbDevices,
  parseBatteryLevel,
  parseGetprop,
  parseMemTotalKb,
  type AdbDeviceLine,
} from './parsers';

/** Thin, typed wrapper around the `adb` CLI. */
export class AdbClient {
  constructor(
    private readonly runner: CommandRunner,
    private readonly binary = 'adb',
  ) {}

  async isAvailable(): Promise<boolean> {
    const { code } = await this.runner.run(this.binary, ['version']);
    return code === 0;
  }

  async listDevices(): Promise<AdbDeviceLine[]> {
    const { code, stdout } = await this.runner.run(this.binary, ['devices']);
    if (code !== 0) return [];
    return parseAdbDevices(stdout);
  }

  async getProps(serial: string): Promise<Record<string, string>> {
    const { code, stdout } = await this.runner.run(this.binary, ['-s', serial, 'shell', 'getprop']);
    if (code !== 0) return {};
    return parseGetprop(stdout);
  }

  async getBatteryLevel(serial: string): Promise<number | undefined> {
    const { code, stdout } = await this.runner.run(this.binary, [
      '-s',
      serial,
      'shell',
      'dumpsys',
      'battery',
    ]);
    if (code !== 0) return undefined;
    return parseBatteryLevel(stdout);
  }

  async getTotalRamKb(serial: string): Promise<number | undefined> {
    const { code, stdout } = await this.runner.run(this.binary, [
      '-s',
      serial,
      'shell',
      'cat',
      '/proc/meminfo',
    ]);
    if (code !== 0) return undefined;
    return parseMemTotalKb(stdout);
  }
}
