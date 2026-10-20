import type { Auth } from './auth.ts';

export type SeedUser = {
  email: string;
  password: string;
  name: string;
  role: 'admin' | 'analyst';
};

/** Creates users that do not exist yet; returns the emails it created. */
export async function seedUsers(
  auth: Auth,
  users: SeedUser[],
): Promise<string[]> {
  const ctx = await auth.$context;
  const created: string[] = [];
  for (const user of users) {
    if (await ctx.internalAdapter.findUserByEmail(user.email)) continue;
    await auth.api.createUser({ body: user });
    created.push(user.email);
  }
  return created;
}

function seedUser(prefix: string, role: SeedUser['role']): SeedUser {
  const email = process.env[`${prefix}_EMAIL`];
  const password = process.env[`${prefix}_PASSWORD`];
  if (!email || !password)
    throw new Error(`Set ${prefix}_EMAIL and ${prefix}_PASSWORD`);
  return {
    email,
    password,
    name: role === 'admin' ? 'Admin' : 'Analyst',
    role,
  };
}

if (import.meta.main) {
  const { auth, pool } = await import('./db/client.ts');
  const created = await seedUsers(auth, [
    seedUser('SEED_ADMIN', 'admin'),
    seedUser('SEED_ANALYST', 'analyst'),
  ]);
  console.log(
    created.length ? `created: ${created.join(', ')}` : 'nothing to create',
  );
  await pool.end();
}
