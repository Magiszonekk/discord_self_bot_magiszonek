const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

interface ApiResponse<T = unknown> {
  success?: boolean;
  error?: string;
  data?: T;
}

async function fetchApi<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const response = await fetch(url, {
    ...options,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      ...options.headers,
    },
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.error || errorData.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

// Auth
export async function login(username: string, password: string): Promise<ApiResponse> {
  return fetchApi("/api/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

export async function logout(): Promise<ApiResponse> {
  return fetchApi("/api/logout");
}

export interface AuthStatus {
  authenticated: boolean;
  username?: string;
  permissions?: string[];
}

export async function checkAuth(): Promise<AuthStatus> {
  return fetchApi("/api/auth/status");
}

// Statuses
export interface Status {
  id: number;
  person_name: string;
  person_id: number;
  status: string;
  date_add: string;
  category: string;
  approved_by_user_id: number | null;
}

export async function getStatuses(): Promise<Status[]> {
  return fetchApi("/api/statuses");
}

export async function addStatus(status: string, category: string): Promise<ApiResponse> {
  const formData = new URLSearchParams();
  formData.append("status", status);
  formData.append("category", category);

  return fetchApi("/api/statuses", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: formData.toString(),
  });
}

export async function deleteStatus(id: number): Promise<ApiResponse> {
  return fetchApi(`/api/statuses/${id}/delete`, { method: "POST" });
}

export async function approveStatus(id: number): Promise<ApiResponse> {
  return fetchApi(`/api/statuses/${id}/approve`, { method: "POST" });
}

export async function revokeStatus(id: number): Promise<ApiResponse> {
  return fetchApi(`/api/statuses/${id}/revoke`, { method: "POST" });
}

// Categories
export interface Category {
  id: number;
  label: string;
  created_by_user_id: number;
  date_add: string;
}

export async function getCategories(): Promise<Category[]> {
  return fetchApi("/api/categories");
}

export async function addCategory(name: string): Promise<ApiResponse> {
  const formData = new URLSearchParams();
  formData.append("name", name);

  return fetchApi("/api/categories", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: formData.toString(),
  });
}

export async function deleteCategory(name: string): Promise<ApiResponse> {
  return fetchApi(`/api/categories/${encodeURIComponent(name)}/delete`, { method: "POST" });
}

// Discord Actions
export async function changeStatus(status?: string, random?: boolean): Promise<ApiResponse> {
  const formData = new URLSearchParams();
  if (status) formData.append("status", status);
  if (random) formData.append("random_status", "true");

  return fetchApi("/api/discord/change-status", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: formData.toString(),
  });
}

export async function sendDm(userId: string, message: string): Promise<ApiResponse> {
  const formData = new URLSearchParams();
  formData.append("user_id", userId);
  formData.append("message", message);

  return fetchApi("/api/discord/send-dm", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: formData.toString(),
  });
}

// DM Recipients
export interface DmRecipient {
  user_id: string;
  username: string;
  display_name: string;
  avatar: string | null;
}

export async function getDmRecipients(): Promise<DmRecipient[]> {
  return fetchApi("/api/discord/dm-recipients");
}

// EventSub
export async function getEventSubStatus(): Promise<{ running: boolean }> {
  return fetchApi("/api/eventsub/status");
}

export async function startEventSub(): Promise<ApiResponse> {
  return fetchApi("/api/eventsub/start", { method: "POST" });
}

export async function stopEventSub(): Promise<ApiResponse> {
  return fetchApi("/api/eventsub/stop", { method: "POST" });
}

// Rotation
export interface RotationStatus {
  enabled: boolean;
  interval_min: number;
  interval_max: number;
  approved_count: number;
}

export async function getRotationStatus(): Promise<RotationStatus> {
  return fetchApi("/api/rotation/status");
}

export async function toggleRotation(): Promise<ApiResponse> {
  return fetchApi("/api/rotation/toggle", { method: "POST" });
}

export async function setRotationSettings(minMinutes: number, maxMinutes: number): Promise<ApiResponse> {
  const formData = new URLSearchParams();
  formData.append("min_minutes", minMinutes.toString());
  formData.append("max_minutes", maxMinutes.toString());

  return fetchApi("/api/rotation/settings", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: formData.toString(),
  });
}

// Logs
export async function getLogs(lines: number = 30): Promise<{ logs: string[] }> {
  return fetchApi(`/api/logs?lines=${lines}`);
}
