import type { Migration } from './types';
import { migration001Init } from './001_init';

/**
 * Ordered list of all migrations. Append new migrations here with the next
 * version number — never edit or reorder existing ones (forward-only).
 */
export const MIGRATIONS: readonly Migration[] = [migration001Init];

export type { Migration } from './types';
