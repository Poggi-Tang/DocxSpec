import type { DraftContent } from "./document";

export async function api<T = any>(
  path: string,
  body?: unknown,
  method = body ? "POST" : "GET",
): Promise<T> {
  const form = body instanceof FormData;
  const response = await fetch("/api/v2" + path, {
    method,
    headers: form ? {} : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : form ? body : JSON.stringify(body),
  });
  const value = await response.json();
  if (!response.ok) {
    throw new Error(
      typeof value.detail === "string"
        ? value.detail
        : JSON.stringify(value.detail ?? value),
    );
  }
  return value;
}

export async function downloadTemplateBundle(
  draft: Pick<DraftContent, "name" | "document">,
): Promise<void> {
  const response = await fetch("/api/v2/template-bundles", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: draft.name, document: draft.document }),
  });
  if (!response.ok) {
    const value = await response.json().catch(() => null);
    throw new Error(
      typeof value?.detail === "string"
        ? value.detail
        : "模板包导出失败，请检查模板内容和本机存储。",
    );
  }

  const disposition = response.headers.get("Content-Disposition") ?? "";
  const encoded = /filename\*=utf-8''([^;]+)/i.exec(disposition)?.[1];
  const name = encoded
    ? decodeURIComponent(encoded)
    : (/filename="([^"]+)"/i.exec(disposition)?.[1] ?? "模板包.zip");
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

const jobMessages: Record<string, string> = {
  queued: "排队中",
  compiling: "正在生成 DOCX",
  rendering: "正在 Office 中排版",
  analyzing: "AI 正在分析报告",
};

export interface Job<T> {
  id: string;
  status: string;
  result: T;
  error?: string;
}

export class JobFailedError extends Error {}

export async function pollJob<T>(
  id: string,
  onProgress: (message: string) => void,
  isCurrent = () => true,
): Promise<Job<T> | undefined> {
  while (isCurrent()) {
    const job = await api<Job<T>>("/jobs/" + id);
    if (!isCurrent()) return;
    if (job.status === "ready") return job;
    if (job.status === "failed" || job.status === "cancelled") {
      throw new JobFailedError(job.error || "任务已取消");
    }
    onProgress(jobMessages[job.status] ?? job.status);
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
}
