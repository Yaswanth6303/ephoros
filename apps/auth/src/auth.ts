import { betterAuth, type BetterAuthOptions } from 'better-auth';
import { admin, jwt } from 'better-auth/plugins';
import { createAccessControl } from 'better-auth/plugins/access';
import {
  adminAc,
  defaultStatements,
  userAc,
} from 'better-auth/plugins/admin/access';

const ac = createAccessControl(defaultStatements);
const roles = {
  admin: ac.newRole(adminAc.statements),
  analyst: ac.newRole(userAc.statements),
};

export function createAuth(opts: {
  database: BetterAuthOptions['database'];
  secret: string;
  baseURL: string;
}) {
  return betterAuth({
    database: opts.database,
    secret: opts.secret,
    baseURL: opts.baseURL,
    trustedOrigins: [opts.baseURL],
    // users are created by an admin (seed now, admin UI later), never self-registered
    emailAndPassword: { enabled: true, disableSignUp: true },
    plugins: [
      jwt({
        jwt: {
          issuer: opts.baseURL,
          audience: 'ephoros-api',
          expirationTime: '15m',
          definePayload: ({ user }) => ({
            email: user.email,
            name: user.name,
            role: user['role'],
          }),
        },
      }),
      admin({ ac, roles, defaultRole: 'analyst', adminRoles: ['admin'] }),
    ],
  });
}

export type Auth = ReturnType<typeof createAuth>;
