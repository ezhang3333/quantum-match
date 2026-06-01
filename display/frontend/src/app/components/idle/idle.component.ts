import { Component, ChangeDetectionStrategy, inject } from '@angular/core';
import { MirrorStateService } from '../../services/mirror-state.service';

@Component({
  selector: 'app-idle',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <button type="button" class="idle-screen" (click)="start()" aria-label="Start Quantum Match">
      <span class="idle-core"></span>
      <span class="idle-label">START QUANTUM MATCH</span>
    </button>
  `,
  styles: [`
    .idle-screen {
      appearance: none;
      width: 100vw;
      height: 100vh;
      border: 0;
      background:
        radial-gradient(circle at 50% 50%, rgba(0, 240, 255, 0.16), transparent 38%),
        #000;
      color: #fff;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 2rem;
      cursor: pointer;
      font-family: 'Orbitron', sans-serif;
    }

    .idle-core {
      width: min(34vw, 260px);
      aspect-ratio: 1;
      border: 2px solid rgba(0, 240, 255, 0.36);
      box-shadow:
        0 0 42px rgba(0, 240, 255, 0.18),
        inset 0 0 42px rgba(0, 240, 255, 0.12);
      animation: idle-pulse 2.2s ease-in-out infinite;
    }

    .idle-label {
      font-size: clamp(0.8rem, 2vw, 1rem);
      letter-spacing: 0.32em;
      color: rgba(255, 255, 255, 0.78);
    }

    .idle-screen:focus-visible {
      outline: 3px solid #00f0ff;
      outline-offset: -12px;
    }

    @keyframes idle-pulse {
      0%, 100% {
        opacity: 0.72;
        transform: scale(0.98);
      }
      50% {
        opacity: 1;
        transform: scale(1.02);
      }
    }
  `]
})
export class IdleComponent {
  private mirrorState = inject(MirrorStateService);

  start(): void {
    this.mirrorState.goToCategorySelect();
  }
}
