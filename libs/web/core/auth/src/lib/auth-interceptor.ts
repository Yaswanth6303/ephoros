import {
  HttpErrorResponse,
  type HttpInterceptorFn,
  type HttpRequest,
} from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, from, switchMap, throwError } from 'rxjs';
import { AuthStore, SessionExpiredError } from './auth-store';

const isUnauthorized = (error: unknown) =>
  error instanceof HttpErrorResponse && error.status === 401;

/**
 * Adds the API JWT to /api/v1 calls. An API 401 (clock skew, token expired in flight) gets one
 * retry with a fresh token; only a session the auth service rejects sends the user to /login.
 */
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
  const send = (request: HttpRequest<unknown>) =>
    from(store.accessToken()).pipe(
      switchMap((token) =>
        next(
          request.clone({ setHeaders: { Authorization: `Bearer ${token}` } }),
        ),
      ),
    );
  const onAuthFailure = (error: unknown) =>
    error instanceof SessionExpiredError || isUnauthorized(error)
      ? toLogin(error)
      : throwError(() => error);

  return send(req).pipe(
    catchError((error) => {
      if (!isUnauthorized(error)) return onAuthFailure(error);
      store.invalidateToken();
      return send(req).pipe(catchError(onAuthFailure));
    }),
  );
};
