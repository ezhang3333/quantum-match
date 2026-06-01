import {
  AfterViewInit,
  ChangeDetectionStrategy,
  ChangeDetectorRef,
  Component,
  ElementRef,
  OnDestroy,
  ViewChild,
  inject,
  signal,
} from '@angular/core';
import { AsyncPipe } from '@angular/common';
import { Subscription } from 'rxjs';
import { MirrorStateService } from '../../services/mirror-state.service';
import { apiUrl } from '../../services/websocket.service';

@Component({
  selector: 'app-output',
  standalone: true,
  imports: [AsyncPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (mirrorState.matchResult$ | async; as result) {
      <div class="output-screen">
        <div class="result-container">
          <div class="top-row">
            <div class="image-panel fade-in">
              <div class="image-frame">
                <img [src]="resolveUrl(result.image_url)" [alt]="result.name" />
              </div>

              <div class="match-badge">
                <div class="match-pct">{{ (result.similarity * 100).toFixed(0) }}%</div>
                <div class="match-label">IDENTITY MATCH</div>
              </div>
            </div>

            <div class="info-panel fade-in-delay-1">
              <div class="label">MATCH DETECTED</div>
              <div class="name fade-in-delay-2">{{ result.name }}</div>
              <div class="position fade-in-delay-2">{{ result.position }}</div>
              <div class="role fade-in-delay-3">{{ result.role }}</div>

              @if (result.research_areas.length > 0) {
                <div class="research-areas fade-in-delay-3">
                  @for (area of result.research_areas.slice(0, 6); track area) {
                    <span class="chip">{{ area }}</span>
                  }
                </div>
              }
            </div>
          </div>

          @if (result.summary) {
            <div class="summary-row fade-in-delay-4">
              <div class="summary-block">
                <div class="summary-label">SUMMARY</div>
                <div #summaryBody class="summary-body">
                  <p class="summary-text">{{ displaySummary() }}</p>
                  <p #summaryMeasure class="summary-text summary-measure" aria-hidden="true"></p>
                </div>
              </div>
            </div>
          }
        </div>
      </div>
    }
  `,
  styleUrl: './output.component.less',
})
export class OutputComponent implements AfterViewInit, OnDestroy {
  mirrorState = inject(MirrorStateService);
  readonly resolveUrl = apiUrl;
  readonly displaySummary = signal('');

  @ViewChild('summaryBody')
  private summaryBodyRef?: ElementRef<HTMLDivElement>;

  @ViewChild('summaryMeasure')
  private summaryMeasureRef?: ElementRef<HTMLParagraphElement>;

  private readonly cdr = inject(ChangeDetectorRef);
  private readonly matchSub: Subscription;
  private resizeObserver?: ResizeObserver;
  private pendingFrame: number | null = null;
  private latestSummary = '';

  constructor() {
    this.matchSub = this.mirrorState.matchResult$.subscribe((result) => {
      this.latestSummary = result?.summary?.trim() ?? '';
      this.displaySummary.set(this.latestSummary);
      this.scheduleFit();
    });
  }

  ngAfterViewInit(): void {
    const summaryBody = this.summaryBodyRef?.nativeElement;
    if (summaryBody) {
      this.resizeObserver = new ResizeObserver(() => this.scheduleFit());
      this.resizeObserver.observe(summaryBody);
    }

    this.scheduleFit();
  }

  ngOnDestroy(): void {
    this.matchSub.unsubscribe();
    this.resizeObserver?.disconnect();
    if (this.pendingFrame !== null) {
      cancelAnimationFrame(this.pendingFrame);
    }
  }

  private scheduleFit(): void {
    if (this.pendingFrame !== null) {
      cancelAnimationFrame(this.pendingFrame);
    }

    this.pendingFrame = requestAnimationFrame(() => {
      this.pendingFrame = null;
      this.fitSummary();
    });
  }

  private fitSummary(): void {
    const summary = this.latestSummary;
    const summaryBody = this.summaryBodyRef?.nativeElement;
    const summaryMeasure = this.summaryMeasureRef?.nativeElement;

    if (!summaryBody || !summaryMeasure) {
      this.displaySummary.set(summary);
      return;
    }

    if (!summary) {
      this.displaySummary.set('');
      return;
    }

    const candidate = this.fitWholeSentences(summary, summaryMeasure, summaryBody.clientHeight)
      ?? this.fitWholeWords(summary, summaryMeasure, summaryBody.clientHeight);

    this.displaySummary.set(candidate || summary);
    this.cdr.markForCheck();
  }

  private fitWholeSentences(
    summary: string,
    summaryMeasure: HTMLParagraphElement,
    maxHeight: number,
  ): string | null {
    const sentences = this.splitIntoSentences(summary);
    if (sentences.length <= 1) {
      return null;
    }

    if (this.fits(summaryMeasure, summary, maxHeight)) {
      return summary;
    }

    let low = 1;
    let high = sentences.length;
    let best = '';

    while (low <= high) {
      const mid = Math.floor((low + high) / 2);
      const candidate = sentences.slice(0, mid).join(' ').trim();

      if (!candidate) {
        low = mid + 1;
        continue;
      }

      if (this.fits(summaryMeasure, candidate, maxHeight)) {
        best = candidate;
        low = mid + 1;
      } else {
        high = mid - 1;
      }
    }

    return best || null;
  }

  private fitWholeWords(
    summary: string,
    summaryMeasure: HTMLParagraphElement,
    maxHeight: number,
  ): string {
    if (this.fits(summaryMeasure, summary, maxHeight)) {
      return summary;
    }

    const words = summary.split(/\s+/).filter(Boolean);
    if (words.length === 0) {
      return summary;
    }

    let low = 1;
    let high = words.length;
    let best = words[0];

    while (low <= high) {
      const mid = Math.floor((low + high) / 2);
      const candidate = words.slice(0, mid).join(' ').trim();

      if (this.fits(summaryMeasure, candidate, maxHeight)) {
        best = candidate;
        low = mid + 1;
      } else {
        high = mid - 1;
      }
    }

    return this.backtrackToBoundary(best);
  }

  private splitIntoSentences(summary: string): string[] {
    const parts = summary
      .split(/(?<=[.!?])\s+/)
      .map((part) => part.trim())
      .filter(Boolean);

    return parts.length > 0 ? parts : [summary];
  }

  private backtrackToBoundary(candidate: string): string {
    const trimmed = candidate.trim();
    const lastPunctuation = Math.max(
      trimmed.lastIndexOf('.'),
      trimmed.lastIndexOf('!'),
      trimmed.lastIndexOf('?'),
      trimmed.lastIndexOf(';'),
      trimmed.lastIndexOf(':'),
    );

    if (lastPunctuation >= 0) {
      const bounded = trimmed.slice(0, lastPunctuation + 1).trim();
      if (bounded.length > 0) {
        return bounded;
      }
    }

    return trimmed;
  }

  private fits(
    summaryMeasure: HTMLParagraphElement,
    candidate: string,
    maxHeight: number,
  ): boolean {
    summaryMeasure.textContent = candidate;
    return summaryMeasure.scrollHeight <= maxHeight;
  }
}
