import { inject, Service, signal } from '@angular/core';
import type { SessionUser } from '@ephoros/web/auth/domain';
import { jwtExp } from '@ephoros/web/shared/util';
import { AUTH_CLIENT } from './auth-client';

const REFRESH_BEFORE_MS = 60_000;

/** The auth service says there is no valid session (401) — the user must sign in again. */
export class SessionExpiredError extends Error {}

@Service()
export class AuthStore {
  private readonly client = inject(AUTH_CLIENT);
  private readonly _user = signal<SessionUser | null>(null);
  private readonly _status = signal<'unknown' | 'authenticated' | 'anonymous'>(
    'unknown',
  );
  private token: string | null = null;
  private refreshing: Promise<string> | null = null;
  private generation = 0; // bumped by expire(): refreshes started before it are discarded

  readonly user = this._user.asReadonly();
  readonly status = this._status.asReadonly();

  async load(): Promise<void> {
    try {
      const { data } = await this.client.getSession();
      this.setUser(data?.user ?? null);
    } catch {
      this.setUser(null);
    }
  }

  async signIn(
    email: string,
    password: string,
  ): Promise<'ok' | 'invalid' | 'error'> {
    const { error } = await this.client.signIn.email({ email, password });
    if (error) return error.status === 401 ? 'invalid' : 'error';
    await this.load();
    return 'ok';
  }

  async signOut(): Promise<void> {
    await this.client.signOut();
    this.expire();
  }

  /** Clears local auth state (sign-out, or the API answered 401). */
  expire(): void {
    this.generation++;
    this.token = null;
    this.refreshing = null;
    this.setUser(null);
  }

  /** Drops the cached JWT so the next accessToken() fetches a fresh one (e.g. after an API 401). */
  invalidateToken(): void {
    this.token = null;
  }

  /** A short-lived API JWT, refreshed shortly before it expires; concurrent callers share one fetch. */
  accessToken(): Promise<string> {
    if (
      this.token &&
      jwtExp(this.token) * 1000 - Date.now() > REFRESH_BEFORE_MS
    ) {
      return Promise.resolve(this.token);
    }
    const generation = this.generation;
    this.refreshing ??= this.client
      .token()
      .then(({ data, error }) => {
        if (!data) {
          throw error?.status === 401
            ? new SessionExpiredError('Session expired')
            : new Error(
                `Auth service unavailable (${error?.status ?? 'network'})`,
              );
        }
        if (generation !== this.generation)
          throw new SessionExpiredError('Signed out');
        this.token = data.token;
        return data.token;
      })
      .finally(() => {
        if (generation === this.generation) this.refreshing = null;
      });
    return this.refreshing;
  }

  private setUser(user: SessionUser | null): void {
    this._user.set(user);
    this._status.set(user ? 'authenticated' : 'anonymous');
  }
}
