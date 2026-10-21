import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { AuthStore } from '@ephoros/web/core/auth';
import { Login, safeReturnUrl } from './login';

describe('Login', () => {
  let signIn: ReturnType<typeof vi.fn>;

  async function render(returnUrl?: string) {
    signIn = vi.fn(async () => 'ok');
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        { provide: AuthStore, useValue: { signIn } },
      ],
    });
    const router = TestBed.inject(Router);
    if (returnUrl) await router.navigate([], { queryParams: { returnUrl } });
    const navigate = vi.spyOn(router, 'navigateByUrl').mockResolvedValue(true);
    const fixture = TestBed.createComponent(Login);
    await fixture.whenStable();
    const el: HTMLElement = fixture.nativeElement;
    const type = (label: string, value: string) => {
      const input = el.querySelector<HTMLInputElement>(`#${label}`)!;
      input.value = value;
      input.dispatchEvent(new Event('input'));
    };
    const submit = async () => {
      el.querySelector('form')!.dispatchEvent(new Event('submit'));
      await fixture.whenStable();
    };
    return { fixture, el, type, submit, navigate };
  }

  it('shows an inline error for an invalid email and does not call signIn', async () => {
    const { el, type, submit } = await render();
    type('email', 'not-an-email');
    type('password', 'secret');
    await submit();
    expect(el.textContent).toContain('Enter a valid email');
    expect(signIn).not.toHaveBeenCalled();
  });

  it('marks invalid fields for assistive technology (WCAG AA)', async () => {
    const { el, type, submit } = await render();
    type('email', 'not-an-email');
    await submit();
    const input = el.querySelector('#email')!;
    expect(input.getAttribute('aria-invalid')).toBe('true');
    const error = el.querySelector(
      `#${input.getAttribute('aria-describedby')}`,
    );
    expect(error?.textContent).toContain('Enter a valid email');
  });

  it('signs in and navigates to the returnUrl', async () => {
    const { type, submit, navigate } = await render('/incidents');
    type('email', 'ana@ephoros.test');
    type('password', 'secret');
    await submit();
    expect(signIn).toHaveBeenCalledWith('ana@ephoros.test', 'secret');
    expect(navigate).toHaveBeenCalledWith('/incidents');
  });

  it('shows "Invalid email or password" when sign-in fails', async () => {
    const { el, type, submit } = await render();
    signIn.mockResolvedValueOnce('invalid');
    type('email', 'ana@ephoros.test');
    type('password', 'wrong');
    await submit();
    expect(el.querySelector('[role=alert]')?.textContent).toContain(
      'Invalid email or password',
    );
  });

  it('disables the button while signing in', async () => {
    const { el, fixture, type, submit } = await render();
    let finish!: (v: string) => void;
    signIn.mockReturnValueOnce(new Promise((resolve) => (finish = resolve)));
    type('email', 'ana@ephoros.test');
    type('password', 'secret');
    const pending = submit();
    await fixture.whenStable().catch(() => undefined);
    await vi.waitFor(() =>
      expect(el.querySelector('button')!.disabled).toBe(true),
    );
    finish('ok');
    await pending;
  });
});

describe('safeReturnUrl', () => {
  it('ignores an external returnUrl', () => {
    expect(safeReturnUrl('/incidents?x=1')).toBe('/incidents?x=1');
    for (const bad of [
      '//evil.com',
      '/\\evil.com',
      'https://evil.com',
      'javascript:alert(1)',
      null,
    ]) {
      expect(safeReturnUrl(bad)).toBe('/');
    }
  });
});
