import type { IBrandModule } from '@core/domain/services/IBrandModule';

export interface ModuleDefinition {
  id: string;
  displayName: string;
  kind: 'brand' | 'platform';
  recommendedTools: string[];
  /** Lower-cased substrings matched against the detected manufacturer / chipset. */
  aliases: string[];
}

/**
 * Factory that builds an {@link IBrandModule} from declarative data, deriving the
 * `matches` predicate from `aliases`. Keeps each brand/platform module to a few
 * lines so new ones are trivial to add (Modular Architecture).
 */
export function defineModule(def: ModuleDefinition): IBrandModule {
  const needles = def.aliases.map((a) => a.toLowerCase());
  return {
    id: def.id,
    displayName: def.displayName,
    kind: def.kind,
    recommendedTools: def.recommendedTools,
    matches(value: string): boolean {
      const hay = value.toLowerCase();
      return needles.some((n) => hay.includes(n));
    },
  };
}
