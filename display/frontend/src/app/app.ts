import { Component, inject, ChangeDetectionStrategy } from '@angular/core';
import { AsyncPipe } from '@angular/common';
import { MirrorStateService } from './services/mirror-state.service';
import { MirrorState } from './models/mirror-state.model';
import { IdleComponent } from './components/idle/idle.component';
import { CategorySelectComponent } from './components/category-select/category-select.component';
import { CameraComponent } from './components/camera/camera.component';
import { InferenceComponent } from './components/inference/inference.component';
import { OutputComponent } from './components/output/output.component';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [AsyncPipe, IdleComponent, CategorySelectComponent, CameraComponent, InferenceComponent, OutputComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './app.html',
  styleUrl: './app.less'
})
export class App {
  mirrorState = inject(MirrorStateService);
  MirrorState = MirrorState;
}
