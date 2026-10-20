// Used only by `auth generate` to emit the Drizzle schema; the running service builds auth in main.ts.
import { drizzleAdapter } from 'better-auth/adapters/drizzle';
import { createAuth } from './auth.ts';

export const auth = createAuth({
  database: drizzleAdapter({} as never, { provider: 'pg', schemaName: 'auth' }),
  secret: 'x'.repeat(32),
  baseURL: 'http://localhost',
});
