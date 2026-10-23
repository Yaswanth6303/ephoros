export type Role = 'admin' | 'analyst';

export type SessionUser = {
  id: string;
  email: string;
  name: string;
  role: string;
};

export function hasRole(user: SessionUser | null, role: Role): boolean {
  return user?.role === role;
}
