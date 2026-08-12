// @vitest-environment node
import { describe, it, expect } from 'vitest';
import { AppDatabase } from '@backend/database/Database';
import { ToolRepository } from '@backend/database/repositories/ToolRepository';

describe('ToolRepository', () => {
  it('persists and updates a tool path', () => {
    const db = AppDatabase.open(':memory:');
    const repo = new ToolRepository(db.connection);

    expect(repo.getPath('odin')).toBeNull();
    repo.setPath('odin', 'Odin', 'C:/tools/Odin3.exe');
    expect(repo.getPath('odin')).toBe('C:/tools/Odin3.exe');

    repo.setPath('odin', 'Odin', 'D:/Odin/Odin3.exe'); // upsert
    expect(repo.getPath('odin')).toBe('D:/Odin/Odin3.exe');
    expect(repo.all()).toHaveLength(1);

    db.close();
  });
});
