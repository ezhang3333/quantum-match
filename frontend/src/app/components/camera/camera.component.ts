import {
  Component,
  ChangeDetectionStrategy,
  inject,
  signal,
  OnDestroy,
} from '@angular/core';
import { AsyncPipe } from '@angular/common';
import { Subscription } from 'rxjs';
import { WebSocketService } from '../../services/websocket.service';
import { MirrorStateService } from '../../services/mirror-state.service';

@Component({
  selector: 'app-camera',
  standalone: true,
  imports: [AsyncPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="camera-screen">
      <div class="frame-container">
        <div class="corner top-left"></div>
        <div class="corner top-right"></div>
        <div class="corner bottom-left"></div>
        <div class="corner bottom-right"></div>

        <div class="feed-area">
          <div class="scan-line"></div>
          @if (frameUrl(); as url) {
            <img class="feed-img" [src]="url" alt="camera feed" />
          } @else {
            <div class="feed-placeholder">
              <div class="crosshair"></div>
            </div>
          }
        </div>

        <div class="status-bar">
          <span class="status-dot"></span>
          <span class="status-text">SCANNING</span>
        </div>
      </div>

      @if (mirrorState.collecting$ | async; as c) {
        <div class="progress">
          ANALYZING {{ c.progress }} / {{ c.total }}
        </div>
      } @else if (mirrorState.faceError$ | async; as err) {
        <div class="error">
          {{ err.reason === 'no_face' ? 'NO FACE DETECTED' : 'MULTIPLE FACES — STAND ALONE' }}
        </div>
      } @else {
        <div class="instructions">HOLD STILL — ANALYZING FEATURES</div>
      }
    </div>
  `,
  styleUrl: './camera.component.less',
})
export class CameraComponent implements OnDestroy {
  private webSocket = inject(WebSocketService);
  mirrorState = inject(MirrorStateService);

  readonly frameUrl = signal<string | null>(null);
  private framesSub: Subscription;
  private previousUrl: string | null = null;

  constructor() {
    this.framesSub = this.webSocket.frames$.subscribe((blob) => {
      const url = URL.createObjectURL(blob);
      const prev = this.previousUrl;
      this.previousUrl = url;
      this.frameUrl.set(url);
      if (prev) URL.revokeObjectURL(prev);
    });
  }

  ngOnDestroy(): void {
    this.framesSub.unsubscribe();
    if (this.previousUrl) {
      URL.revokeObjectURL(this.previousUrl);
      this.previousUrl = null;
    }
  }
}
