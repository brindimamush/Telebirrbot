import { apiClient } from '../lib/api';
import type { LoginResponse } from '../types/auth';

export const loginAdmin = async (username: string, password: string): Promise<LoginResponse> => {
  // Using URLSearchParams because FastAPI's OAuth2PasswordRequestForm expects application/x-www-form-urlencoded
  const params = new URLSearchParams();
  params.append('username', username);
  params.append('password', password);

  // Adjust URL matching your FastAPI token/login endpoint
  const response = await apiClient.post<LoginResponse>('/token', params, {
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
  });
  return response.data;
};