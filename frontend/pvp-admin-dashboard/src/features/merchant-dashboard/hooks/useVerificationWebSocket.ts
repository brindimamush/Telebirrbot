// src/features/merchant-dashboard/hooks/useVerificationWebSocket.ts
import { useState, useEffect, useRef, useCallback } from 'react';

// Define the expected payload structure from the FastAPI backend
interface VerificationEvent {
  sessionId: string;
  status: 'PENDING' | 'VERIFIED' | 'FAILED' | 'EXPIRED';
  transactionId?: string;
  amount?: number;
  timestamp: string;
}

export const useVerificationWebSocket = (merchantId: string, apiKey: string) => {
  const [events, setEvents] = useState<VerificationEvent[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const connect = useCallback(() => {
    // Replace with your actual FastAPI WebSocket URL
    const wsUrl = `wss://api.yourdomain.com/ws/merchant/${merchantId}/sessions?token=${apiKey}`;
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      setIsConnected(true);
      console.log('WebSocket connection established.');
    };

    ws.onmessage = (event) => {
      try {
        const newEvent: VerificationEvent = JSON.parse(event.data);
        setEvents((prev) => [newEvent, ...prev]);
      } catch (error) {
        console.error('Failed to parse WebSocket message:', error);
      }
    };

    ws.onclose = () => {
      setIsConnected(false);
      console.log('WebSocket disconnected. Attempting to reconnect...');
      // Implement simple exponential backoff or fixed delay for reconnection
      reconnectTimeoutRef.current = setTimeout(connect, 5000);
    };

    ws.onerror = (error) => {
      console.error('WebSocket encountered an error:', error);
      ws.close(); // Trigger onclose to handle reconnection
    };

    wsRef.current = ws;
  }, [merchantId, apiKey]);

  useEffect(() => {
    connect();

    return () => {
      // Cleanup on unmount
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      if (wsRef.current) {
        wsRef.current.onclose = null; // Prevent reconnection loop on intended unmount
        wsRef.current.close();
      }
    };
  }, [connect]);

  return { events, isConnected };
};