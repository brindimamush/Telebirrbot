import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider } from './context/AuthContext';
import { ProtectedRoute } from './components/layout/ProtectedRoute';
import { DashboardLayout } from './components/layout/DashboardLayout';
import { Login } from './pages/Login';
import { MerchantTable } from './features/merchants/MerchantTable';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            {/* Public Access Layer */}
            <Route path="/login" element={<Login />} />

            {/* Protected Gateways */}
            <Route element={<ProtectedRoute />}>
              <Route element={<DashboardLayout />}>
                <Route path="/" element={<Navigate to="/merchants" replace />} />
                <Route path="/merchants" element={<MerchantTable />} />
                
                {/* Fallback component placeholds for building subsequent features */}
                <Route path="/fraud" element={<div className="text-xl font-bold">Fraud Queue Pipeline</div>} />
                <Route path="/analytics" element={<div className="text-xl font-bold">Financial Performance Analytics</div>} />
                <Route path="/settings" element={<div className="text-xl font-bold">Platform Configuration Matrix</div>} />
              </Route>
            </Route>

            {/* Global Wildcard Fallback */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
}

export default App;