import type { DriverReport, DriverStatus } from '@shared/types/driver';
import type { CommandRunner } from '../process/CommandRunner';
import { NodeCommandRunner } from '../process/CommandRunner';
import { DRIVER_CATALOG, type DriverInfo } from './catalog';
import { matchDriver, parsePnpUtilDrivers, type PnpDriverEntry } from './pnputil';

/**
 * Reports driver status. On Windows it uses `pnputil /enum-drivers` to detect
 * installed vendor drivers; ADB/Fastboot interface presence is inferred from the
 * CLI being runnable. The suite NEVER installs drivers automatically — it links
 * to the official download page instead (see docs/SECURITY.md).
 */
export class DriverManagerService {
  constructor(
    private readonly runner: CommandRunner = new NodeCommandRunner(),
    private readonly platform: NodeJS.Platform = process.platform,
  ) {}

  private async cliAvailable(binary: string, arg: string): Promise<boolean> {
    const { code } = await this.runner.run(binary, [arg]);
    return code === 0;
  }

  private async pnpEntries(): Promise<PnpDriverEntry[]> {
    if (this.platform !== 'win32') return [];
    const { code, stdout } = await this.runner.run('pnputil', ['/enum-drivers']);
    if (code !== 0) return [];
    return parsePnpUtilDrivers(stdout);
  }

  async list(): Promise<DriverReport> {
    const [adbAvailable, fastbootAvailable, entries] = await Promise.all([
      this.cliAvailable('adb', 'version'),
      this.cliAvailable('fastboot', '--version'),
      this.pnpEntries(),
    ]);

    const drivers = DRIVER_CATALOG.map((info) =>
      this.toStatus(info, adbAvailable, fastbootAvailable, entries),
    );
    return { platform: this.platform, drivers };
  }

  private toStatus(
    info: DriverInfo,
    adbAvailable: boolean,
    fastbootAvailable: boolean,
    entries: PnpDriverEntry[],
  ): DriverStatus {
    const base = {
      key: info.key,
      name: info.name,
      vendor: info.vendor,
      supportedBrands: [...info.supportedBrands],
      description: info.description,
      downloadUrl: info.downloadUrl,
    };

    if (info.detect.type === 'adb' || info.detect.type === 'fastboot') {
      const available = info.detect.type === 'adb' ? adbAvailable : fastbootAvailable;
      return {
        ...base,
        checkable: true,
        installed: available ? 'yes' : 'no',
        version: null,
        status: available ? 'installed' : 'not-installed',
      };
    }

    // pnputil-based detection is only meaningful on Windows.
    if (this.platform !== 'win32') {
      return { ...base, checkable: false, installed: 'unknown', version: null, status: 'unknown' };
    }
    const version = matchDriver(entries, info.detect.match);
    return {
      ...base,
      checkable: true,
      installed: version ? 'yes' : 'no',
      version: version && version !== 'installed' ? version : null,
      status: version ? 'installed' : 'not-installed',
    };
  }
}
