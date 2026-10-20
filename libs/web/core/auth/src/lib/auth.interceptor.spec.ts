import {
  HttpClient,
  provideHttpClient,
  withInterceptors,
} from '@angular/common/http';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { AUTH_CLIENT } from './auth-client';
import { authInterceptor } from './auth.interceptor';
import { AuthStore } from './auth-store';
import { fakeAuthApi } from './testing';

describe('authInterceptor', () => {
  let http: HttpClient;
  let backend: HttpTestingController;
  let api: ReturnType<typeof fakeAuthApi>;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
        { provide: AUTH_CLIENT, useValue: (api = fakeAuthApi()) },
      ],
    });
    http = TestBed.inject(HttpClient);
    backend = TestBed.inject(HttpTestingController);
  });

  it('adds the bearer token to /api/v1 requests', async () => {
    const done = firstValueFrom(http.get('/api/v1/me'));
    const req = await vi.waitFor(() => backend.expectOne('/api/v1/me'));
    expect(req.request.headers.get('Authorization')).toMatch(
      /^Bearer header\./,
    );
    req.flush({});
    await done;
  });

  it('does not add it to /api/auth requests', () => {
    http.get('/api/auth/get-session').subscribe();
    const req = backend.expectOne('/api/auth/get-session');
    expect(req.request.headers.has('Authorization')).toBe(false);
  });

  async function call() {
    const done = firstValueFrom(http.get('/api/v1/me')).catch((e) => e);
    const next = () => vi.waitFor(() => backend.expectOne('/api/v1/me'));
    return { done, next };
  }

  it('retries once with a fresh token when the API answers 401', async () => {
    const expire = vi.spyOn(TestBed.inject(AuthStore), 'expire');
    const { done, next } = await call();
    (await next()).flush('', { status: 401, statusText: 'Unauthorized' });
    const retry = await next();
    expect(retry.request.headers.get('Authorization')).toMatch(/^Bearer /);
    retry.flush({ ok: true });
    expect(await done).toEqual({ ok: true });
    expect(expire).not.toHaveBeenCalled();
    expect(api.token).toHaveBeenCalledTimes(2);
  });

  it('expires the session and redirects to login when the retry is also 401', async () => {
    const store = TestBed.inject(AuthStore);
    const navigate = vi
      .spyOn(TestBed.inject(Router), 'navigate')
      .mockResolvedValue(true);
    const expire = vi.spyOn(store, 'expire');
    const { done, next } = await call();
    (await next()).flush('', { status: 401, statusText: 'Unauthorized' });
    (await next()).flush('', { status: 401, statusText: 'Unauthorized' });
    expect((await done).status).toBe(401);
    expect(expire).toHaveBeenCalled();
    expect(navigate).toHaveBeenCalledWith(['/login'], {
      queryParams: { returnUrl: '/' },
    });
  });

  it('does not log out when the auth service is unavailable', async () => {
    const navigate = vi
      .spyOn(TestBed.inject(Router), 'navigate')
      .mockResolvedValue(true);
    api.token.mockResolvedValueOnce({ data: null, error: { status: 503 } });
    const result = await firstValueFrom(http.get('/api/v1/me')).catch((e) => e);
    expect(result).toBeInstanceOf(Error);
    expect(navigate).not.toHaveBeenCalled();
    expect(TestBed.inject(AuthStore).status()).not.toBe('anonymous');
  });
});
