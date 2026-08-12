import type { DetectionResult } from '@shared/types/device';

/**
 * Service-layer contract for device detection (Service Layer pattern).
 *
 * Implemented in PHASE 5 against ADB/Fastboot. Declared in the domain so the UI
 * and other services can depend on the abstraction rather than the concrete
 * process-driven implementation.
 */
export interface IDeviceDetectionService {
  /** Probe USB via ADB and Fastboot, returning tool availability + devices. */
  detect(): Promise<DetectionResult>;
}
