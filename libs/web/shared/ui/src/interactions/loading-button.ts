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
  templateUrl: './loading-button.html',
})
export class LoadingButton {
  readonly loading = input(false);
}
