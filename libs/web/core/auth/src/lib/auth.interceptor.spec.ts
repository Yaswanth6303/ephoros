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

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
        { provide: AUTH_CLIENT, useValue: fakeAuthApi() },
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

  it('expires the session and redirects to login on 401', async () => {
    const store = TestBed.inject(AuthStore);
    const navigate = vi
      .spyOn(TestBed.inject(Router), 'navigate')
      .mockResolvedValue(true);
    const expire = vi.spyOn(store, 'expire');
    const done = firstValueFrom(http.get('/api/v1/me')).catch((e) => e);
    (await vi.waitFor(() => backend.expectOne('/api/v1/me'))).flush('', {
      status: 401,
      statusText: 'Unauthorized',
    });
    expect((await done).status).toBe(401);
    expect(expire).toHaveBeenCalled();
    expect(navigate).toHaveBeenCalledWith(['/login'], {
      queryParams: { returnUrl: '/' },
    });
  });
});
