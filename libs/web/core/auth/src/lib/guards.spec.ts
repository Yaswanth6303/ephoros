import { TestBed } from '@angular/core/testing';
import { provideRouter, Router, UrlSegment, UrlTree } from '@angular/router';
import { AUTH_CLIENT } from './auth-client';
import { authGuard, roleGuard } from './guards';
import { analyst, fakeAuthApi } from './testing';

const segments = [new UrlSegment('incidents', {})];

function setup(user: Parameters<typeof fakeAuthApi>[0]) {
  TestBed.configureTestingModule({
    providers: [
      provideRouter([]),
      { provide: AUTH_CLIENT, useValue: fakeAuthApi(user) },
    ],
  });
}

const run = (guard: typeof authGuard) =>
  TestBed.runInInjectionContext(() =>
    guard({}, segments, {} as never),
  ) as Promise<boolean | UrlTree>;

describe('guards', () => {
  it('redirects anonymous users to /login with returnUrl', async () => {
    setup(null);
    const result = await run(authGuard);
    expect(TestBed.inject(Router).serializeUrl(result as UrlTree)).toBe(
      '/login?returnUrl=%2Fincidents',
    );
  });

  it('lets authenticated users through', async () => {
    setup(undefined);
    expect(await run(authGuard)).toBe(true);
  });

  it('roleGuard blocks analysts from admin routes', async () => {
    setup(undefined);
    await run(authGuard);
    const result = await run(roleGuard('admin'));
    expect(result).toBeInstanceOf(UrlTree);
  });

  it('roleGuard works on its own: guards in one array run concurrently', async () => {
    setup({ ...analyst, role: 'admin' });
    expect(await run(roleGuard('admin'))).toBe(true);
  });
});
