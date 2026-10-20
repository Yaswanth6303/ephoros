import { Component, resource } from '@angular/core';
import { healthz } from '@ephoros/api-contract';

@Component({
  selector: 'eph-status',
  template: `
    @if (health.hasValue()) {
      <p>API: ok</p>
    } @else if (health.error()) {
      <p>API: unreachable</p>
    }
  `,
})
export class Status {
  protected readonly health = resource({
    loader: () => healthz({ throwOnError: true }),
  });
}
