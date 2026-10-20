/*
 * Motion design ported from interior "Loading Button" (https://github.com/ddoemonn/interior).
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
  // eslint-disable-next-line @angular-eslint/component-selector -- enhances the native <button>, like hlmBtn
  selector: 'button[ephLoadingButton]',
  host: {
    '[disabled]': 'loading() || disabled()',
    '[attr.aria-busy]': 'loading()',
  },
  template: `
    <span class="inline-flex items-center gap-2">
      @if (loading()) {
        <svg
          #spinner
          class="size-4 animate-spin"
          viewBox="0 0 24 24"
          fill="none"
          aria-hidden="true"
        >
          <circle
            cx="12"
            cy="12"
            r="9"
            stroke="currentColor"
            stroke-opacity="0.25"
            stroke-width="3"
          />
          <path
            d="M21 12a9 9 0 0 0-9-9"
            stroke="currentColor"
            stroke-width="3"
            stroke-linecap="round"
          />
        </svg>
      }
      <ng-content />
    </span>
  `,
})
export class EphLoadingButton {
  readonly loading = input(false);
  readonly disabled = input(false);
  private readonly spinner = viewChild<ElementRef<SVGElement>>('spinner');

  constructor() {
    effect(() => {
      const el = this.spinner()?.nativeElement;
      if (el && motionAllowed())
        animate(el, { opacity: [0, 1], scale: [0.6, 1] }, { duration: 0.18 });
    });
  }
}
