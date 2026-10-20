import { provideHttpClient } from '@angular/common/http';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { client, provideHeyApiClient } from '@ephoros/api-contract';
import { Status } from './status';

describe('Status', () => {
  beforeEach(() =>
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideHeyApiClient(client),
      ],
    }),
  );

  // zoneless: the resource fires its request asynchronously, so poll for it
  const pending = () =>
    vi.waitFor(() =>
      TestBed.inject(HttpTestingController).expectOne('/api/v1/healthz'),
    );

  it('shows ok when the API is healthy', async () => {
    const fixture = TestBed.createComponent(Status);
    (await pending()).flush({ status: 'ok' });
    await fixture.whenStable();
    expect(fixture.nativeElement.textContent).toContain('API: ok');
  });

  it('shows unreachable when the API fails', async () => {
    const fixture = TestBed.createComponent(Status);
    (await pending()).flush('bad gateway', {
      status: 502,
      statusText: 'Bad Gateway',
    });
    await fixture.whenStable();
    expect(fixture.nativeElement.textContent).toContain('API: unreachable');
  });
});
