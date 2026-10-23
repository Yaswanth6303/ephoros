import { hasRole, type SessionUser } from './session-user';

const user: SessionUser = {
  id: 'u1',
  email: 'a@ephoros.test',
  name: 'A',
  role: 'analyst',
};

describe('hasRole', () => {
  it('matches only the exact role and never a missing user', () => {
    expect(hasRole(user, 'analyst')).toBe(true);
    expect(hasRole(user, 'admin')).toBe(false);
    expect(hasRole(null, 'admin')).toBe(false);
  });
});
