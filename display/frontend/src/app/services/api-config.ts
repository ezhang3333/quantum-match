type ApiWindow = Window & {
  __QM_API_BASE_URL__?: string;
};

export function apiBaseUrl(): string {
  const configured = (window as ApiWindow).__QM_API_BASE_URL__?.trim();
  if (configured) {
    return configured.replace(/\/$/, '');
  }

  if (window.location.host === 'localhost:4200' || window.location.host === '127.0.0.1:4200') {
    return `${window.location.protocol}//localhost:8000`;
  }

  return window.location.origin;
}

export function apiUrl(path: string): string {
  if (/^https?:\/\//i.test(path)) return path;
  const normalized = path.startsWith('/') ? path : `/${path}`;
  return `${apiBaseUrl()}${normalized}`;
}
