import { Injectable, inject } from '@angular/core';
import { BehaviorSubject } from 'rxjs';
import { MirrorState, MatchResult, Category } from '../models/mirror-state.model';
import { WebSocketService, WsEvent } from './websocket.service';

export interface CollectingProgress {
  progress: number;
  total: number;
  ready?: boolean;
  captured?: number;
  required?: number;
}

export interface FaceError {
  reason: 'no_face' | 'multiple_faces' | string;
  count: number;
}

const OUTPUT_AUTO_IDLE_MS = 35000;

@Injectable({ providedIn: 'root' })
export class MirrorStateService {
  private webSocket = inject(WebSocketService);

  private stateSubject = new BehaviorSubject<MirrorState>(MirrorState.IDLE);
  private matchResultSubject = new BehaviorSubject<MatchResult | null>(null);
  private collectingSubject = new BehaviorSubject<CollectingProgress | null>(null);
  private faceErrorSubject = new BehaviorSubject<FaceError | null>(null);
  private selectedCategorySubject = new BehaviorSubject<Category | null>(null);
  private highlightedCategorySubject = new BehaviorSubject<Category | null>(null);
  private outputTimer: ReturnType<typeof setTimeout> | null = null;

  state$ = this.stateSubject.asObservable();
  matchResult$ = this.matchResultSubject.asObservable();
  collecting$ = this.collectingSubject.asObservable();
  faceError$ = this.faceErrorSubject.asObservable();
  selectedCategory$ = this.selectedCategorySubject.asObservable();
  highlightedCategory$ = this.highlightedCategorySubject.asObservable();

  get currentState(): MirrorState {
    return this.stateSubject.value;
  }

  constructor() {
    this.webSocket.events$.subscribe((event) => this.handleEvent(event));
    // Tell the backend our starting state so it knows which detector to run.
    this.webSocket.sendStateChange(this.currentState);
  }

  goToIdle(): void {
    this.clearOutputTimer();
    this.matchResultSubject.next(null);
    this.collectingSubject.next(null);
    this.faceErrorSubject.next(null);
    this.selectedCategorySubject.next(null);
    this.highlightedCategorySubject.next(null);
    this.transition(MirrorState.IDLE);
  }

  goToCategorySelect(): void {
    this.clearOutputTimer();
    this.matchResultSubject.next(null);
    this.collectingSubject.next(null);
    this.faceErrorSubject.next(null);
    this.selectedCategorySubject.next(null);
    this.highlightedCategorySubject.next(null);
    this.transition(MirrorState.CATEGORY_SELECT);
  }

  goToCamera(): void {
    this.clearOutputTimer();
    this.collectingSubject.next(null);
    this.faceErrorSubject.next(null);
    this.transition(MirrorState.CAMERA);
  }

  goToInference(): void {
    this.clearOutputTimer();
    this.collectingSubject.next(null);
    this.faceErrorSubject.next(null);
    this.transition(MirrorState.INFERENCE);
  }

  goToOutput(result: MatchResult): void {
    this.matchResultSubject.next(result);
    this.transition(MirrorState.OUTPUT);
    this.clearOutputTimer();
    this.outputTimer = setTimeout(() => this.goToIdle(), OUTPUT_AUTO_IDLE_MS);
  }

  private clearOutputTimer(): void {
    if (this.outputTimer !== null) {
      clearTimeout(this.outputTimer);
      this.outputTimer = null;
    }
  }

  private transition(next: MirrorState): void {
    this.stateSubject.next(next);
    this.webSocket.sendStateChange(next);
  }

  private handleEvent(event: WsEvent): void {
    switch (event.type) {
      case 'thumbs_up_detected':
        if (this.currentState === MirrorState.IDLE) {
          this.goToCategorySelect();
        }
        break;

      case 'category_selected':
        if (this.currentState === MirrorState.CATEGORY_SELECT) {
          const cat = String(event['category'] ?? '') as Category;
          this.selectedCategorySubject.next(cat);
          this.highlightedCategorySubject.next(cat);
          setTimeout(() => this.goToCamera(), 400);
        }
        break;

      case 'collecting':
        if (this.currentState === MirrorState.CAMERA) {
          this.faceErrorSubject.next(null);
          const collecting = {
            progress: Number(event['progress'] ?? 0),
            total: Number(event['total'] ?? 0),
            ready: Boolean(event['ready']),
            captured: Number(event['captured'] ?? 0),
            required: Number(event['required'] ?? 0),
          };
          this.collectingSubject.next(collecting);
          if (collecting.ready) {
            this.goToInference();
          }
        }
        break;

      case 'face_error':
        if (this.currentState === MirrorState.CAMERA || this.currentState === MirrorState.INFERENCE) {
          this.faceErrorSubject.next({
            reason: String(event['reason'] ?? ''),
            count: Number(event['count'] ?? 0),
          });
          this.collectingSubject.next(null);
          setTimeout(() => this.goToIdle(), 2500);
        }
        break;

      case 'match_result':
        if (this.currentState === MirrorState.CAMERA || this.currentState === MirrorState.INFERENCE) {
          const matches = event['matches'] as MatchResult[] | undefined;
          if (matches && matches.length > 0) {
            this.goToOutput(matches[0]);
          } else {
            this.collectingSubject.next(null);
            this.faceErrorSubject.next({ reason: 'no_match', count: 0 });
            setTimeout(() => this.goToIdle(), 2500);
          }
        }
        break;
    }
  }
}
