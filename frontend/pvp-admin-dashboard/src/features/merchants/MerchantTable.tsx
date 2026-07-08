import React, { useState } from 'react';
import { useQuery, keepPreviousData } from '@tanstack/react-query';
import { getMerchants } from '../../services/merchantService';
import { Activity, Key } from 'lucide-react';

export const MerchantTable = () => {
  const [page, setPage] = useState(1);
  const limit = 20;

  const { data, isLoading, isError } = useQuery({
    queryKey: ['merchants', page],
    queryFn: () => getMerchants(page, limit),
    placeholderData: keepPreviousData, // Keeps UI stable during pagination
  });

  if (isLoading) return <div className="p-8 text-gray-500">Loading merchants...</div>;
  if (isError) return <div className="p-8 text-red-500">Failed to load merchants.</div>;

  return (
    <div className="bg-white rounded-lg shadow border border-gray-200">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">ID / Name</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Phone</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
            <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Actions</th>
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-200">
          {data?.data.map((merchant) => (
            <tr key={merchant.id} className="hover:bg-gray-50">
              <td className="px-6 py-4 whitespace-nowrap">
                <div className="text-sm font-medium text-gray-900">{merchant.name}</div>
                <div className="text-sm text-gray-500">#{merchant.id}</div>
              </td>
              <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                {merchant.payment_phone}
              </td>
              <td className="px-6 py-4 whitespace-nowrap">
                <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${merchant.is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                  {merchant.is_active ? 'Active' : 'Suspended'}
                </span>
              </td>
              <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                <button className="text-blue-600 hover:text-blue-900 mx-2" title="Rotate API Key">
                  <Key size={16} />
                </button>
                <button className="text-gray-600 hover:text-gray-900 mx-2" title="View Activity">
                  <Activity size={16} />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {/* Pagination Controls Here */}
    </div>
  );
};