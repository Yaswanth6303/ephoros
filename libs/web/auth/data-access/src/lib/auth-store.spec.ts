import { TestBed } from '@angular/core/testing';
import { AUTH_CLIENT } from './auth-client';
import { AuthStore, SessionExpiredError } from './auth-store';
import { analyst, fakeAuthApi } from './testing';

describe('AuthStore', () => {
  let api: ReturnType<typeof fakeAuthApi>;
  let store: AuthStore;

  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['Date'] });
    api = fakeAuthApi();
    TestBed.configureTestingModule({
      providers: [{ provide: AUTH_CLIENT, useValue: api }],
    });
    store = TestBed.inject(AuthStore);
  });
  afterEach(() => vi.useRealTimers());

  it('signIn loads the user on success', async () => {
    expect(await store.signIn(analyst.email, 'right')).toBe('ok');
    expect(store.user()).toEqual(analyst);
    expect(store.status()).toBe('authenticated');
  });

  it('signIn returns invalid on 401', async () => {
    expect(await store.signIn(analyst.email, 'wrong')).toBe('invalid');
  });

  it('signIn returns error when the auth service fails for another reason', async () => {
    api.signIn.email.mockResolvedValueOnce({ error: { status: 429 } });
    expect(await store.signIn(analyst.email, 'right')).toBe('error');
  });

  it('accessToken reuses a fresh token', async () => {
    const first = await store.accessToken();
    expect(await store.accessToken()).toBe(first);
    expect(api.token).toHaveBeenCalledTimes(1);
  });

  it('refreshes the token when it is about to expire', async () => {
    api.tokenTtl = 90;
    await store.accessToken();
    vi.advanceTimersByTime(31_000); // 59 s left, inside the 60 s refresh window
    await store.accessToken();
    expect(api.token).toHaveBeenCalledTimes(2);
  });

  it('shares one refresh between concurrent callers', async () => {
    const [a, b] = await Promise.all([
      store.accessToken(),
      store.accessToken(),
    ]);
    expect(a).toBe(b);
    expect(api.token).toHaveBeenCalledTimes(1);
  });

  it('accessToken rejects without a session', async () => {
    api.user = null;
    await expect(store.accessToken()).rejects.toThrow();
  });

  it('signOut clears the user and the cached token', async () => {
    await store.signIn(analyst.email, 'right');
    await store.accessToken();
    await store.signOut();
    expect(store.user()).toBeNull();
    expect(store.status()).toBe('anonymous');
    await store.accessToken().catch(() => undefined);
    expect(api.token).toHaveBeenCalledTimes(2);
  });

  it('a non-401 token failure rejects without signing the user out', async () => {
    await store.signIn(analyst.email, 'right');
    api.token.mockResolvedValueOnce({ data: null, error: { status: 503 } });
    await expect(store.accessToken()).rejects.not.toBeInstanceOf(
      SessionExpiredError,
    );
    expect(store.status()).toBe('authenticated');
  });

  it('a 401 from the auth service rejects with SessionExpiredError', async () => {
    api.user = null;
    await expect(store.accessToken()).rejects.toBeInstanceOf(
      SessionExpiredError,
    );
  });

  it('signOut during a refresh does not keep the old token', async () => {
    let release!: () => void;
    api.token.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          release = () => resolve({ data: { token: 'stale' }, error: null });
        }),
    );
    const inFlight = store.accessToken();
    await store.signOut();
    release();
    await inFlight.catch(() => undefined);
    api.user = analyst;
    expect(await store.accessToken()).not.toBe('stale');
  });
});
