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
  selector: 'app-startup',
  standalone: true,
  imports: [AsyncPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="startup-screen">
      <div class="scanline"></div>
      <div class="content">
        <h1 class="title fade-in">Initialize the System</h1>
        <div class="divider fade-in-delay-2"></div>

        <div class="game-frame">
          @if (frameUrl(); as url) {
            <img class="feed-img" [src]="url" alt="hand game feed" />
          } @else {
            <div class="game-placeholder">CONNECTING…</div>
          }
        </div>

        @if (mirrorState.startupProgress$ | async; as progress) {
          <div class="hud">
            ATOMS HIT {{ progress.hits }} / {{ progress.total }}
          </div>
        } @else {
          <div class="hud">PINCH TO FIRE — DESTROY THE ATOMS</div>
        }
      </div>
    </div>
  `,
  styleUrl: './startup.component.less',
})
export class StartupComponent implements OnDestroy {
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
