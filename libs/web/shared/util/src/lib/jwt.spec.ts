import { jwtExp } from './jwt';

describe('jwtExp', () => {
  it('reads exp from a base64url payload', () => {
    const payload = btoa(JSON.stringify({ exp: 1700000000 })).replace(
      /=+$/,
      '',
    );
    expect(jwtExp(`header.${payload}.signature`)).toBe(1700000000);
  });
});
