import { join } from 'node:path';

function env(name: string): string {
  const value = process.env[name];
  if (!value)
    throw new Error(`Set ${name} (see .env.example) before running e2e`);
  return value;
}

export const users = {
  analyst: {
    email: env('SEED_ANALYST_EMAIL'),
    password: env('SEED_ANALYST_PASSWORD'),
  },
  admin: {
    email: env('SEED_ADMIN_EMAIL'),
    password: env('SEED_ADMIN_PASSWORD'),
  },
};

export const storageStateFor = (role: keyof typeof users) =>
  join(__dirname, '..', '.auth', `${role}.json`);
