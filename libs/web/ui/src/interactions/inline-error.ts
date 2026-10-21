/*
 * Motion design ported from interior "Inline Validation" (https://github.com/ddoemonn/interior).
 * MIT License, Copyright (c) ddoemonn. See THIRD_PARTY_NOTICES.md.
 */
import { Component, DestroyRef, inject, input } from '@angular/core';
import { BrnFieldA11yService } from '@spartan-ng/brain/field';

let nextId = 0;

@Component({
  selector: 'eph-inline-error',
  host: { 'aria-live': 'polite', class: 'block', '[id]': '_id' },
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
  protected readonly _id = `eph-inline-error-${nextId++}`;

  constructor() {
    // inside an hlmField, the field's control gets aria-describedby pointing here (same as hlm-field-error)
    const a11y = inject(BrnFieldA11yService, { optional: true });
    a11y?.registerDescription(this._id);
    inject(DestroyRef).onDestroy(() => a11y?.unregisterDescription(this._id));
  }
}
