import {
  AfterViewInit,
  Component,
  ChangeDetectionStrategy,
  ElementRef,
  inject,
  signal,
  OnDestroy,
  ViewChild,
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
          <canvas #feedCanvas class="feed-canvas" [class.visible]="hasFrame()"></canvas>
          @if (!hasFrame()) {
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
        <div class="progress-panel">
          <div class="progress-header">
            <span class="progress-label">FACE MATRIX</span>
            <span class="progress-value">{{ progressPercent(c.progress, c.total).toFixed(0) }}%</span>
          </div>
          <div class="progress-rail">
            <div class="progress-fill" [style.width.%]="progressPercent(c.progress, c.total)"></div>
          </div>
          <div class="progress-caption">COLLECTING FACIAL SIGNATURE</div>
        </div>
      } @else if (mirrorState.faceError$ | async; as err) {
        <div class="error">
          @switch (err.reason) {
            @case ('no_face') { NO FACE DETECTED }
            @case ('multiple_faces') { MULTIPLE FACES — STAND ALONE }
            @case ('no_match') { NO MATCH FOUND — TRY AGAIN }
            @default { ERROR }
          }
        </div>
      } @else {
        <div class="instructions">HOLD STILL — ANALYZING FEATURES</div>
      }
    </div>
  `,
  styleUrl: './camera.component.less',
})
export class CameraComponent implements AfterViewInit, OnDestroy {
  private webSocket = inject(WebSocketService);
  mirrorState = inject(MirrorStateService);

  @ViewChild('feedCanvas')
  private canvasRef?: ElementRef<HTMLCanvasElement>;

  readonly hasFrame = signal(false);
  private framesSub: Subscription;
  private canvasContext: CanvasRenderingContext2D | null = null;
  private pendingBlob: Blob | null = null;
  private decodeInFlight = false;
  private destroyed = false;

  constructor() {
    this.framesSub = this.webSocket.frames$.subscribe((blob) => {
      if (!blob) return;
      this.pendingBlob = blob;
      if (!this.decodeInFlight) {
        void this.flushLatestFrame();
      }
    });
  }

  ngAfterViewInit(): void {
    const canvas = this.canvasRef?.nativeElement;
    if (!canvas) return;

    this.canvasContext = canvas.getContext('2d', {
      alpha: false,
      desynchronized: true,
    });

    if (this.pendingBlob && !this.decodeInFlight) {
      void this.flushLatestFrame();
    }
  }

  ngOnDestroy(): void {
    this.destroyed = true;
    this.framesSub.unsubscribe();
  }

  progressPercent(progress: number, total: number): number {
    if (total <= 0) return 0;
    return Math.max(0, Math.min(100, (progress / total) * 100));
  }

  private async flushLatestFrame(): Promise<void> {
    if (this.decodeInFlight || !this.pendingBlob) return;

    const blob = this.pendingBlob;
    this.pendingBlob = null;
    this.decodeInFlight = true;

    try {
      const bitmap = await createImageBitmap(blob);
      try {
        if (!this.destroyed) {
          this.drawBitmap(bitmap);
          this.hasFrame.set(true);
        }
      } finally {
        bitmap.close();
      }
    } catch {
      // Ignore corrupt or incomplete frames and keep streaming.
    } finally {
      this.decodeInFlight = false;
      if (this.pendingBlob && !this.destroyed) {
        void this.flushLatestFrame();
      }
    }
  }

  private drawBitmap(bitmap: ImageBitmap): void {
    const canvas = this.canvasRef?.nativeElement;
    const ctx = this.canvasContext;
    if (!canvas || !ctx) return;

    if (canvas.width !== bitmap.width || canvas.height !== bitmap.height) {
      canvas.width = bitmap.width;
      canvas.height = bitmap.height;
    }

    ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  }
}
