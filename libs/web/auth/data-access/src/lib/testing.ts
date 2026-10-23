import type { SessionUser } from '@ephoros/web/auth/domain';
import type { AuthApi } from './auth-client';

/** Unsigned JWT-shaped string with the given `exp` (seconds). Tests only. */
export function fakeJwt(exp: number): string {
  const payload = btoa(JSON.stringify({ exp })).replace(/=+$/, '');
  return `header.${payload}.signature`;
}

export const analyst: SessionUser = {
  id: 'u1',
  email: 'ana@ephoros.test',
  name: 'Ana',
  role: 'analyst',
};

export function fakeAuthApi(user: SessionUser | null = analyst) {
  const nowSeconds = () => Math.floor(Date.now() / 1000);
  const api = {
    user,
    tokenTtl: 900,
    getSession: vi.fn(async () => ({
      data: api.user ? { user: api.user } : null,
    })),
    signIn: {
      email: vi.fn(async ({ password }: { email: string; password: string }) =>
        password === 'right' ? { error: null } : { error: { status: 401 } },
      ),
    },
    signOut: vi.fn(async () => ({})),
    token: vi.fn(
      async (): Promise<{
        data: { token: string } | null;
        error: { status: number } | null;
      }> =>
        api.user
          ? {
              data: { token: fakeJwt(nowSeconds() + api.tokenTtl) },
              error: null,
            }
          : { data: null, error: { status: 401 } },
    ),
  };
  return api satisfies AuthApi;
}
