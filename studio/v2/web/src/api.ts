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
