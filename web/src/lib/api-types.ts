export type Role = "admin" | "member";

export interface User {
  id: string;
  username: string;
  role: Role;
  created_at: string;
  disabled: boolean;
}

export interface AuthMeResponse {
  ok: boolean;
  user?: User;
  error?: string;
}

export interface LoginResponse {
  ok: boolean;
  user?: User;
  token?: string;
  error?: string;
}

export interface HealthResponse {
  ok: boolean;
  helper_ok?: boolean;
  accounts?: number;
  image_global_concurrency?: number;
}

export interface CandidatesResponse {
  ok: boolean;
  count?: number;
  accounts?: Array<{
    email: string;
    proxy_host: string;
    has_token: boolean;
  }>;
}

export interface QuotaResponse {
  ok: boolean;
  email?: string;
  remaining?: number;
  imageable?: boolean;
  error?: string;
}

export interface UsersListResponse {
  ok: boolean;
  users?: User[];
  error?: string;
}

export interface BackendCapabilities {
  ok: boolean;
  service?: string;
  wave?: string;
  helper_ok?: boolean;
  features?: {
    auth?: boolean;
    chat?: boolean;
    chat_stream?: boolean;
    models?: boolean;
    quota_probe?: boolean;
    account_candidates?: boolean;
    image_generations?: boolean;
    image_edits?: boolean;
    estuary_download?: boolean;
  };
  deferred?: string[];
  notes?: Record<string, string>;
}
