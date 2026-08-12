import { ok, err, type Result } from '@shared/types/result';
import type { CommandRunner } from '../process/CommandRunner';
import { NodeCommandRunner } from '../process/CommandRunner';
import {
  isRebootTarget,
  isSafeShellCommand,
  isValidHostPort,
  isValidPackageName,
  isValidSerial,
} from './validation';

const DEVICE_SCREENSHOT_PATH = '/sdcard/mss_screenshot.png';

/**
 * High-level ADB operations used by the ADB Manager page. Every method validates
 * its inputs before touching the CLI. Destructive actions are gated behind an
 * explicit confirmation in the UI; this layer additionally refuses malformed
 * input as defence in depth.
 */
export class AdbManagerService {
  private readonly runner: CommandRunner;

  constructor(
    runner: CommandRunner = new NodeCommandRunner(),
    private readonly binary = 'adb',
  ) {
    this.runner = runner;
  }

  private async exec(args: string[], timeoutMs?: number): Promise<Result<string>> {
    const { code, stdout, stderr } = await this.runner.run(this.binary, args, timeoutMs);
    if (code === null) return err('adb is not installed or could not be started');
    if (code !== 0) return err(stderr.trim() || `adb exited with code ${code}`);
    return ok(stdout.trim());
  }

  reboot(serial: string, target: string): Promise<Result<string>> {
    if (!isValidSerial(serial)) return Promise.resolve(err('Invalid device serial'));
    if (!isRebootTarget(target)) return Promise.resolve(err(`Invalid reboot target: ${target}`));
    const args =
      target === 'system'
        ? ['-s', serial, 'reboot']
        : ['-s', serial, 'reboot', target];
    return this.exec(args);
  }

  connect(hostPort: string): Promise<Result<string>> {
    if (!isValidHostPort(hostPort)) return Promise.resolve(err('Invalid host:port'));
    return this.exec(['connect', hostPort]);
  }

  disconnect(hostPort?: string): Promise<Result<string>> {
    if (hostPort !== undefined && !isValidHostPort(hostPort)) {
      return Promise.resolve(err('Invalid host:port'));
    }
    return this.exec(hostPort ? ['disconnect', hostPort] : ['disconnect']);
  }

  install(serial: string, apkPath: string): Promise<Result<string>> {
    if (!isValidSerial(serial)) return Promise.resolve(err('Invalid device serial'));
    if (!apkPath.trim()) return Promise.resolve(err('APK path is required'));
    return this.exec(['-s', serial, 'install', '-r', apkPath], 120_000);
  }

  uninstall(serial: string, pkg: string): Promise<Result<string>> {
    if (!isValidSerial(serial)) return Promise.resolve(err('Invalid device serial'));
    if (!isValidPackageName(pkg)) return Promise.resolve(err('Invalid package name'));
    return this.exec(['-s', serial, 'uninstall', pkg]);
  }

  async listPackages(serial: string): Promise<Result<string[]>> {
    if (!isValidSerial(serial)) return err('Invalid device serial');
    const res = await this.exec(['-s', serial, 'shell', 'pm', 'list', 'packages']);
    if (!res.ok) return res;
    const packages = res.value
      .split(/\r?\n/)
      .map((l) => l.replace(/^package:/, '').trim())
      .filter((l) => l.length > 0)
      .sort();
    return ok(packages);
  }

  shell(serial: string, command: string): Promise<Result<string>> {
    if (!isValidSerial(serial)) return Promise.resolve(err('Invalid device serial'));
    if (!isSafeShellCommand(command)) return Promise.resolve(err('Unsafe or empty shell command'));
    return this.exec(['-s', serial, 'shell', command]);
  }

  pull(serial: string, remotePath: string, localPath: string): Promise<Result<string>> {
    if (!isValidSerial(serial)) return Promise.resolve(err('Invalid device serial'));
    if (!remotePath.trim() || !localPath.trim()) return Promise.resolve(err('Paths are required'));
    return this.exec(['-s', serial, 'pull', remotePath, localPath], 120_000);
  }

  push(serial: string, localPath: string, remotePath: string): Promise<Result<string>> {
    if (!isValidSerial(serial)) return Promise.resolve(err('Invalid device serial'));
    if (!localPath.trim() || !remotePath.trim()) return Promise.resolve(err('Paths are required'));
    return this.exec(['-s', serial, 'push', localPath, remotePath], 120_000);
  }

  logcat(serial: string, lines = 200): Promise<Result<string>> {
    if (!isValidSerial(serial)) return Promise.resolve(err('Invalid device serial'));
    const count = Math.min(Math.max(Math.floor(lines), 1), 5000);
    return this.exec(['-s', serial, 'logcat', '-d', '-t', String(count)]);
  }

  /** Capture a screenshot on the device and pull it to a local PNG path. */
  async screenshot(serial: string, localPath: string): Promise<Result<string>> {
    if (!isValidSerial(serial)) return err('Invalid device serial');
    if (!localPath.trim()) return err('Destination path is required');
    const capture = await this.exec([
      '-s',
      serial,
      'shell',
      'screencap',
      '-p',
      DEVICE_SCREENSHOT_PATH,
    ]);
    if (!capture.ok) return capture;
    const pulled = await this.pull(serial, DEVICE_SCREENSHOT_PATH, localPath);
    if (!pulled.ok) return pulled;
    await this.exec(['-s', serial, 'shell', 'rm', '-f', DEVICE_SCREENSHOT_PATH]);
    return ok(localPath);
  }
}
