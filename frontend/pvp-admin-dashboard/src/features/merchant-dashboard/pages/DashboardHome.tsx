// src/features/merchant-dashboard/pages/DashboardHome.tsx
import React from 'react';

const stats = [
  { name: 'Total Volume Processed', stat: '145,000 ETB', change: '+12%', changeType: 'increase' },
  { name: 'Successful Verifications', stat: '842', change: '+5.4%', changeType: 'increase' },
  { name: 'Pending Sessions', stat: '12', change: '-2', changeType: 'decrease' },
  { name: 'Parser Success Rate', stat: '99.2%', change: '+0.1%', changeType: 'increase' },
];

export const DashboardHome = () => {
  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-2xl font-bold leading-7 text-gray-900">Welcome back!</h2>
        <p className="mt-1 text-sm text-gray-500">Here is what's happening with your verification traffic today.</p>
      </div>

      <dl className="mt-5 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((item) => (
          <div key={item.name} className="relative overflow-hidden rounded-lg bg-white px-4 pb-12 pt-5 shadow sm:px-6 sm:pt-6 border border-gray-100">
            <dt>
              <div className="absolute rounded-md bg-indigo-500 p-3">
                 {/* Icon placeholder */}
                 <div className="h-6 w-6 text-white bg-indigo-500" />
              </div>
              <p className="ml-16 truncate text-sm font-medium text-gray-500">{item.name}</p>
            </dt>
            <dd className="ml-16 flex items-baseline pb-6 sm:pb-7">
              <p className="text-2xl font-semibold text-gray-900">{item.stat}</p>
              <p className={`ml-2 flex items-baseline text-sm font-semibold ${item.changeType === 'increase' ? 'text-green-600' : 'text-red-600'}`}>
                {item.change}
              </p>
            </dd>
          </div>
        ))}
      </dl>

      {/* Placeholder for Recent Transactions Table */}
      <div className="bg-white shadow rounded-lg p-6 border border-gray-200">
        <h3 className="text-lg font-medium leading-6 text-gray-900 mb-4">Recent Verification Sessions</h3>
        <div className="text-center text-gray-500 py-10 border-2 border-dashed border-gray-200 rounded-md">
          List of recent active polling sessions will render here.
        </div>
      </div>
    </div>
  );
};