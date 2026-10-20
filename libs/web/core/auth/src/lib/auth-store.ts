import { inject, Injectable, signal } from '@angular/core';
import { AUTH_CLIENT, type SessionUser } from './auth-client';
import { jwtExp } from './jwt';

const REFRESH_BEFORE_MS = 60_000;

@Injectable({ providedIn: 'root' })
export class AuthStore {
  private readonly client = inject(AUTH_CLIENT);
  private readonly _user = signal<SessionUser | null>(null);
  private readonly _status = signal<'unknown' | 'authenticated' | 'anonymous'>(
    'unknown',
  );
  private token: string | null = null;
  private refreshing: Promise<string> | null = null;

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
    this.token = null;
    this.setUser(null);
  }

  /** A short-lived API JWT, refreshed shortly before it expires; concurrent callers share one fetch. */
  accessToken(): Promise<string> {
    if (
      this.token &&
      jwtExp(this.token) * 1000 - Date.now() > REFRESH_BEFORE_MS
    ) {
      return Promise.resolve(this.token);
    }
    this.refreshing ??= this.client
      .token()
      .then(({ data }) => {
        if (!data) throw new Error('No active session');
        this.token = data.token;
        return data.token;
      })
      .finally(() => (this.refreshing = null));
    return this.refreshing;
  }

  private setUser(user: SessionUser | null): void {
    this._user.set(user);
    this._status.set(user ? 'authenticated' : 'anonymous');
  }
}
