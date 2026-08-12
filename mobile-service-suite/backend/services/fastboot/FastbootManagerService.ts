import { ok, err, type Result } from '@shared/types/result';
import type { CommandRunner } from '../process/CommandRunner';
import { NodeCommandRunner } from '../process/CommandRunner';
import { parseFastbootDevices, parseFastbootVars } from './parsers';
import {
  isFastbootRebootTarget,
  isValidPartition,
  isValidSerial,
  isValidVarName,
} from './validation';

/**
 * High-level Fastboot operations. Destructive actions (unlock, lock, erase,
 * flash) are gated behind an explicit confirmation in the UI and additionally
 * validate their inputs here as defence in depth.
 *
 * The suite performs bootloader lock/unlock ONLY as an explicit, confirmed
 * technician action; it never bypasses account protection (see SECURITY.md).
 */
export class FastbootManagerService {
  private readonly runner: CommandRunner;

  constructor(
    runner: CommandRunner = new NodeCommandRunner(),
    private readonly binary = 'fastboot',
  ) {
    this.runner = runner;
  }

  private async exec(args: string[], timeoutMs?: number): Promise<Result<string>> {
    const { code, stdout, stderr } = await this.runner.run(this.binary, args, timeoutMs);
    if (code === null) return err('fastboot is not installed or could not be started');
    // Fastboot prints progress to stderr even on success, so combine streams.
    const output = `${stdout}\n${stderr}`.trim();
    if (code !== 0) return err(output || `fastboot exited with code ${code}`);
    return ok(output);
  }

  async listDevices(): Promise<Result<string[]>> {
    const { code, stdout } = await this.runner.run(this.binary, ['devices']);
    if (code === null) return err('fastboot is not installed or could not be started');
    if (code !== 0) return err(`fastboot exited with code ${code}`);
    return ok(parseFastbootDevices(stdout));
  }

  async getVar(serial: string, name: string): Promise<Result<string>> {
    if (!isValidSerial(serial)) return err('Invalid device serial');
    if (!isValidVarName(name)) return err('Invalid variable name');
    const { stdout, stderr, code } = await this.runner.run(this.binary, [
      '-s',
      serial,
      'getvar',
      name,
    ]);
    if (code === null) return err('fastboot is not installed or could not be started');
    const vars = parseFastbootVars(`${stderr}\n${stdout}`);
    const value = vars[name];
    return value !== undefined ? ok(value) : err(`Variable not found: ${name}`);
  }

  async getAllVars(serial: string): Promise<Result<Record<string, string>>> {
    if (!isValidSerial(serial)) return err('Invalid device serial');
    const { stdout, stderr, code } = await this.runner.run(this.binary, [
      '-s',
      serial,
      'getvar',
      'all',
    ]);
    if (code === null) return err('fastboot is not installed or could not be started');
    return ok(parseFastbootVars(`${stderr}\n${stdout}`));
  }

  reboot(serial: string, target: string): Promise<Result<string>> {
    if (!isValidSerial(serial)) return Promise.resolve(err('Invalid device serial'));
    if (!isFastbootRebootTarget(target)) {
      return Promise.resolve(err(`Invalid reboot target: ${target}`));
    }
    const argsByTarget: Record<string, string[]> = {
      system: ['-s', serial, 'reboot'],
      bootloader: ['-s', serial, 'reboot-bootloader'],
      recovery: ['-s', serial, 'reboot', 'recovery'],
      fastboot: ['-s', serial, 'reboot', 'fastboot'],
    };
    return this.exec(argsByTarget[target] ?? ['-s', serial, 'reboot']);
  }

  // ---- Sensitive operations (confirmed in the UI) ----

  unlock(serial: string): Promise<Result<string>> {
    if (!isValidSerial(serial)) return Promise.resolve(err('Invalid device serial'));
    return this.exec(['-s', serial, 'flashing', 'unlock'], 60_000);
  }

  lock(serial: string): Promise<Result<string>> {
    if (!isValidSerial(serial)) return Promise.resolve(err('Invalid device serial'));
    return this.exec(['-s', serial, 'flashing', 'lock'], 60_000);
  }

  erase(serial: string, partition: string): Promise<Result<string>> {
    if (!isValidSerial(serial)) return Promise.resolve(err('Invalid device serial'));
    if (!isValidPartition(partition)) return Promise.resolve(err('Invalid partition name'));
    return this.exec(['-s', serial, 'erase', partition], 60_000);
  }

  flash(serial: string, partition: string, imagePath: string): Promise<Result<string>> {
    if (!isValidSerial(serial)) return Promise.resolve(err('Invalid device serial'));
    if (!isValidPartition(partition)) return Promise.resolve(err('Invalid partition name'));
    if (!imagePath.trim()) return Promise.resolve(err('Image path is required'));
    return this.exec(['-s', serial, 'flash', partition, imagePath], 300_000);
  }
}
