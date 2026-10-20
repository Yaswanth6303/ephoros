import { Hono } from 'hono';
import type { Auth } from './auth.ts';

export function createApp(auth: Auth): Hono {
  const app = new Hono();
  app.all('/api/auth/*', (c) => auth.handler(c.req.raw));
  return app;
}
