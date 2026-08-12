import { execFile } from 'node:child_process';

export interface CommandResult {
  code: number | null;
  stdout: string;
  stderr: string;
}

/**
 * Abstraction over running an external process. The service layer depends on
 * this interface so tests can inject canned output without any real binary.
 */
export interface CommandRunner {
  run(command: string, args: string[], timeoutMs?: number): Promise<CommandResult>;
}

/** Real implementation backed by child_process.execFile. */
export class NodeCommandRunner implements CommandRunner {
  run(command: string, args: string[], timeoutMs = 15_000): Promise<CommandResult> {
    return new Promise((resolve) => {
      execFile(
        command,
        args,
        { timeout: timeoutMs, windowsHide: true, maxBuffer: 8 * 1024 * 1024 },
        (error, stdout, stderr) => {
          if (error && typeof error.code === 'string') {
            // Spawn failure (e.g. ENOENT: binary not installed).
            resolve({ code: null, stdout: '', stderr: String(error.message) });
            return;
          }
          const code = error && typeof error.code === 'number' ? error.code : 0;
          resolve({ code, stdout: stdout.toString(), stderr: stderr.toString() });
        },
      );
    });
  }
}
