import type { CommandRunner } from '../process/CommandRunner';
import { parseFastbootDevices, parseFastbootVar } from './parsers';

/** Thin, typed wrapper around the `fastboot` CLI. */
export class FastbootClient {
  constructor(
    private readonly runner: CommandRunner,
    private readonly binary = 'fastboot',
  ) {}

  async isAvailable(): Promise<boolean> {
    const { code } = await this.runner.run(this.binary, ['--version']);
    return code === 0;
  }

  async listDevices(): Promise<string[]> {
    const { code, stdout } = await this.runner.run(this.binary, ['devices']);
    if (code !== 0) return [];
    return parseFastbootDevices(stdout);
  }

  /** Read a bootloader variable. Fastboot prints to stderr, so we scan both. */
  async getVar(serial: string, name: string): Promise<string | undefined> {
    const { stdout, stderr } = await this.runner.run(this.binary, [
      '-s',
      serial,
      'getvar',
      name,
    ]);
    return parseFastbootVar(`${stderr}\n${stdout}`, name);
  }
}
