import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { loginAdmin } from '../services/authService';
import { useAuth } from '../context/AuthContext';
import { Lock } from 'lucide-react';

export const Login: React.FC = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      const data = await loginAdmin(username, password);
      login(data.access_token);
      navigate('/merchants');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'System authentication failed. Verify credentials.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-100 px-4">
      <div className="max-w-md w-full bg-white rounded-lg shadow-xl border border-gray-200 p-8">
        <div className="flex flex-col items-center mb-8">
          <div className="p-3 bg-gray-900 text-white rounded-full mb-3">
            <Lock size={24} />
          </div>
          <h2 className="text-2xl font-bold text-gray-900">Elevated System Access</h2>
          <p className="text-sm text-gray-500 mt-1">Platform Administrative Controls</p>
        </div>

        {error && (
          <div className="mb-6 p-3 bg-red-50 border border-red-200 text-red-700 text-sm rounded">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Administrative User</label>
            <input
              type="text"
              required
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-gray-900 focus:border-gray-900"
              placeholder="e.g., admin_root"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Security Keyphrase</label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-gray-900 focus:border-gray-900"
              placeholder="••••••••••••"
            />
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="w-full bg-gray-900 hover:bg-gray-800 text-white py-2 px-4 rounded font-medium transition-colors disabled:bg-gray-400"
          >
            {submitting ? 'Verifying Context...' : 'Authorize Session'}
          </button>
        </form>
      </div>
    </div>
  );
};