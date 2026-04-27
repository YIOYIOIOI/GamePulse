export type ProgressEvent = {
  stage?: string;
  percent?: number;
  message?: string;
  rows?: number;
  done?: boolean;
  ok?: boolean;
  error?: string;
  results?: unknown[];
  reviews?: unknown[];
};

export async function postProgressStream<T>(url: string, payload: unknown, onEvent: (event: ProgressEvent) => void): Promise<T> {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok || !res.body) {
    const text = await res.text().catch(() => '');
    throw new Error(text || `请求失败：HTTP ${res.status}`);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let finalPayload: T | undefined;

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split('\n');
    buffer = parts.pop() || '';
    for (const part of parts) {
      const line = part.trim();
      if (!line) continue;
      const event = JSON.parse(line) as ProgressEvent;
      onEvent(event);
      if (event.done) {
        if (event.ok === false) throw new Error(event.error || event.message || '操作失败');
        finalPayload = event as T;
      }
    }
  }

  if (!finalPayload && buffer.trim()) {
    const event = JSON.parse(buffer.trim()) as ProgressEvent;
    onEvent(event);
    if (event.ok === false) throw new Error(event.error || event.message || '操作失败');
    if (event.done) finalPayload = event as T;
  }

  if (!finalPayload) throw new Error('服务端没有返回完成事件。');
  return finalPayload;
}
