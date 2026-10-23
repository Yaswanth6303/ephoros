import { Component, inject, signal } from '@angular/core';
import {
  email,
  type FieldTree,
  form,
  FormField,
  required,
  submit,
} from '@angular/forms/signals';
import { ActivatedRoute, Router } from '@angular/router';
import { AuthStore } from '@ephoros/web/auth/data-access';
import {
  InlineError,
  LoadingButton,
} from '@ephoros/web/shared/ui/interactions';
import { HlmButtonImports } from '@spartan-ng/helm/button';
import { HlmCardImports } from '@spartan-ng/helm/card';
import { HlmFieldImports } from '@spartan-ng/helm/field';
import { HlmInputImports } from '@spartan-ng/helm/input';

/** Only same-app paths; anything else (`//host`, `/\host`, `https:`, `javascript:`) goes home. */
export function safeReturnUrl(raw: string | null): string {
  return raw?.startsWith('/') && !raw.startsWith('//') && !raw.startsWith('/\\')
    ? raw
    : '/';
}

@Component({
  selector: 'eph-login',
  imports: [
    FormField,
    InlineError,
    LoadingButton,
    HlmButtonImports,
    HlmCardImports,
    HlmFieldImports,
    HlmInputImports,
  ],
  template: `
    <div class="flex min-h-[70vh] items-center justify-center">
      <section hlmCard class="w-full max-w-sm">
        <div hlmCardHeader>
          <h1 hlmCardTitle>Sign in to Ephoros</h1>
          <p hlmCardDescription>Analyst and admin accounts only.</p>
        </div>
        <form
          hlmCardContent
          class="grid gap-4"
          novalidate
          (submit)="onSubmit($event)"
        >
          <div hlmField>
            <label hlmFieldLabel for="email">Email</label>
            <input
              hlmInput
              id="email"
              type="email"
              autocomplete="username"
              [formField]="loginForm.email"
            />
            <eph-inline-error [message]="errorOf(loginForm.email)" />
          </div>
          <div hlmField>
            <label hlmFieldLabel for="password">Password</label>
            <input
              hlmInput
              id="password"
              type="password"
              autocomplete="current-password"
              [formField]="loginForm.password"
            />
            <eph-inline-error [message]="errorOf(loginForm.password)" />
          </div>
          @if (failure(); as text) {
            <p role="alert" class="text-destructive text-sm">{{ text }}</p>
          }
          <button
            hlmBtn
            ephLoadingButton
            type="submit"
            [loading]="loginForm().submitting()"
          >
            Sign in
          </button>
        </form>
      </section>
    </div>
  `,
})
export class Login {
  private readonly store = inject(AuthStore);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);

  protected readonly failure = signal<string | null>(null);
  protected readonly loginForm = form(
    signal({ email: '', password: '' }),
    (p) => {
      required(p.email, { message: 'Email is required' });
      email(p.email, { message: 'Enter a valid email' });
      required(p.password, { message: 'Password is required' });
    },
  );

  protected errorOf(field: FieldTree<string>): string | null {
    const state = field();
    return state.touched() ? (state.errors()[0]?.message ?? null) : null;
  }

  protected async onSubmit(event: Event): Promise<void> {
    event.preventDefault();
    this.failure.set(null);
    await submit(this.loginForm, async (f) => {
      const { email, password } = f().value();
      const result = await this.store.signIn(email, password);
      if (result === 'ok') {
        await this.router.navigateByUrl(
          safeReturnUrl(this.route.snapshot.queryParamMap.get('returnUrl')),
        );
      } else {
        this.failure.set(
          result === 'invalid'
            ? 'Invalid email or password'
            : 'Sign-in is unavailable, try again shortly',
        );
      }
      return undefined;
    });
  }
}
