// src/features/merchant-dashboard/pages/VerificationSessions.tsx
import React from 'react';
import { useVerificationWebSocket } from '../hooks/useVerificationWebSocket';

export const VerificationSessions = () => {
  // In a real app, these values would come from an Auth context or state management store
  const merchantId = 'merch_01H8X...'; 
  const apiKey = 'pk_prod_...';

  const { events, isConnected } = useVerificationWebSocket(merchantId, apiKey);

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-bold leading-7 text-gray-900 sm:truncate sm:tracking-tight">
            Live Verification Sessions
          </h2>
          <p className="mt-1 text-sm text-gray-500">
            Real-time feed of your customers' payment verifications.
          </p>
        </div>
        <div className="flex items-center">
          <span className="relative flex h-3 w-3 mr-2">
            {isConnected && (
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
            )}
            <span className={`relative inline-flex rounded-full h-3 w-3 ${isConnected ? 'bg-green-500' : 'bg-red-500'}`}></span>
          </span>
          <span className="text-sm font-medium text-gray-700">
            {isConnected ? 'Connected' : 'Disconnected'}
          </span>
        </div>
      </div>

      <div className="bg-white shadow-sm ring-1 ring-gray-900/5 sm:rounded-xl overflow-hidden">
        {events.length === 0 ? (
          <div className="text-center py-12 text-gray-500">
            Waiting for incoming verification sessions...
          </div>
        ) : (
          <table className="min-w-full divide-y divide-gray-300">
            <thead className="bg-gray-50">
              <tr>
                <th className="py-3.5 pl-4 pr-3 text-left text-sm font-semibold text-gray-900">Session ID</th>
                <th className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">Status</th>
                <th className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">Amount (ETB)</th>
                <th className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">Timestamp</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {events.map((event, index) => (
                <tr key={`${event.sessionId}-${index}`} className="transition-colors duration-300 hover:bg-gray-50">
                  <td className="whitespace-nowrap py-4 pl-4 pr-3 text-sm font-medium text-gray-900 font-mono">
                    {event.sessionId.substring(0, 8)}...
                  </td>
                  <td className="whitespace-nowrap px-3 py-4 text-sm">
                    <span className={`inline-flex items-center rounded-md px-2 py-1 text-xs font-medium ring-1 ring-inset ${
                      event.status === 'VERIFIED' ? 'bg-green-50 text-green-700 ring-green-600/20' :
                      event.status === 'PENDING' ? 'bg-yellow-50 text-yellow-700 ring-yellow-600/20' :
                      'bg-red-50 text-red-700 ring-red-600/20'
                    }`}>
                      {event.status}
                    </span>
                  </td>
                  <td className="whitespace-nowrap px-3 py-4 text-sm text-gray-500">
                    {event.amount ? event.amount.toFixed(2) : '--'}
                  </td>
                  <td className="whitespace-nowrap px-3 py-4 text-sm text-gray-500">
                    {new Date(event.timestamp).toLocaleTimeString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};