import { ModuleRegistry } from '@core/application/services/ModuleRegistry';
import type { IBrandModule } from '@core/domain/services/IBrandModule';

// Brand modules
import { samsungModule } from './samsung';
import { xiaomiModule } from './xiaomi';
import { huaweiModule } from './huawei';
import { honorModule } from './honor';
import { oppoModule } from './oppo';
import { realmeModule } from './realme';
import { oneplusModule } from './oneplus';
import { vivoModule } from './vivo';
import { tecnoModule } from './tecno';
import { infinixModule } from './infinix';
import { itelModule } from './itel';
import { motorolaModule } from './motorola';
import { googleModule } from './google';
import { sonyModule } from './sony';
import { nokiaModule } from './nokia';
// Platform (chipset) modules
import { qualcommModule } from './qualcomm';
import { mediatekModule } from './mediatek';
import { unisocModule } from './unisoc';

export const ALL_MODULES: readonly IBrandModule[] = [
  samsungModule,
  xiaomiModule,
  huaweiModule,
  honorModule,
  oppoModule,
  realmeModule,
  oneplusModule,
  vivoModule,
  tecnoModule,
  infinixModule,
  itelModule,
  motorolaModule,
  googleModule,
  sonyModule,
  nokiaModule,
  qualcommModule,
  mediatekModule,
  unisocModule,
];

/** Build a fresh registry with every module registered. */
export function createModuleRegistry(): ModuleRegistry {
  const registry = new ModuleRegistry();
  for (const module of ALL_MODULES) registry.register(module);
  return registry;
}

/** Shared singleton used across the app. */
export const moduleRegistry = createModuleRegistry();

export interface DeviceHint {
  brand?: string | undefined;
  manufacturer?: string | undefined;
  chipset?: string | undefined;
}

export interface ToolRecommendation {
  brand: IBrandModule | null;
  platform: IBrandModule | null;
  /** Ordered, de-duplicated tool keys (baseline adb/fastboot always included). */
  tools: string[];
}

/**
 * Smart tool recommendation (PHASE 22 core): match the detected brand and
 * chipset against the registered modules and merge their recommended tools with
 * the always-available adb/fastboot baseline.
 */
export function recommendToolsForDevice(
  hint: DeviceHint,
  registry: ModuleRegistry = moduleRegistry,
): ToolRecommendation {
  const modules = registry.list();
  const brandCandidates = [hint.brand, hint.manufacturer].filter(
    (v): v is string => typeof v === 'string' && v.length > 0,
  );

  const brand =
    modules.find((m) => m.kind === 'brand' && brandCandidates.some((c) => m.matches(c))) ?? null;
  const platform =
    hint.chipset && hint.chipset.length > 0
      ? (modules.find((m) => m.kind === 'platform' && m.matches(hint.chipset as string)) ?? null)
      : null;

  const tools = [
    ...(brand?.recommendedTools ?? []),
    ...(platform?.recommendedTools ?? []),
    'adb',
    'fastboot',
  ];
  return { brand, platform, tools: [...new Set(tools)] };
}
