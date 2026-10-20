import { serve } from '@hono/node-server';
import { createApp } from './app.ts';
import { auth } from './db/client.ts';
import { env } from './env.ts';

serve({ fetch: createApp(auth).fetch, port: env.port }, ({ port }) =>
  console.log(`auth listening on :${port}`),
);
