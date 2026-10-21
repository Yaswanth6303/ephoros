/*
 * Motion design ported from interior "Loading Button" (https://github.com/ddoemonn/interior).
 * MIT License, Copyright (c) ddoemonn. See THIRD_PARTY_NOTICES.md.
 */
import { Component, input } from '@angular/core';

@Component({
  // eslint-disable-next-line @angular-eslint/component-selector -- enhances the native <button>, like hlmBtn
  selector: 'button[ephLoadingButton]',
  host: {
    '[disabled]': 'loading()',
    '[attr.aria-busy]': 'loading()',
  },
  template: `
    <span class="inline-flex items-center gap-2">
      @if (loading()) {
        <svg
          animate.enter="motion-safe:animate-in motion-safe:fade-in motion-safe:zoom-in-50 duration-200"
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
export class LoadingButton {
  readonly loading = input(false);
}
