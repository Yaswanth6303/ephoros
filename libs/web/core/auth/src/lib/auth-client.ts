import { InjectionToken } from '@angular/core';
import { createAuthClient } from 'better-auth/client';
import { jwtClient } from 'better-auth/client/plugins';

export type SessionUser = {
  id: string;
  email: string;
  name: string;
  role: string;
};

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
  token(): Promise<{ data: { token: string } | null }>;
}

export const AUTH_CLIENT = new InjectionToken<AuthApi>('AUTH_CLIENT', {
  factory: () =>
    createAuthClient({
      baseURL: location.origin,
      plugins: [jwtClient()],
    }) as unknown as AuthApi,
});
