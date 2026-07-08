export interface LoginResponse {
  access_token: string;
  token_type: string;
}

export interface AdminTokenPayload {
  sub: string;         // Username or ID
  type: string;        // Expecting "admin_access"
  is_superuser: boolean;
  exp: number;         // Expiration timestamp
}