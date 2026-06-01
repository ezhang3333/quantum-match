import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { Category, MatchResult } from '../models/mirror-state.model';
import { apiUrl } from './api-config';
import { FaceError } from './mirror-state.service';

export interface MatchResponse {
  matches: MatchResult[];
  error: FaceError | null;
}

@Injectable({ providedIn: 'root' })
export class MatchApiService {
  private http = inject(HttpClient);

  match(category: Category, frames: string[]): Observable<MatchResponse> {
    return this.http.post<MatchResponse>(apiUrl('/api/match'), { category, frames });
  }
}
