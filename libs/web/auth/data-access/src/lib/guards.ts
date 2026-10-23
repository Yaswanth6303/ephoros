import { inject } from '@angular/core';
import { type CanMatchFn, Router } from '@angular/router';
import { hasRole, type Role } from '@ephoros/web/auth/domain';
import { AuthStore } from './auth-store';

// guards in one array run concurrently, so each loads the session itself instead of relying on another
async function sessionUser(store: AuthStore) {
  if (store.status() === 'unknown') await store.load();
  return store.user();
}

export const authGuard: CanMatchFn = async (_route, segments) => {
  const router = inject(Router);
  if (await sessionUser(inject(AuthStore))) return true;
  const returnUrl = '/' + segments.map((s) => s.path).join('/');
  return router.createUrlTree(['/login'], { queryParams: { returnUrl } });
};

export const roleGuard =
  (role: Role): CanMatchFn =>
  async () => {
    const router = inject(Router);
    const user = await sessionUser(inject(AuthStore));
    return hasRole(user, role) || router.createUrlTree(['/']);
  };
