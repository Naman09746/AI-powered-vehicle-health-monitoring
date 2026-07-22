"use client";

import { useCallback, useEffect, useRef, useState } from "react";

interface SSEOptions {
  onMessage?: (data: unknown) => void;
  onError?: (err: Event) => void;
  onOpen?: () => void;
  autoConnect?: boolean;
  maxRetries?: number;
  retryDelay?: number;
}

interface SSEState {
  status: "disconnected" | "connecting" | "connected" | "error";
  lastEvent: unknown | null;
  error: Event | null;
}

const DEFAULT_RETRY_DELAY = 3000;
const MAX_RETRIES = 10;

/**
 * Hook for Server-Sent Events (SSE) with auto-reconnect and backoff.
 *
 * Usage:
 *   const { status, lastEvent } = useSSE("/api/v1/dashboard/1/stream");
 */
export function useSSE<T = unknown>(url: string | null, options: SSEOptions = {}) {
  const {
    onMessage,
    onError,
    onOpen,
    autoConnect = true,
    maxRetries = MAX_RETRIES,
    retryDelay = DEFAULT_RETRY_DELAY,
  } = options;

  const [state, setState] = useState<SSEState>({
    status: "disconnected",
    lastEvent: null,
    error: null,
  });

  const eventSourceRef = useRef<EventSource | null>(null);
  const retryCountRef = useRef(0);
  const retryTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onMessageRef = useRef(onMessage);
  const onErrorRef = useRef(onError);
  const onOpenRef = useRef(onOpen);

  // Keep callback refs current without re-triggering effect
  onMessageRef.current = onMessage;
  onErrorRef.current = onError;
  onOpenRef.current = onOpen;

  const connect = useCallback(() => {
    if (!url) return;

    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    setState((prev) => ({ ...prev, status: "connecting" }));

    const es = new EventSource(url);
    eventSourceRef.current = es;

    es.onopen = () => {
      retryCountRef.current = 0;
      setState((prev) => ({ ...prev, status: "connected", error: null }));
      onOpenRef.current?.();
    };

    es.onmessage = (event) => {
      let data: T | null = null;
      try {
        data = JSON.parse(event.data) as T;
      } catch {
        data = event.data as unknown as T;
      }
      setState((prev) => ({ ...prev, lastEvent: data }));
      onMessageRef.current?.(data);
    };

    es.onerror = (event) => {
      es.close();
      setState((prev) => ({ ...prev, status: "error", error: event }));
      onErrorRef.current?.(event);

      if (retryCountRef.current < maxRetries) {
        retryCountRef.current++;
        const delay = Math.min(retryDelay * Math.pow(2, retryCountRef.current - 1), 30_000);
        retryTimeoutRef.current = setTimeout(connect, delay);
      } else {
        setState((prev) => ({ ...prev, status: "disconnected" }));
      }
    };
  }, [url, maxRetries, retryDelay]);

  const disconnect = useCallback(() => {
    if (retryTimeoutRef.current) {
      clearTimeout(retryTimeoutRef.current);
      retryTimeoutRef.current = null;
    }
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    setState((prev) => ({ ...prev, status: "disconnected" }));
  }, []);

  useEffect(() => {
    if (autoConnect && url) {
      connect();
    }
    return disconnect;
  }, [url, autoConnect, connect, disconnect]);

  return {
    ...state,
    connect,
    disconnect,
  };
}
