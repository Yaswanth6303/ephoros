import { defineConfig } from 'drizzle-kit';

export default defineConfig({
  dialect: 'postgresql',
  schema: './src/db/schema.ts',
  out: './drizzle',
  schemaFilter: ['auth'],
  migrations: { schema: 'auth' },
  dbCredentials: { url: process.env['DATABASE_URL'] ?? '' },
});
