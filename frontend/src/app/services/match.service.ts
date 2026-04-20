import { Injectable } from '@angular/core';
import { Observable, of } from 'rxjs';
import { MatchResult } from '../models/mirror-state.model';

@Injectable({ providedIn: 'root' })
export class MatchService {
  // Stubbed with mock data - will be replaced with HTTP calls to FastAPI backend
  getTopMatch(): Observable<MatchResult> {
    return of({
      name: 'Marcela Carena',
      similarity: 0.87,
      role: 'Research Faculty Office of Executive Leadership',
      position: 'Executive Director',
      research_areas: ['Particle Physics'],
      image_url: '/images/Marcela Carena.jpg',
      profile_url: 'https://perimeterinstitute.ca/people/marcela-carena'
    });
  }

  getImageUrl(name: string): string {
    return `/images/${name}.jpg`;
  }
}
