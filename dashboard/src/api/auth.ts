import { apiClient } from "./client";

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export function login(username: string, password: string): Promise<TokenResponse> {
  return apiClient.post<TokenResponse>("/auth/login", { username, password });
}
