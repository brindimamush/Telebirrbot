// src/features/merchant-dashboard/MerchantDashboardLayout.tsx
import React from 'react';
import { Outlet, NavLink } from 'react-router-dom';
import { 
  HomeIcon, ChartBarIcon, ShieldCheckIcon, 
  CurrencyDollarIcon, KeyIcon, CogIcon, 
  CreditCardIcon, DocumentTextIcon, BellIcon, UserIcon 
} from '@heroicons/react/24/outline'; // Assuming Heroicons for UI consistency

const navigation = [
  { name: 'Home Dashboard', href: '/merchant', icon: HomeIcon },
  { name: 'Statistics', href: '/merchant/statistics', icon: ChartBarIcon },
  { name: 'Verification Sessions', href: '/merchant/sessions', icon: ShieldCheckIcon },
  { name: 'Transactions', href: '/merchant/transactions', icon: CurrencyDollarIcon },
  { name: 'API Keys', href: '/merchant/api-keys', icon: KeyIcon },
  { name: 'Parser Status', href: '/merchant/parser-status', icon: DocumentTextIcon },
  { name: 'Subscription', href: '/merchant/subscription', icon: CreditCardIcon },
  { name: 'Billing History', href: '/merchant/billing', icon: CurrencyDollarIcon },
  { name: 'Webhook Settings', href: '/merchant/webhooks', icon: CogIcon },
  { name: 'Notification Settings', href: '/merchant/notifications', icon: BellIcon },
  { name: 'Merchant Profile', href: '/merchant/profile', icon: UserIcon },
];

export const MerchantDashboardLayout = () => {
  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar */}
      <div className="w-64 bg-white border-r border-gray-200 flex flex-col hidden md:flex">
        <div className="h-16 flex items-center px-6 border-b border-gray-200">
          <span className="text-xl font-bold text-indigo-600">Merchant Portal</span>
        </div>
        <nav className="flex-1 overflow-y-auto py-4 px-3 space-y-1">
          {navigation.map((item) => (
            <NavLink
              key={item.name}
              to={item.href}
              end={item.href === '/merchant'}
              className={({ isActive }) =>
                `flex items-center px-3 py-2 text-sm font-medium rounded-md transition-colors ${
                  isActive 
                    ? 'bg-indigo-50 text-indigo-700' 
                    : 'text-gray-700 hover:bg-gray-100'
                }`
              }
            >
              <item.icon className="mr-3 flex-shrink-0 h-5 w-5" aria-hidden="true" />
              {item.name}
            </NavLink>
          ))}
        </nav>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <header className="h-16 bg-white border-b border-gray-200 flex items-center justify-between px-6">
          <h1 className="text-lg font-semibold text-gray-900">Dashboard</h1>
          <div className="flex items-center space-x-4">
            <span className="text-sm text-gray-500">Production Environment</span>
            <button className="bg-gray-100 text-gray-700 px-3 py-1 rounded-md text-sm font-medium">Log out</button>
          </div>
        </header>
        
        <main className="flex-1 overflow-y-auto bg-gray-50 p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
};