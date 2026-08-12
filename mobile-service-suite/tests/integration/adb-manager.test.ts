// @vitest-environment node
import { describe, it, expect } from 'vitest';
import { AdbManagerService } from '@backend/services/adb/AdbManagerService';
import type { CommandResult, CommandRunner } from '@backend/services/process/CommandRunner';

/** Records the last invocation and returns a scripted result. */
class SpyRunner implements CommandRunner {
  calls: Array<{ command: string; args: string[] }> = [];
  constructor(private readonly result: CommandResult) {}
  run(command: string, args: string[]): Promise<CommandResult> {
    this.calls.push({ command, args });
    return Promise.resolve(this.result);
  }
  get lastArgs(): string[] {
    return this.calls[this.calls.length - 1]?.args ?? [];
  }
}

const okResult: CommandResult = { code: 0, stdout: 'done', stderr: '' };

describe('AdbManagerService', () => {
  it('rejects invalid input before running anything', async () => {
    const spy = new SpyRunner(okResult);
    const svc = new AdbManagerService(spy);

    expect(await svc.reboot('bad serial', 'system')).toEqual({ ok: false, error: 'Invalid device serial' });
    expect(await svc.reboot('ABC', 'edl')).toEqual({ ok: false, error: 'Invalid reboot target: edl' });
    expect(await svc.uninstall('ABC', 'notapackage')).toEqual({ ok: false, error: 'Invalid package name' });
    expect(await svc.shell('ABC', 'rm -rf / ; reboot')).toEqual({
      ok: false,
      error: 'Unsafe or empty shell command',
    });
    expect(spy.calls).toHaveLength(0);
  });

  it('builds the correct reboot args', async () => {
    const spy = new SpyRunner(okResult);
    const svc = new AdbManagerService(spy);

    await svc.reboot('ABC123', 'system');
    expect(spy.lastArgs).toEqual(['-s', 'ABC123', 'reboot']);
    await svc.reboot('ABC123', 'recovery');
    expect(spy.lastArgs).toEqual(['-s', 'ABC123', 'reboot', 'recovery']);
  });

  it('parses `pm list packages` output', async () => {
    const spy = new SpyRunner({
      code: 0,
      stdout: 'package:com.b.app\npackage:com.a.app\n',
      stderr: '',
    });
    const res = await new AdbManagerService(spy).listPackages('ABC123');
    expect(res).toEqual({ ok: true, value: ['com.a.app', 'com.b.app'] });
  });

  it('surfaces adb-not-installed as an error', async () => {
    const spy = new SpyRunner({ code: null, stdout: '', stderr: 'ENOENT' });
    const res = await new AdbManagerService(spy).logcat('ABC123');
    expect(res.ok).toBe(false);
    if (!res.ok) expect(res.error).toMatch(/not installed/);
  });

  it('returns stderr on non-zero exit', async () => {
    const spy = new SpyRunner({ code: 1, stdout: '', stderr: 'device offline' });
    const res = await new AdbManagerService(spy).shell('ABC123', 'getprop');
    expect(res).toEqual({ ok: false, error: 'device offline' });
  });
});
