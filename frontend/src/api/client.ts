import type { ValidationIssue } from "./types";

/**
 * Error thrown for any non-2xx response. `fieldErrors` maps a top-level body field
 * (e.g. "price_minor") to its first validation message, for inline form display.
 */
export class ApiError extends Error {
  readonly status: number;
  readonly fieldErrors: Readonly<Record<string, string>>;

  constructor(status: number, message: string, fieldErrors: Record<string, string> = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.fieldErrors = Object.freeze({ ...fieldErrors });
  }
}

type Method = "GET" | "POST" | "PATCH" | "DELETE";

function isValidationIssue(value: unknown): value is ValidationIssue {
  return (
    typeof value === "object" &&
    value !== null &&
    Array.isArray((value as ValidationIssue).loc) &&
    typeof (value as ValidationIssue).msg === "string"
  );
}

/** ["body", "price_minor"] -> "price_minor"; ["body", "attributes", "size"] -> "attributes". */
function fieldFromLoc(loc: (string | number)[]): string {
  const [scope, field] = loc;
  if ((scope === "body" || scope === "query" || scope === "path") && field !== undefined) {
    return String(field);
  }
  return loc.map(String).join(".") || "_";
}

function cleanMessage(msg: string): string {
  return msg.replace(/^Value error, /, "");
}

function errorFromDetail(status: number, detail: unknown, fallback: string): ApiError {
  if (typeof detail === "string" && detail.trim()) {
    return new ApiError(status, detail);
  }
  if (Array.isArray(detail) && detail.length > 0) {
    const issues = detail.filter(isValidationIssue);
    // First message per field wins (Object.fromEntries keeps the last, so reverse first).
    const fieldErrors = Object.fromEntries(
      [...issues].reverse().map((issue) => [fieldFromLoc(issue.loc), cleanMessage(issue.msg)]),
    );
    const summary = issues.map((i) => `${fieldFromLoc(i.loc)}: ${cleanMessage(i.msg)}`).join("; ");
    return new ApiError(status, summary || fallback, fieldErrors);
  }
  return new ApiError(status, fallback);
}

function fallbackMessage(status: number, statusText: string): string {
  if (status === 401) return "You're signed out. Reload the page to sign in again.";
  if (status === 403) return "You don't have access to this.";
  if (status === 404) return "Not found.";
  if (status >= 500) return "The server hit an error. Try again in a moment.";
  return statusText || `Request failed (${status})`;
}

async function readBody(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return undefined;
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return text;
  }
}

async function request<T>(method: Method, path: string, body?: unknown): Promise<T> {
  const init: RequestInit = {
    method,
    credentials: "same-origin",
    headers:
      body === undefined
        ? { Accept: "application/json" }
        : { "Content-Type": "application/json", Accept: "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  };

  let response: Response;
  try {
    response = await fetch(path, init);
  } catch {
    throw new ApiError(0, "Can't reach the Salesie server. Is the backend running?");
  }

  const parsed = await readBody(response);
  if (!response.ok) {
    const detail =
      typeof parsed === "object" && parsed !== null ? (parsed as { detail?: unknown }).detail : parsed;
    throw errorFromDetail(response.status, detail, fallbackMessage(response.status, response.statusText));
  }
  return parsed as T;
}

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body: unknown) => request<T>("POST", path, body),
  patch: <T>(path: string, body: unknown) => request<T>("PATCH", path, body),
};

export function errorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  return "Something went wrong.";
}

export function fieldErrorsOf(error: unknown): Readonly<Record<string, string>> {
  return error instanceof ApiError ? error.fieldErrors : {};
}
