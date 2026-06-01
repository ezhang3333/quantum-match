export enum MirrorState {
  IDLE = 'idle',
  CATEGORY_SELECT = 'category_select',
  CAMERA = 'camera',
  INFERENCE = 'inference',
  OUTPUT = 'output'
}

export type Category = 'scientist' | 'engineer' | 'entrepreneur';

export interface MatchResult {
  name: string;
  similarity: number;
  role: string;
  position: string;
  research_areas: string[];
  image_url: string;
  profile_url: string;
  summary: string;
  category: string;
}
