/**
 * Generic repository contract (Repository Pattern).
 *
 * Concrete repositories (SQLite-backed) implement this interface in the backend
 * layer starting in PHASE 4. The domain and service layers depend only on this
 * abstraction, never on a specific database — keeping the core decoupled.
 */
export interface IRepository<TEntity, TId = number> {
  findById(id: TId): Promise<TEntity | null>;
  findAll(): Promise<TEntity[]>;
  create(entity: Omit<TEntity, 'id'>): Promise<TEntity>;
  update(id: TId, changes: Partial<TEntity>): Promise<TEntity | null>;
  delete(id: TId): Promise<boolean>;
}
