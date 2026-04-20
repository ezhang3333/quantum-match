import { Injectable, OnDestroy } from '@angular/core';
import { Subject, BehaviorSubject } from 'rxjs';

export interface WsEvent {
  type: string;
  [key: string]: unknown;
}

@Injectable({ providedIn: 'root' })
export class WebSocketService implements OnDestroy {
  private socket: WebSocket | null = null;
  private reconnectDelayMs = 500;
  private readonly maxReconnectDelayMs = 5000;
  private destroyed = false;
  private pendingStateOnConnect: string | null = null;

  readonly frames$ = new Subject<Blob>();
  readonly events$ = new Subject<WsEvent>();
  readonly connected$ = new BehaviorSubject<boolean>(false);

  constructor() {
    this.connect();
  }

  ngOnDestroy(): void {
    this.destroyed = true;
    this.socket?.close();
  }

  sendStateChange(state: string): void {
    const payload = JSON.stringify({ type: 'state_change', state });
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(payload);
    } else {
      this.pendingStateOnConnect = state;
    }
  }

  private connect(): void {
    if (this.destroyed) return;

    const url = this.buildUrl();
    const ws = new WebSocket(url);
    ws.binaryType = 'blob';
    this.socket = ws;

    ws.addEventListener('open', () => {
      this.connected$.next(true);
      this.reconnectDelayMs = 500;
      if (this.pendingStateOnConnect) {
        ws.send(JSON.stringify({ type: 'state_change', state: this.pendingStateOnConnect }));
        this.pendingStateOnConnect = null;
      }
    });

    ws.addEventListener('message', (event) => {
      const data = event.data;
      if (data instanceof Blob) {
        this.frames$.next(data);
        return;
      }
      if (typeof data === 'string') {
        try {
          const parsed = JSON.parse(data) as WsEvent;
          this.events$.next(parsed);
        } catch {
          // ignore non-JSON text frames
        }
      }
    });

    ws.addEventListener('close', () => {
      this.connected$.next(false);
      this.socket = null;
      if (this.destroyed) return;
      const delay = this.reconnectDelayMs;
      this.reconnectDelayMs = Math.min(this.reconnectDelayMs * 2, this.maxReconnectDelayMs);
      setTimeout(() => this.connect(), delay);
    });

    ws.addEventListener('error', () => {
      ws.close();
    });
  }

  private buildUrl(): string {
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
    return `${proto}://${apiHost()}/ws/camera`;
  }
}

/** Resolve a backend-relative URL (e.g. "/images/Foo.jpg") to an absolute URL.
 * In dev, the page is on :4200 but FastAPI serves images on :8000, so we
 * always prefix with the API host. */
export function apiUrl(path: string): string {
  if (/^https?:\/\//i.test(path)) return path;
  const proto = window.location.protocol === 'https:' ? 'https' : 'http';
  const normalized = path.startsWith('/') ? path : `/${path}`;
  return `${proto}://${apiHost()}${normalized}`;
}

function apiHost(): string {
  // Angular dev server runs on :4200, but the FastAPI server lives on :8000.
  return window.location.host === 'localhost:4200' || window.location.host === '127.0.0.1:4200'
    ? 'localhost:8000'
    : window.location.host;
}
