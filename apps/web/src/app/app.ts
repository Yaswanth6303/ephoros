import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';

@Component({
  selector: 'eph-root',
  imports: [RouterOutlet],
  template: `<main class="p-6"><router-outlet /></main>`,
})
export class App {}
