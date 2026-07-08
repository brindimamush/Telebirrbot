import React from 'react';
import { Outlet, Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { Users, ShieldAlert, BarChart3, Settings, LogOut } from 'lucide-react';

export const DashboardLayout: React.FC = () => {
  const { adminName, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="flex h-screen bg-gray-100 overflow-hidden">
      {/* Sidebar Navigation */}
      <aside className="w-64 bg-gray-900 text-white flex flex-col justify-between">
        <div className="p-6">
          <div className="text-xl font-bold tracking-wider border-b border-gray-800 pb-4 mb-6">
            PVP GATEWAY
          </div>
          <nav className="space-y-1">
            <Link to="/merchants" className="flex items-center gap-3 px-4 py-3 rounded-md hover:bg-gray-800 transition-colors">
              <Users size={18} /> <span className="text-sm font-medium">Merchants</span>
            </Link>
            <Link to="/fraud" className="flex items-center gap-3 px-4 py-3 rounded-md hover:bg-gray-800 transition-colors">
              <ShieldAlert size={18} /> <span className="text-sm font-medium">Fraud Queue</span>
            </Link>
            <Link to="/analytics" className="flex items-center gap-3 px-4 py-3 rounded-md hover:bg-gray-800 transition-colors">
              <BarChart3 size={18} /> <span className="text-sm font-medium">Analytics</span>
            </Link>
            <Link to="/settings" className="flex items-center gap-3 px-4 py-3 rounded-md hover:bg-gray-800 transition-colors">
              <Settings size={18} /> <span className="text-sm font-medium">Configuration</span>
            </Link>
          </nav>
        </div>

        {/* Admin Footer Controls */}
        <div className="p-4 border-t border-gray-800 bg-gray-950 flex items-center justify-between">
          <div className="truncate pr-2">
            <p className="text-xs text-gray-400">Authenticated as</p>
            <p className="text-sm font-semibold truncate text-white">{adminName || 'Admin'}</p>
          </div>
          <button onClick={handleLogout} className="p-2 text-gray-400 hover:text-red-400 transition-colors" title="Log Out">
            <LogOut size={18} />
          </button>
        </div>
      </aside>

      {/* Main App Feed Container */}
      <main className="flex-1 overflow-y-auto p-8">
        <Outlet />
      </main>
    </div>
  );
};