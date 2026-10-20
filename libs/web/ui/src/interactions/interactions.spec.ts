import { Component, signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { EphInlineError, EphLoadingButton } from './index';

@Component({
  imports: [EphLoadingButton, EphInlineError],
  template: `
    <button ephLoadingButton [loading]="loading()">Sign in</button>
    <eph-inline-error [message]="message()" />
  `,
})
class Host {
  loading = signal(false);
  message = signal<string | null>(null);
}

describe('interactions', () => {
  const render = async () => {
    const fixture = TestBed.createComponent(Host);
    await fixture.whenStable();
    return fixture;
  };

  it('loading button is busy and disabled while loading', async () => {
    const fixture = await render();
    const button: HTMLButtonElement =
      fixture.nativeElement.querySelector('button');
    expect(button.disabled).toBe(false);
    fixture.componentInstance.loading.set(true);
    await fixture.whenStable();
    expect(button.disabled).toBe(true);
    expect(button.getAttribute('aria-busy')).toBe('true');
    expect(button.textContent).toContain('Sign in');
  });

  it('inline error announces its message and is empty without one', async () => {
    const fixture = await render();
    const region: HTMLElement =
      fixture.nativeElement.querySelector('eph-inline-error');
    expect(region.getAttribute('aria-live')).toBe('polite');
    expect(region.textContent?.trim()).toBe('');
    fixture.componentInstance.message.set('Enter a valid email');
    await fixture.whenStable();
    expect(region.textContent).toContain('Enter a valid email');
  });
});
