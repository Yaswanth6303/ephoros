import { DOCUMENT, inject, InjectionToken } from '@angular/core';
import { createAuthClient } from 'better-auth/client';
import { jwtClient } from 'better-auth/client/plugins';
import type { SessionUser } from '@ephoros/web/auth/domain';

/** The slice of the Better Auth client the app uses; tests provide a fake. */
export interface AuthApi {
  getSession(): Promise<{ data: { user: SessionUser } | null }>;
  signIn: {
    email(body: {
      email: string;
      password: string;
    }): Promise<{ error: { status: number } | null }>;
  };
  signOut(): Promise<unknown>;
  token(): Promise<{
    data: { token: string } | null;
    error?: { status: number } | null;
  }>;
}

export const AUTH_CLIENT = new InjectionToken<AuthApi>('AUTH_CLIENT', {
  factory: () =>
    createAuthClient({
      baseURL: inject(DOCUMENT).location.origin,
      plugins: [jwtClient()],
    }) as unknown as AuthApi,
});
