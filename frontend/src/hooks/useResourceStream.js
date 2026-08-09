import { Client } from '@stomp/stompjs';
import { useEffect, useRef, useState } from 'react';
import SockJS from 'sockjs-client/dist/sockjs';
import { SERVER_ORIGIN } from '../api/client';

/**
 * Subscribes to live resource updates over STOMP/SockJS.
 *
 * If the socket cannot connect, the caller falls back to polling. That matters
 * for a demo: a blocked WebSocket should degrade to slightly-slower updates,
 * not a frozen page showing stale emergency data.
 *
 * @param onUpdate called with the ResourceView from each broadcast
 * @returns {{connected: boolean}}
 */
export default function useResourceStream(onUpdate) {
  const [connected, setConnected] = useState(false);
  const handlerRef = useRef(onUpdate);

  // Keep the latest callback without forcing a reconnect on every render.
  useEffect(() => {
    handlerRef.current = onUpdate;
  }, [onUpdate]);

  useEffect(() => {
    let client;
    try {
      client = new Client({
        webSocketFactory: () => new SockJS(`${SERVER_ORIGIN}/ws`),
        reconnectDelay: 5000,
        heartbeatIncoming: 10000,
        heartbeatOutgoing: 10000,
        debug: () => {},
        onConnect: () => {
          setConnected(true);
          client.subscribe('/topic/resources', (frame) => {
            try {
              const event = JSON.parse(frame.body);
              if (event?.resource && handlerRef.current) {
                handlerRef.current(event.resource);
              }
            } catch {
              /* ignore malformed frame */
            }
          });
        },
        onDisconnect: () => setConnected(false),
        onWebSocketClose: () => setConnected(false),
        onStompError: () => setConnected(false),
      });
      client.activate();
    } catch {
      setConnected(false);
    }

    return () => {
      try {
        client?.deactivate();
      } catch {
        /* already closed */
      }
    };
  }, []);

  return { connected };
}
