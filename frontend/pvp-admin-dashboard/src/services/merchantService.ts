import { apiClient } from '../lib/api';
import type { Merchant, PaginatedResponse } from '../types/merchant';

export const getMerchants = async (page: number = 1, limit: number = 20) => {
  const response = await apiClient.get<PaginatedResponse<Merchant>>('/admin/merchants', {
    params: { page, limit }
  });
  return response.data;
};

export const rotateMerchantKey = async (merchantId: number) => {
  const response = await apiClient.post(`/admin/merchants/${merchantId}/rotate-key`);
  return response.data;
};