import { Component, resource } from '@angular/core';
import { healthz } from '@ephoros/api-contract';

@Component({
  selector: 'eph-status',
  templateUrl: './status.html',
})
export class Status {
  protected readonly health = resource({
    loader: () => healthz({ throwOnError: true }),
  });
}
