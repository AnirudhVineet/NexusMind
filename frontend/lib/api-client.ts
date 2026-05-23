"use client";

import { signOut } from "next-auth/react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function getToken(): Promise<string | null> {
  const res = await fetch("/api/auth/session");
  if (!res.ok) return null;
  const json = await res.json();
  return json?.accessToken ?? null;
}

interface RequestOptions {
  method?: string;
  body?: BodyInit | object;
  headers?: Record<string, string>;
  isFormData?: boolean;
}

export class ApiError extends Error {
  status: number;
  code: string;
  requestId?: string;
  constructor(status: number, message: string, code = "error", requestId?: string) {
    super(message);
    this.status = status;
    this.code = code;
    this.requestId = requestId;
  }
}

export async function apiFetch<T>(
  path: string,
  opts: RequestOptions = {}
): Promise<T> {
  const token = await getToken();
  const headers: Record<string, string> = {
    Accept: "application/json",
    ...(opts.headers ?? {}),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (!opts.isFormData) headers["Content-Type"] = "application/json";

  const body =
    opts.body == null
      ? undefined
      : opts.isFormData
      ? (opts.body as BodyInit)
      : typeof opts.body === "string"
      ? opts.body
      : JSON.stringify(opts.body);

  const res = await fetch(`${API_URL}${path}`, {
    method: opts.method ?? "GET",
    headers,
    body,
  });

  if (res.status === 401) {
    try { await signOut({ redirect: false }); } catch {}
    if (typeof window !== "undefined") window.location.href = "/sign-in";
    throw new ApiError(401, "Unauthorized");
  }

  if (!res.ok) {
    let detail = res.statusText;
    let code = "error";
    let requestId: string | undefined;
    try {
      const errJson = await res.json();
      const raw = errJson.detail ?? detail;
      detail = Array.isArray(raw)
        ? raw.map((e: any) => e.msg ?? JSON.stringify(e)).join("; ")
        : String(raw);
      code = errJson.code ?? code;
      requestId = errJson.request_id;
    } catch {}
    throw new ApiError(res.status, detail, code, requestId);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

/** Fetch a file response (e.g. exports) as a Blob, with auth attached. */
export async function apiFetchBlob(path: string): Promise<Blob> {
  const token = await getToken();
  const headers: Record<string, string> = { Accept: "*/*" };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_URL}${path}`, { headers });
  if (!res.ok) {
    throw new ApiError(res.status, res.statusText || "Download failed");
  }
  return res.blob();
}
