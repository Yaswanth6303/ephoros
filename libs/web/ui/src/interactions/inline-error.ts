/*
 * Motion design ported from interior "Inline Validation" (https://github.com/ddoemonn/interior).
 * MIT License, Copyright (c) ddoemonn. See THIRD_PARTY_NOTICES.md.
 */
import { Component, input } from '@angular/core';

@Component({
  selector: 'eph-inline-error',
  host: { 'aria-live': 'polite', class: 'block' },
  template: `
    @if (message(); as text) {
      <p
        animate.enter="motion-safe:animate-in motion-safe:fade-in motion-safe:slide-in-from-top-1 duration-200"
        class="text-destructive mt-1 text-sm"
      >
        {{ text }}
      </p>
    }
  `,
})
export class InlineError {
  readonly message = input<string | null>(null);
}
