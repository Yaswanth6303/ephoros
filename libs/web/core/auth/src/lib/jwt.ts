/** Reads `exp` (seconds) from a JWT without verifying it — only to schedule a refresh. */
export function jwtExp(token: string): number {
  const payload = token.split('.')[1] ?? '';
  return JSON.parse(atob(payload.replace(/-/g, '+').replace(/_/g, '/'))).exp;
}
