import { memoryAdapter } from 'better-auth/adapters/memory';
import { describe, expect, it } from 'vitest';
import { createAuth } from './auth.ts';
import { seedUsers } from './seed.ts';

describe('seedUsers', () => {
  it('creates missing users once and is idempotent', async () => {
    const auth = createAuth({
      database: memoryAdapter({
        user: [],
        session: [],
        account: [],
        verification: [],
        jwks: [],
      }),
      secret: 'x'.repeat(32),
      baseURL: 'https://ephoros.test',
    });
    const users = [
      {
        email: 'a@ephoros.test',
        password: 'test-password',
        name: 'A',
        role: 'admin' as const,
      },
    ];
    expect(await seedUsers(auth, users)).toEqual(['a@ephoros.test']);
    expect(await seedUsers(auth, users)).toEqual([]);
  });
});
