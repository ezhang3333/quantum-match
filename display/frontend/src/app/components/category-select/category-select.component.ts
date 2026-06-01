import { Component, ChangeDetectionStrategy, inject } from '@angular/core';
import { AsyncPipe } from '@angular/common';
import { MirrorStateService } from '../../services/mirror-state.service';

@Component({
  selector: 'app-category-select',
  standalone: true,
  imports: [AsyncPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './category-select.component.html',
  styleUrl: './category-select.component.less'
})
export class CategorySelectComponent {
  mirrorState = inject(MirrorStateService);
  highlighted$ = this.mirrorState.highlightedCategory$;
}
