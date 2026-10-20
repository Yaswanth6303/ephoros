import { memoryAdapter } from 'better-auth/adapters/memory';
import { createLocalJWKSet, type JSONWebKeySet, jwtVerify } from 'jose';
import { beforeAll, describe, expect, it } from 'vitest';
import { createApp } from './app.ts';
import { createAuth } from './auth.ts';

const baseURL = 'https://ephoros.test';
const email = 'analyst@ephoros.test';
const password = 'correct-horse-9';

const post = (body: unknown) => ({
  method: 'POST',
  headers: { 'content-type': 'application/json', origin: baseURL },
  body: JSON.stringify(body),
});

describe('auth service', () => {
  const auth = createAuth({
    database: memoryAdapter({
      user: [],
      session: [],
      account: [],
      verification: [],
      jwks: [],
    }),
    secret: 'x'.repeat(32),
    baseURL,
  });
  const app = createApp(auth);

  beforeAll(async () => {
    await auth.api.createUser({
      body: { email, password, name: 'Ana', role: 'analyst' },
    });
  });

  it('signs in and issues a 15-minute EdDSA JWT that verifies against the JWKS', async () => {
    const signIn = await app.request(
      '/api/auth/sign-in/email',
      post({ email, password }),
    );
    expect(signIn.status).toBe(200);
    const cookie = signIn.headers
      .getSetCookie()
      .map((c) => c.split(';')[0])
      .join('; ');
    const { token } = (await (
      await app.request('/api/auth/token', { headers: { cookie } })
    ).json()) as {
      token: string;
    };
    const jwks = (await (
      await app.request('/api/auth/jwks')
    ).json()) as JSONWebKeySet;
    const { payload, protectedHeader } = await jwtVerify(
      token,
      createLocalJWKSet(jwks),
      {
        issuer: baseURL,
        audience: 'ephoros-api',
      },
    );
    expect(protectedHeader.alg).toBe('EdDSA');
    expect(payload).toMatchObject({ email, role: 'analyst' });
    expect(Number(payload.exp) - Number(payload.iat)).toBe(900);
  });

  it('rejects a wrong password', async () => {
    const r = await app.request(
      '/api/auth/sign-in/email',
      post({ email, password: 'nope-nope-1' }),
    );
    expect(r.status).toBe(401);
  });

  it('rejects public sign-up', async () => {
    const intruder = {
      email: 'intruder@ephoros.test',
      password: 'whatever-123',
      name: 'X',
    };
    const r = await app.request('/api/auth/sign-up/email', post(intruder));
    expect(r.ok).toBe(false);
    const signIn = await app.request('/api/auth/sign-in/email', post(intruder));
    expect(signIn.status).toBe(401);
  });
});
