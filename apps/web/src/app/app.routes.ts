import type { Route } from '@angular/router';
import { authGuard } from '@ephoros/web/auth/data-access';

export const appRoutes: Route[] = [
  {
    path: 'login',
    loadComponent: () =>
      import('@ephoros/web/auth/feature-login').then((m) => m.Login),
  },
  {
    path: '',
    canMatch: [authGuard],
    loadComponent: () => import('./status/status').then((m) => m.Status),
  },
  { path: '**', redirectTo: '' },
];
