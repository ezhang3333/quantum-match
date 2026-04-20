import { Component, ChangeDetectionStrategy } from '@angular/core';

@Component({
  selector: 'app-idle',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<div class="idle-screen"></div>`,
  styles: [`
    .idle-screen {
      width: 100vw;
      height: 100vh;
      background: #000;
    }
  `]
})
export class IdleComponent {}
