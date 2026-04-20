import { Injectable, inject } from '@angular/core';
import { BehaviorSubject } from 'rxjs';
import { MirrorState, MatchResult } from '../models/mirror-state.model';
import { WebSocketService, WsEvent } from './websocket.service';

export interface StartupProgress {
  hits: number;
  total: number;
  trigger_down: boolean;
  system_ready: boolean;
}

export interface CollectingProgress {
  progress: number;
  total: number;
}

export interface FaceError {
  reason: 'no_face' | 'multiple_faces' | string;
  count: number;
}

@Injectable({ providedIn: 'root' })
export class MirrorStateService {
  private webSocket = inject(WebSocketService);

  private stateSubject = new BehaviorSubject<MirrorState>(MirrorState.IDLE);
  private matchResultSubject = new BehaviorSubject<MatchResult | null>(null);
  private startupProgressSubject = new BehaviorSubject<StartupProgress | null>(null);
  private collectingSubject = new BehaviorSubject<CollectingProgress | null>(null);
  private faceErrorSubject = new BehaviorSubject<FaceError | null>(null);

  state$ = this.stateSubject.asObservable();
  matchResult$ = this.matchResultSubject.asObservable();
  startupProgress$ = this.startupProgressSubject.asObservable();
  collecting$ = this.collectingSubject.asObservable();
  faceError$ = this.faceErrorSubject.asObservable();

  get currentState(): MirrorState {
    return this.stateSubject.value;
  }

  constructor() {
    this.webSocket.events$.subscribe((event) => this.handleEvent(event));
    // Tell the backend our starting state so it knows which detector to run.
    this.webSocket.sendStateChange(this.currentState);
  }

  goToIdle(): void {
    this.matchResultSubject.next(null);
    this.startupProgressSubject.next(null);
    this.collectingSubject.next(null);
    this.faceErrorSubject.next(null);
    this.transition(MirrorState.IDLE);
  }

  goToStartup(): void {
    this.startupProgressSubject.next(null);
    this.transition(MirrorState.STARTUP);
  }

  goToCamera(): void {
    this.collectingSubject.next(null);
    this.faceErrorSubject.next(null);
    this.transition(MirrorState.CAMERA);
  }

  goToOutput(result: MatchResult): void {
    this.matchResultSubject.next(result);
    this.transition(MirrorState.OUTPUT);
  }

  private transition(next: MirrorState): void {
    this.stateSubject.next(next);
    this.webSocket.sendStateChange(next);
  }

  private handleEvent(event: WsEvent): void {
    switch (event.type) {
      case 'thumbs_up_detected':
        if (this.currentState === MirrorState.IDLE) {
          this.goToStartup();
        }
        break;

      case 'startup_progress':
        if (this.currentState === MirrorState.STARTUP) {
          this.startupProgressSubject.next({
            hits: Number(event['hits'] ?? 0),
            total: Number(event['total'] ?? 0),
            trigger_down: Boolean(event['trigger_down']),
            system_ready: Boolean(event['system_ready']),
          });
        }
        break;

      case 'startup_complete':
        if (this.currentState === MirrorState.STARTUP) {
          this.goToCamera();
        }
        break;

      case 'collecting':
        if (this.currentState === MirrorState.CAMERA) {
          this.faceErrorSubject.next(null);
          this.collectingSubject.next({
            progress: Number(event['progress'] ?? 0),
            total: Number(event['total'] ?? 0),
          });
        }
        break;

      case 'face_error':
        if (this.currentState === MirrorState.CAMERA) {
          this.faceErrorSubject.next({
            reason: String(event['reason'] ?? ''),
            count: Number(event['count'] ?? 0),
          });
        }
        break;

      case 'match_result':
        if (this.currentState === MirrorState.CAMERA) {
          const matches = event['matches'] as MatchResult[] | undefined;
          if (matches && matches.length > 0) {
            this.goToOutput(matches[0]);
          }
        }
        break;
    }
  }
}
