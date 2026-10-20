function required(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`Missing environment variable ${name}`);
  return value;
}

export const env = {
  databaseUrl: required('DATABASE_URL'),
  secret: required('BETTER_AUTH_SECRET'),
  baseUrl: required('BETTER_AUTH_URL'),
  port: Number(process.env['PORT'] ?? 3000),
};
