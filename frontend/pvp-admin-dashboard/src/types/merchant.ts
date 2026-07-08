export interface Merchant {
  id: number;
  name: string;
  telegram_user_id: number;
  payment_phone: string;
  subscription_expires_at: string | null;
  is_active: boolean;
  created_at: string;
}

export interface PaginatedResponse<T> {
  total: number;
  data: T[];
}