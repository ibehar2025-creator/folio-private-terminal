import { useQuery } from "@tanstack/react-query";
let csrf = "";
export function setCsrf(value: string) {
  csrf = value;
}
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}
export async function api<T>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  const response = await fetch("/api" + path, {
    method,
    credentials: "same-origin",
    headers:
      method === "GET"
        ? {}
        : { "Content-Type": "application/json", "X-CSRF-Token": csrf },
    body: method === "GET" ? undefined : JSON.stringify(body ?? {}),
  });
  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Unable to reach the server" }));
    if (response.status === 401 && path != "/auth/login" && path != "/auth/me")
      window.dispatchEvent(new Event("session-expired"));
    const message =
      typeof error.detail === "string"
        ? error.detail
        : Array.isArray(error.detail)
          ? error.detail
              .map(
                (x: { loc?: string[]; msg: string }) =>
                  `${x.loc?.slice(1).join(".")}: ${x.msg}`,
              )
              .join("; ")
          : "Request failed";
    throw new ApiError(message, response.status);
  }
  return response.json();
}
export function useData<T>(path: string, enabled = true) {
  return useQuery<T, Error>({
    queryKey: [path],
    queryFn: () => api<T>(path),
    enabled,
    staleTime: 60000,
    retry: (count, error) =>
      !(error instanceof ApiError && error.status < 500) && count < 1,
  });
}
