import { Injectable } from '@angular/core';
import { BehaviorSubject } from 'rxjs';
import { Category, MatchResult, MirrorState } from '../models/mirror-state.model';

export interface CollectingProgress {
  progress: number;
  total: number;
  ready?: boolean;
  captured?: number;
  required?: number;
}

export interface FaceError {
  reason: 'no_face' | 'multiple_faces' | 'no_match' | 'camera_denied' | 'camera_unavailable' | 'network_error' | string;
  count: number;
}

@Injectable({ providedIn: 'root' })
export class MirrorStateService {
  private stateSubject = new BehaviorSubject<MirrorState>(MirrorState.IDLE);
  private matchResultSubject = new BehaviorSubject<MatchResult | null>(null);
  private collectingSubject = new BehaviorSubject<CollectingProgress | null>(null);
  private faceErrorSubject = new BehaviorSubject<FaceError | null>(null);
  private selectedCategorySubject = new BehaviorSubject<Category | null>(null);
  private highlightedCategorySubject = new BehaviorSubject<Category | null>(null);

  state$ = this.stateSubject.asObservable();
  matchResult$ = this.matchResultSubject.asObservable();
  collecting$ = this.collectingSubject.asObservable();
  faceError$ = this.faceErrorSubject.asObservable();
  selectedCategory$ = this.selectedCategorySubject.asObservable();
  highlightedCategory$ = this.highlightedCategorySubject.asObservable();

  get currentState(): MirrorState {
    return this.stateSubject.value;
  }

  get selectedCategory(): Category | null {
    return this.selectedCategorySubject.value;
  }

  goToIdle(): void {
    this.matchResultSubject.next(null);
    this.collectingSubject.next(null);
    this.faceErrorSubject.next(null);
    this.selectedCategorySubject.next(null);
    this.highlightedCategorySubject.next(null);
    this.transition(MirrorState.IDLE);
  }

  goToCategorySelect(): void {
    this.matchResultSubject.next(null);
    this.collectingSubject.next(null);
    this.faceErrorSubject.next(null);
    this.selectedCategorySubject.next(null);
    this.highlightedCategorySubject.next(null);
    this.transition(MirrorState.CATEGORY_SELECT);
  }

  selectCategory(category: Category): void {
    if (this.currentState !== MirrorState.CATEGORY_SELECT) return;
    this.selectedCategorySubject.next(category);
    this.highlightedCategorySubject.next(category);
    setTimeout(() => this.goToCamera(), 400);
  }

  goToCamera(): void {
    this.collectingSubject.next(null);
    this.faceErrorSubject.next(null);
    this.transition(MirrorState.CAMERA);
  }

  goToInference(): void {
    this.collectingSubject.next(null);
    this.faceErrorSubject.next(null);
    this.transition(MirrorState.INFERENCE);
  }

  updateCollecting(progress: CollectingProgress): void {
    if (this.currentState === MirrorState.CAMERA) {
      this.faceErrorSubject.next(null);
      this.collectingSubject.next(progress);
    }
  }

  showError(error: FaceError): void {
    this.faceErrorSubject.next(error);
    this.collectingSubject.next(null);
    setTimeout(() => this.goToIdle(), 2500);
  }

  goToOutput(result: MatchResult): void {
    this.matchResultSubject.next(result);
    this.transition(MirrorState.OUTPUT);
  }

  private transition(next: MirrorState): void {
    this.stateSubject.next(next);
  }
}
