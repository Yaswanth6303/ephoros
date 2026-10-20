/*
 * Motion design ported from interior "Inline Validation" (https://github.com/ddoemonn/interior).
 * MIT License, Copyright (c) ddoemonn. See THIRD_PARTY_NOTICES.md.
 */
import {
  Component,
  effect,
  type ElementRef,
  input,
  viewChild,
} from '@angular/core';
import { animate } from 'motion';
import { motionAllowed } from './motion';

@Component({
  selector: 'eph-inline-error',
  host: { 'aria-live': 'polite', class: 'block' },
  template: `
    @if (message(); as text) {
      <p #text class="text-destructive mt-1 text-sm">{{ text }}</p>
    }
  `,
})
export class EphInlineError {
  readonly message = input<string | null>(null);
  private readonly text = viewChild<ElementRef<HTMLElement>>('text');

  constructor() {
    effect(() => {
      const el = this.text()?.nativeElement;
      if (el && motionAllowed())
        animate(el, { opacity: [0, 1], y: [-4, 0] }, { duration: 0.18 });
    });
  }
}
