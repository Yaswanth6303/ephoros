import { Component, inject, resource } from '@angular/core';
import { Router, RouterOutlet } from '@angular/router';
import { me } from '@ephoros/api-contract';
import { AuthStore } from '@ephoros/web/auth/data-access';
import { HlmBadgeImports } from '@spartan-ng/helm/badge';
import { HlmButtonImports } from '@spartan-ng/helm/button';

@Component({
  selector: 'eph-root',
  imports: [RouterOutlet, HlmBadgeImports, HlmButtonImports],
  templateUrl: './app.html',
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
