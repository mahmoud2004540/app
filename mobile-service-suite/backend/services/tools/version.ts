/** Extract a dotted version number from a CLI tool's `--version` output. */
export function parseToolVersion(output: string): string | null {
  const match = /(\d+\.\d+(?:\.\d+){0,2})/.exec(output);
  return match && match[1] !== undefined ? match[1] : null;
}
