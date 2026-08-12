// @vitest-environment node
import { describe, it, expect } from 'vitest';
import { ToolManagerService, type ToolPathStore } from '@backend/services/tools/ToolManagerService';
import { parseToolVersion } from '@backend/services/tools/version';
import { ok, err } from '@shared/types/result';
import type { CommandResult, CommandRunner } from '@backend/services/process/CommandRunner';

class FakeRunner implements CommandRunner {
  constructor(private readonly table: Record<string, CommandResult>) {}
  run(command: string, args: string[]): Promise<CommandResult> {
    const key = [command, ...args].join(' ');
    return Promise.resolve(this.table[key] ?? { code: null, stdout: '', stderr: 'ENOENT' });
  }
}

class MemStore implements ToolPathStore {
  private map = new Map<string, string>();
  getPath(key: string): string | null {
    return this.map.get(key) ?? null;
  }
  setPath(key: string, _name: string, path: string): void {
    this.map.set(key, path);
  }
}

function makeService(opts: {
  runner?: CommandRunner;
  existing?: Set<string>;
  launched?: string[];
}): { svc: ToolManagerService; store: MemStore } {
  const store = new MemStore();
  const svc = new ToolManagerService({
    runner: opts.runner ?? new FakeRunner({}),
    store,
    fileExists: (p) => opts.existing?.has(p) ?? false,
    launch: (p) => {
      opts.launched?.push(p);
      return ok('launched');
    },
  });
  return { svc, store };
}

describe('parseToolVersion', () => {
  it('extracts dotted versions', () => {
    expect(parseToolVersion('Android Debug Bridge version 1.0.41')).toBe('1.0.41');
    expect(parseToolVersion('fastboot version 34.0.0-11609240')).toBe('34.0.0');
    expect(parseToolVersion('no version')).toBeNull();
  });
});

describe('ToolManagerService', () => {
  it('detects CLI tools and parses version', async () => {
    const runner = new FakeRunner({
      'adb version': { code: 0, stdout: 'Android Debug Bridge version 1.0.41', stderr: '' },
      'fastboot --version': { code: null, stdout: '', stderr: '' },
    });
    const { svc } = makeService({ runner });
    const report = await svc.list();
    const adb = report.tools.find((t) => t.key === 'adb')!;
    expect(adb.installed).toBe('yes');
    expect(adb.version).toBe('1.0.41');
    const fb = report.tools.find((t) => t.key === 'fastboot')!;
    expect(fb.installed).toBe('no');
  });

  it('reports external tools as unknown until a path is set', async () => {
    const { svc } = makeService({});
    const report = await svc.list();
    const odin = report.tools.find((t) => t.key === 'odin')!;
    expect(odin.installed).toBe('unknown');
    expect(odin.path).toBeNull();
  });

  it('sets an external tool path only when the file exists', async () => {
    const existing = new Set(['/opt/odin/Odin3.exe']);
    const { svc } = makeService({ existing });
    expect(await svc.setPath('odin', '/nope')).toEqual({
      ok: false,
      error: 'File not found at the given path',
    });
    const good = await svc.setPath('odin', '/opt/odin/Odin3.exe');
    expect(good.ok).toBe(true);
    if (good.ok) {
      expect(good.value.installed).toBe('yes');
      expect(good.value.path).toBe('/opt/odin/Odin3.exe');
    }
  });

  it('rejects setPath on a CLI tool', async () => {
    const { svc } = makeService({ existing: new Set(['/x']) });
    expect(await svc.setPath('adb', '/x')).toEqual({
      ok: false,
      error: 'Path applies to external tools only',
    });
  });

  it('launches an external tool from its configured path', async () => {
    const launched: string[] = [];
    const existing = new Set(['/opt/odin/Odin3.exe']);
    const { svc } = makeService({ existing, launched });
    expect(svc.launch('odin')).toEqual(err('Set the tool path first'));
    await svc.setPath('odin', '/opt/odin/Odin3.exe');
    expect(svc.launch('odin')).toEqual(ok('launched'));
    expect(launched).toEqual(['/opt/odin/Odin3.exe']);
  });

  it('refuses to launch CLI tools', () => {
    const { svc } = makeService({});
    expect(svc.launch('adb')).toEqual(err('CLI tools are used from the ADB/Fastboot pages'));
  });
});
