import type { SupportedBrand, SupportedPlatform } from '@shared/constants/app';

/**
 * Contract every brand / platform module must satisfy (Modular Architecture).
 *
 * A new brand or tool is added by dropping a module under /modules that exports
 * an object implementing this interface and registering it — no changes to the
 * core system are required. Feature phases (PHASE 10+) flesh out the members.
 */
export interface IBrandModule {
  /** Stable identifier, e.g. "samsung". */
  readonly id: SupportedBrand | SupportedPlatform | string;

  /** Human-readable name, e.g. "Samsung". */
  readonly displayName: string;

  /** External tools this module recommends, e.g. ["odin"]. */
  readonly recommendedTools: readonly string[];

  /**
   * Return true if this module can handle the given detected manufacturer /
   * chipset string. Used by the smart tool recommendation engine (PHASE 22).
   */
  matches(manufacturerOrChipset: string): boolean;
}
