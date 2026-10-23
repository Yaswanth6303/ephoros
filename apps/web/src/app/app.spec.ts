import { provideHttpClient } from '@angular/common/http';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { client, provideHeyApiClient } from '@ephoros/api-contract';
import { AuthStore } from '@ephoros/web/auth/data-access';
import { App } from './app';

describe('App', () => {
  const signOut = vi.fn(async () => undefined);

  async function render(status: 'authenticated' | 'anonymous') {
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        provideHttpClient(),
        provideHttpClientTesting(),
        provideHeyApiClient(client),
        { provide: AuthStore, useValue: { status: signal(status), signOut } },
      ],
    });
    // no whenStable here: it would wait on the pending /api/v1/me request the tests answer
    const fixture = TestBed.createComponent(App);
    return { fixture, el: fixture.nativeElement as HTMLElement };
  }

  it('renders the router outlet inside the main landmark', async () => {
    const { el, fixture } = await render('anonymous');
    await fixture.whenStable();
    expect(
      el.querySelector('main')?.querySelector('router-outlet'),
    ).toBeInstanceOf(HTMLElement);
    expect(el.querySelector('header')).toBeNull();
  });

  it('shows the signed-in email and role from /api/v1/me', async () => {
    const { el, fixture } = await render('authenticated');
    const req = await vi.waitFor(() =>
      TestBed.inject(HttpTestingController).expectOne('/api/v1/me'),
    );
    req.flush({
      sub: 'u1',
      email: 'ana@ephoros.test',
      name: 'Ana',
      role: 'analyst',
    });
    await fixture.whenStable();
    expect(el.querySelector('header')?.textContent).toContain(
      'ana@ephoros.test',
    );
    expect(el.querySelector('header')?.textContent).toContain('analyst');
  });

  it('sign out returns to /login', async () => {
    const { el } = await render('authenticated');
    (
      await vi.waitFor(() =>
        TestBed.inject(HttpTestingController).expectOne('/api/v1/me'),
      )
    ).flush({
      sub: 'u1',
      email: 'ana@ephoros.test',
      name: 'Ana',
      role: 'analyst',
    });
    const navigate = vi
      .spyOn(TestBed.inject(Router), 'navigateByUrl')
      .mockResolvedValue(true);
    el.querySelector<HTMLButtonElement>('header button')!.click();
    await vi.waitFor(() => expect(navigate).toHaveBeenCalled());
    expect(signOut).toHaveBeenCalled();
    expect(navigate).toHaveBeenCalledWith('/login');
  });
});
