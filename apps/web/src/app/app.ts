import { Component, inject, resource } from '@angular/core';
import { Router, RouterOutlet } from '@angular/router';
import { me } from '@ephoros/api-contract';
import { AuthStore } from '@ephoros/web/auth/data-access';
import { HlmBadgeImports } from '@spartan-ng/helm/badge';
import { HlmButtonImports } from '@spartan-ng/helm/button';

@Component({
  selector: 'eph-root',
  imports: [RouterOutlet, HlmBadgeImports, HlmButtonImports],
  template: `
    @if (store.status() === 'authenticated') {
      <header class="flex items-center justify-between border-b px-6 py-3">
        <span class="font-semibold">Ephoros</span>
        <div class="flex items-center gap-3 text-sm">
          @if (principal.hasValue()) {
            <span>{{ principal.value().email }}</span>
            <span hlmBadge variant="secondary">{{
              principal.value().role
            }}</span>
          }
          <button hlmBtn variant="outline" size="sm" (click)="signOut()">
            Sign out
          </button>
        </div>
      </header>
    }
    <main class="p-6"><router-outlet /></main>
  `,
})
export class App {
  protected readonly store = inject(AuthStore);
  private readonly router = inject(Router);

  // read from the API (not the session) so the header proves the browser's JWT works end to end
  protected readonly principal = resource({
    params: () => (this.store.status() === 'authenticated' ? true : undefined),
    loader: async () => (await me({ throwOnError: true })).data,
  });

  protected async signOut(): Promise<void> {
    await this.store.signOut();
    await this.router.navigateByUrl('/login');
  }
}
