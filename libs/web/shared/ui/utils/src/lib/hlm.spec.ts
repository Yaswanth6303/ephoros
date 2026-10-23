import { cn } from 'cn';
import { hlm } from './hlm';

describe('hlm', () => {
  it('is cn: later Tailwind classes win and falsy values drop', () => {
    expect(hlm).toBe(cn);
    expect(hlm('p-2 text-sm', false, 'p-4')).toBe('text-sm p-4');
  });
});
