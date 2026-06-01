import { Component, ChangeDetectionStrategy, inject } from '@angular/core';
import { AsyncPipe } from '@angular/common';
import { MirrorStateService } from '../../services/mirror-state.service';

@Component({
  selector: 'app-inference',
  standalone: true,
  imports: [AsyncPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="inference-screen">
      <div class="grid-overlay"></div>
      <div class="analysis-shell">
        <div class="label fade-in">QUANTUM INFERENCE</div>

        @if (mirrorState.faceError$ | async; as err) {
          <div class="error-block fade-in-delay-1">
            @switch (err.reason) {
              @case ('no_face') { SIGNAL LOST }
              @case ('multiple_faces') { INTERFERENCE DETECTED }
              @case ('no_match') { NO STABLE COLLAPSE }
              @default { MODEL ERROR }
            }
          </div>
        } @else {
          <div class="core-frame fade-in-delay-1">
            <div class="ring ring-outer"></div>
            <div class="ring ring-mid"></div>
            <div class="ring ring-inner"></div>
            <div class="orbit orbit-a"></div>
            <div class="orbit orbit-b"></div>
            <div class="core-pulse"></div>
            <div class="node node-a"></div>
            <div class="node node-b"></div>
            <div class="node node-c"></div>
            <div class="scan-column"></div>
          </div>

          <h1 class="headline fade-in-delay-2">ANALYZING FACE VECTOR</h1>
          <div class="subhead fade-in-delay-3">COLLAPSING MATCH SPACE ACROSS KNOWN IDENTITIES</div>

          <div class="activity-row fade-in-delay-4" aria-hidden="true">
            <span></span>
            <span></span>
            <span></span>
            <span></span>
            <span></span>
          </div>
        }
      </div>
    </div>
  `,
  styleUrl: './inference.component.less',
})
export class InferenceComponent {
  mirrorState = inject(MirrorStateService);
}
