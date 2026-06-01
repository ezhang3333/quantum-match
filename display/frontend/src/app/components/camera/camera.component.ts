import {
  AfterViewInit,
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  OnDestroy,
  ViewChild,
  inject,
  signal,
} from '@angular/core';
import { AsyncPipe } from '@angular/common';
import { firstValueFrom } from 'rxjs';
import { MatchApiService } from '../../services/match-api.service';
import { MirrorStateService } from '../../services/mirror-state.service';

const RAW_FRAMES_TO_CAPTURE = 10;
const CAMERA_SCAN_MS = 5000;
const CAPTURE_INTERVAL_MS = CAMERA_SCAN_MS / RAW_FRAMES_TO_CAPTURE;

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
          <video #feedVideo class="feed-video" [class.visible]="hasCamera()" autoplay playsinline muted></video>
          <canvas #captureCanvas class="capture-canvas"></canvas>
          @if (!hasCamera()) {
            <div class="feed-placeholder">
              <div class="crosshair"></div>
            </div>
          }
        </div>

        <div class="status-bar">
          <span class="status-dot"></span>
          <span class="status-text">{{ statusText() }}</span>
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
            @case ('camera_denied') { CAMERA ACCESS DENIED }
            @case ('camera_unavailable') { CAMERA UNAVAILABLE }
            @case ('network_error') { MATCH SERVER UNREACHABLE }
            @case ('no_face') { NO FACE DETECTED }
            @case ('multiple_faces') { MULTIPLE FACES - STAND ALONE }
            @case ('no_match') { NO MATCH FOUND - TRY AGAIN }
            @default { ERROR }
          }
        </div>
      } @else if (hasCamera() && !isCapturing()) {
        <div class="ready-panel">
          <div class="instructions">CENTER YOUR FACE IN THE FRAME</div>
          <button type="button" class="begin-button" (click)="beginMatch()">BEGIN QUANTUM MATCH</button>
        </div>
      } @else {
        <div class="instructions">ALLOW CAMERA ACCESS</div>
      }
    </div>
  `,
  styleUrl: './camera.component.less',
})
export class CameraComponent implements AfterViewInit, OnDestroy {
  private matchApi = inject(MatchApiService);
  mirrorState = inject(MirrorStateService);

  @ViewChild('feedVideo')
  private videoRef?: ElementRef<HTMLVideoElement>;

  @ViewChild('captureCanvas')
  private canvasRef?: ElementRef<HTMLCanvasElement>;

  readonly hasCamera = signal(false);
  readonly isCapturing = signal(false);
  private stream: MediaStream | null = null;
  private destroyed = false;

  ngAfterViewInit(): void {
    void this.startCameraPreview();
  }

  ngOnDestroy(): void {
    this.destroyed = true;
    this.stopCamera();
  }

  progressPercent(progress: number, total: number): number {
    if (total <= 0) return 0;
    return Math.max(0, Math.min(100, (progress / total) * 100));
  }

  statusText(): string {
    if (!this.hasCamera()) return 'SYNCING CAMERA';
    return this.isCapturing() ? 'SCANNING' : 'READY';
  }

  async beginMatch(): Promise<void> {
    if (!this.hasCamera() || this.isCapturing()) return;

    const category = this.mirrorState.selectedCategory;
    if (!category) {
      this.mirrorState.showError({ reason: 'no_match', count: 0 });
      return;
    }

    this.isCapturing.set(true);
    const frames = await this.captureFrames();
    if (this.destroyed) return;
    if (frames.length < RAW_FRAMES_TO_CAPTURE) {
      this.isCapturing.set(false);
      this.mirrorState.showError({ reason: 'camera_unavailable', count: 0 });
      return;
    }

    this.stopCamera();
    this.mirrorState.goToInference();

    try {
      const response = await firstValueFrom(this.matchApi.match(category, frames));
      if (response.error) {
        this.mirrorState.showError(response.error);
      } else if (response.matches.length > 0) {
        this.mirrorState.goToOutput(response.matches[0]);
      } else {
        this.mirrorState.showError({ reason: 'no_match', count: 0 });
      }
    } catch {
      this.mirrorState.showError({ reason: 'network_error', count: 0 });
    }
  }

  private async startCameraPreview(): Promise<void> {
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: 'user',
          width: { ideal: 1280 },
          height: { ideal: 720 },
        },
        audio: false,
      });
    } catch (error) {
      const denied = error instanceof DOMException && error.name === 'NotAllowedError';
      this.mirrorState.showError({ reason: denied ? 'camera_denied' : 'camera_unavailable', count: 0 });
      return;
    }

    const video = this.videoRef?.nativeElement;
    if (!video) {
      this.mirrorState.showError({ reason: 'camera_unavailable', count: 0 });
      return;
    }

    video.srcObject = this.stream;
    await video.play();
    this.hasCamera.set(true);
  }

  private async captureFrames(): Promise<string[]> {
    const frames: string[] = [];
    const startedAt = performance.now();

    for (let i = 0; i < RAW_FRAMES_TO_CAPTURE; i += 1) {
      if (this.destroyed) break;

      const targetTime = startedAt + i * CAPTURE_INTERVAL_MS;
      await this.sleep(Math.max(0, targetTime - performance.now()));

      const frame = await this.captureFrame();
      if (frame) {
        frames.push(frame);
      }

      this.mirrorState.updateCollecting({
        progress: Math.min(CAMERA_SCAN_MS, Math.round(performance.now() - startedAt)),
        total: CAMERA_SCAN_MS,
        captured: frames.length,
        required: RAW_FRAMES_TO_CAPTURE,
        ready: frames.length >= RAW_FRAMES_TO_CAPTURE,
      });
    }

    await this.sleep(Math.max(0, startedAt + CAMERA_SCAN_MS - performance.now()));
    this.mirrorState.updateCollecting({
      progress: CAMERA_SCAN_MS,
      total: CAMERA_SCAN_MS,
      captured: frames.length,
      required: RAW_FRAMES_TO_CAPTURE,
      ready: frames.length >= RAW_FRAMES_TO_CAPTURE,
    });

    return frames;
  }

  private captureFrame(): string | null {
    const video = this.videoRef?.nativeElement;
    const canvas = this.canvasRef?.nativeElement;
    if (!video || !canvas || video.videoWidth === 0 || video.videoHeight === 0) {
      return null;
    }

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d', { alpha: false });
    if (!ctx) return null;

    ctx.translate(canvas.width, 0);
    ctx.scale(-1, 1);
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    ctx.setTransform(1, 0, 0, 1, 0, 0);

    return canvas.toDataURL('image/jpeg', 0.86);
  }

  private sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  private stopCamera(): void {
    this.stream?.getTracks().forEach((track) => track.stop());
    this.stream = null;
    this.hasCamera.set(false);
    this.isCapturing.set(false);
  }
}
