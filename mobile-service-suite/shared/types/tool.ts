import type { TriBool } from './device';

export type ToolKind = 'cli' | 'external';

/** Presentation status for one external/CLI tool. */
export interface ToolStatus {
  key: string;
  name: string;
  vendor: string;
  kind: ToolKind;
  supportedBrands: string[];
  description: string;
  /** Official vendor page. The suite launches the tool but never bundles or cracks it. */
  url: string;
  installed: TriBool;
  version: string | null;
  /** Configured executable path (external tools) or null. */
  path: string | null;
}

export interface ToolReport {
  tools: ToolStatus[];
}
