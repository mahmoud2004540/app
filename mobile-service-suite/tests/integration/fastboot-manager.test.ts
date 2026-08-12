// @vitest-environment node
import { describe, it, expect } from 'vitest';
import { FastbootManagerService } from '@backend/services/fastboot/FastbootManagerService';
import type { CommandResult, CommandRunner } from '@backend/services/process/CommandRunner';

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

const okResult: CommandResult = { code: 0, stdout: '', stderr: 'OKAY' };

describe('FastbootManagerService', () => {
  it('validates input before running', async () => {
    const spy = new SpyRunner(okResult);
    const svc = new FastbootManagerService(spy);
    expect(await svc.reboot('bad serial', 'system')).toEqual({
      ok: false,
      error: 'Invalid device serial',
    });
    expect(await svc.erase('FB123', '../etc')).toEqual({
      ok: false,
      error: 'Invalid partition name',
    });
    expect(await svc.reboot('FB123', 'edl')).toEqual({
      ok: false,
      error: 'Invalid reboot target: edl',
    });
    expect(spy.calls).toHaveLength(0);
  });

  it('builds correct args for reboot targets', async () => {
    const spy = new SpyRunner(okResult);
    const svc = new FastbootManagerService(spy);
    await svc.reboot('FB123', 'bootloader');
    expect(spy.lastArgs).toEqual(['-s', 'FB123', 'reboot-bootloader']);
    await svc.reboot('FB123', 'fastboot');
    expect(spy.lastArgs).toEqual(['-s', 'FB123', 'reboot', 'fastboot']);
  });

  it('builds correct args for unlock and flash', async () => {
    const spy = new SpyRunner(okResult);
    const svc = new FastbootManagerService(spy);
    await svc.unlock('FB123');
    expect(spy.lastArgs).toEqual(['-s', 'FB123', 'flashing', 'unlock']);
    await svc.flash('FB123', 'boot', '/img/boot.img');
    expect(spy.lastArgs).toEqual(['-s', 'FB123', 'flash', 'boot', '/img/boot.img']);
  });

  it('reads a variable from getvar output', async () => {
    const spy = new SpyRunner({ code: 0, stdout: '', stderr: '(bootloader) unlocked: yes' });
    const res = await new FastbootManagerService(spy).getVar('FB123', 'unlocked');
    expect(res).toEqual({ ok: true, value: 'yes' });
  });

  it('reports fastboot missing', async () => {
    const spy = new SpyRunner({ code: null, stdout: '', stderr: 'ENOENT' });
    const res = await new FastbootManagerService(spy).listDevices();
    expect(res.ok).toBe(false);
  });
});
