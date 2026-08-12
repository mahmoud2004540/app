import { ok, err, type Result } from '@shared/types/result';
import type { ToolReport, ToolStatus } from '@shared/types/tool';
import type { CommandRunner } from '../process/CommandRunner';
import { TOOL_CATALOG, type ToolInfo } from './catalog';
import { parseToolVersion } from './version';

/** Persistence of user-configured executable paths (implemented by ToolRepository). */
export interface ToolPathStore {
  getPath(key: string): string | null;
  setPath(key: string, name: string, path: string): void;
}

export interface ToolLogSink {
  append(entry: { level: 'INFO' | 'SUCCESS' | 'FAILED'; tool: string; operation: string; result?: string; error?: string }): void;
}

export interface ToolManagerDeps {
  runner: CommandRunner;
  store: ToolPathStore;
  fileExists: (path: string) => boolean;
  launch: (path: string) => Result<string>;
  log?: ToolLogSink;
}

/**
 * Detects tool availability and launches external tools from the technician's
 * own installation. It never bundles or modifies commercial tools — it only
 * runs the executable the user points it at, and records the launch.
 */
export class ToolManagerService {
  constructor(private readonly deps: ToolManagerDeps) {}

  async list(): Promise<ToolReport> {
    const tools = await Promise.all(TOOL_CATALOG.map((info) => this.status(info)));
    return { tools };
  }

  private async status(info: ToolInfo): Promise<ToolStatus> {
    const base = {
      key: info.key,
      name: info.name,
      vendor: info.vendor,
      kind: info.kind,
      supportedBrands: [...info.supportedBrands],
      description: info.description,
      url: info.url,
    };

    if (info.detect.type === 'cli') {
      const { code, stdout, stderr } = await this.deps.runner.run(info.detect.binary, [
        info.detect.versionArg,
      ]);
      const available = code === 0;
      return {
        ...base,
        installed: available ? 'yes' : 'no',
        version: available ? parseToolVersion(`${stdout}\n${stderr}`) : null,
        path: null,
      };
    }

    const path = this.deps.store.getPath(info.key);
    if (!path) return { ...base, installed: 'unknown', version: null, path: null };
    return {
      ...base,
      installed: this.deps.fileExists(path) ? 'yes' : 'no',
      version: null,
      path,
    };
  }

  private find(key: string): ToolInfo | undefined {
    return TOOL_CATALOG.find((t) => t.key === key);
  }

  async setPath(key: string, path: string): Promise<Result<ToolStatus>> {
    const info = this.find(key);
    if (!info) return err(`Unknown tool: ${key}`);
    if (info.detect.type !== 'external') return err('Path applies to external tools only');
    if (!path.trim()) return err('Path is required');
    if (!this.deps.fileExists(path)) return err('File not found at the given path');
    this.deps.store.setPath(key, info.name, path);
    return ok(await this.status(info));
  }

  async checkVersion(key: string): Promise<Result<string>> {
    const info = this.find(key);
    if (!info) return err(`Unknown tool: ${key}`);
    if (info.detect.type !== 'cli') {
      return err('Automatic version check is available for CLI tools only');
    }
    const { code, stdout, stderr } = await this.deps.runner.run(info.detect.binary, [
      info.detect.versionArg,
    ]);
    if (code !== 0) return err('Tool is not installed or not on PATH');
    return ok(parseToolVersion(`${stdout}\n${stderr}`) ?? 'unknown');
  }

  /** Launch an external tool from its configured path (External Tool Launcher). */
  launch(key: string): Result<string> {
    const info = this.find(key);
    if (!info) return err(`Unknown tool: ${key}`);
    if (info.detect.type !== 'external') {
      return err('CLI tools are used from the ADB/Fastboot pages');
    }
    const path = this.deps.store.getPath(key);
    if (!path) return err('Set the tool path first');
    if (!this.deps.fileExists(path)) return err('Executable not found at the configured path');

    const result = this.deps.launch(path);
    this.deps.log?.append({
      level: result.ok ? 'SUCCESS' : 'FAILED',
      tool: info.name,
      operation: 'launch',
      ...(result.ok ? { result: path } : { error: result.error }),
    });
    return result;
  }
}
