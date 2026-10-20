import {
  HttpErrorResponse,
  type HttpInterceptorFn,
} from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, from, switchMap, throwError } from 'rxjs';
import { AuthStore } from './auth-store';

/** Adds the API JWT to /api/v1 calls; any auth failure sends the user to /login. */
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  if (!req.url.startsWith('/api/v1/')) return next(req);
  const store = inject(AuthStore);
  const router = inject(Router);
  const toLogin = (error: unknown) => {
    store.expire();
    void router.navigate(['/login'], {
      queryParams: { returnUrl: router.url },
    });
    return throwError(() => error);
  };
  return from(store.accessToken()).pipe(
    catchError(toLogin),
    switchMap((token) =>
      next(req.clone({ setHeaders: { Authorization: `Bearer ${token}` } })),
    ),
    catchError((error) =>
      error instanceof HttpErrorResponse && error.status === 401
        ? toLogin(error)
        : throwError(() => error),
    ),
  );
};
