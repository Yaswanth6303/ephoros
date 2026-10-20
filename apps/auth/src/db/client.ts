import { drizzleAdapter } from 'better-auth/adapters/drizzle';
import { drizzle } from 'drizzle-orm/node-postgres';
import pg from 'pg';
import { createAuth } from '../auth.ts';
import { env } from '../env.ts';
import * as schema from './schema.ts';

export const pool = new pg.Pool({ connectionString: env.databaseUrl });
const db = drizzle(pool, { schema });

export const auth = createAuth({
  database: drizzleAdapter(db, { provider: 'pg', schema, schemaName: 'auth' }),
  secret: env.secret,
  baseURL: env.baseUrl,
});
