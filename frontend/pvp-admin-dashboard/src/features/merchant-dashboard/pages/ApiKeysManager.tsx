// src/features/merchant-dashboard/pages/ApiKeysManager.tsx
import React, { useState, useEffect } from 'react';

// Mocking the API service call to the FastAPI backend
const fetchApiKeys = async () => [
  { id: 1, name: 'Production Key', prefix: 'pk_prod_', isActive: true, createdAt: '2026-07-01T10:00:00Z', ipWhitelist: ['192.168.1.1'] },
  { id: 2, name: 'Test Key', prefix: 'pk_test_', isActive: true, createdAt: '2026-07-05T14:30:00Z', ipWhitelist: null }
];

export const ApiKeysManager = () => {
  const [keys, setKeys] = useState([]);
  const [isGenerating, setIsGenerating] = useState(false);

  useEffect(() => {
    fetchApiKeys().then(setKeys);
  }, []);

  const handleRotateKey = async (id: number) => {
    // In production, this calls POST /merchant/platform/api-keys/{key_id}/rotate
    alert(`Initiating rotation for Key ID: ${id}. The old key will be instantly invalidated.`);
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-bold leading-7 text-gray-900 sm:truncate sm:tracking-tight">API Credentials</h2>
          <p className="mt-1 text-sm text-gray-500">Manage your secret keys for verifying transaction receipts.</p>
        </div>
        <button 
          onClick={() => setIsGenerating(true)}
          className="inline-flex items-center rounded-md bg-indigo-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500"
        >
          Generate New Key
        </button>
      </div>

      <div className="bg-white shadow-sm ring-1 ring-gray-900/5 sm:rounded-xl">
        <table className="min-w-full divide-y divide-gray-300">
          <thead className="bg-gray-50">
            <tr>
              <th className="py-3.5 pl-4 pr-3 text-left text-sm font-semibold text-gray-900">Name</th>
              <th className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">Prefix</th>
              <th className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">Status</th>
              <th className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">IP Whitelist</th>
              <th className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {keys.map((apiKey: any) => (
              <tr key={apiKey.id}>
                <td className="whitespace-nowrap py-4 pl-4 pr-3 text-sm font-medium text-gray-900">{apiKey.name}</td>
                <td className="whitespace-nowrap px-3 py-4 text-sm text-gray-500 font-mono">{apiKey.prefix}••••••••</td>
                <td className="whitespace-nowrap px-3 py-4 text-sm">
                  <span className={`inline-flex items-center rounded-md px-2 py-1 text-xs font-medium ring-1 ring-inset ${apiKey.isActive ? 'bg-green-50 text-green-700 ring-green-600/20' : 'bg-red-50 text-red-700 ring-red-600/20'}`}>
                    {apiKey.isActive ? 'Active' : 'Inactive'}
                  </span>
                </td>
                <td className="whitespace-nowrap px-3 py-4 text-sm text-gray-500">
                  {apiKey.ipWhitelist ? apiKey.ipWhitelist.join(', ') : 'Any IP'}
                </td>
                <td className="whitespace-nowrap px-3 py-4 text-sm text-gray-500">
                  <button onClick={() => handleRotateKey(apiKey.id)} className="text-indigo-600 hover:text-indigo-900 font-medium">
                    Rotate Key
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};