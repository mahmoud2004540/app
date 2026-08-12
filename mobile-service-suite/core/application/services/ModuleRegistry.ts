import type { IBrandModule } from '../../domain/services/IBrandModule';

/**
 * In-memory registry that lets brand/platform modules be plugged in at runtime.
 *
 * This is the extension point promised by the architecture: adding a brand means
 * registering a module here, never editing the core. PHASE 10 populates it with
 * real modules; PHASE 22 queries it for smart tool recommendations.
 */
export class ModuleRegistry {
  private readonly modules = new Map<string, IBrandModule>();

  register(module: IBrandModule): void {
    if (this.modules.has(module.id)) {
      throw new Error(`Module "${module.id}" is already registered`);
    }
    this.modules.set(module.id, module);
  }

  get(id: string): IBrandModule | undefined {
    return this.modules.get(id);
  }

  list(): IBrandModule[] {
    return [...this.modules.values()];
  }

  /** Find the first module that claims it can handle the given device string. */
  findByDevice(manufacturerOrChipset: string): IBrandModule | undefined {
    return this.list().find((m) => m.matches(manufacturerOrChipset));
  }

  get size(): number {
    return this.modules.size;
  }
}
