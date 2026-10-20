import type { Route } from '@angular/router';
import { authGuard } from '@ephoros/web/core/auth';

export const appRoutes: Route[] = [
  {
    path: 'login',
    loadComponent: () =>
      import('@ephoros/web/feature-login').then((m) => m.Login),
  },
  {
    path: '',
    canMatch: [authGuard],
    loadComponent: () => import('./status/status').then((m) => m.Status),
  },
  { path: '**', redirectTo: '' },
];
