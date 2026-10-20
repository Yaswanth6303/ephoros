/** False in tests/SSR (no matchMedia) and when the user prefers reduced motion. */
export function motionAllowed(): boolean {
  return (
    typeof matchMedia === 'function' &&
    !matchMedia('(prefers-reduced-motion: reduce)').matches
  );
}
