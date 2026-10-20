import { inject } from '@angular/core';
import { type CanMatchFn, Router } from '@angular/router';
import { AuthStore } from './auth-store';

export const authGuard: CanMatchFn = async (_route, segments) => {
  const store = inject(AuthStore);
  const router = inject(Router);
  if (store.status() === 'unknown') await store.load();
  if (store.status() === 'authenticated') return true;
  const returnUrl = '/' + segments.map((s) => s.path).join('/');
  return router.createUrlTree(['/login'], { queryParams: { returnUrl } });
};

export const roleGuard =
  (role: 'admin'): CanMatchFn =>
  () =>
    inject(AuthStore).user()?.role === role ||
    inject(Router).createUrlTree(['/']);
