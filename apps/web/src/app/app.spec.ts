import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { App } from './app';

describe('App', () => {
  beforeEach(() =>
    TestBed.configureTestingModule({ providers: [provideRouter([])] }),
  );

  it('renders the router outlet inside the main landmark', async () => {
    const fixture = TestBed.createComponent(App);
    await fixture.whenStable();
    const main = (fixture.nativeElement as HTMLElement).querySelector('main');
    expect(main?.querySelector('router-outlet')).toBeInstanceOf(HTMLElement);
  });
});
