/** API 客户端：封装 fetch，统一错误处理。 */

async function request(path, options = {}) {
  const opts = { ...options };
  if (opts.body && !(opts.body instanceof FormData)) {
    opts.headers = { 'Content-Type': 'application/json', ...(opts.headers || {}) };
    opts.body = JSON.stringify(opts.body);
  }
  const res = await fetch(path, opts);
  if (!res.ok) {
    let msg = `${res.status} ${res.statusText}`;
    try { const j = await res.json(); msg = j.detail || msg; } catch (_) {}
    throw new Error(msg);
  }
  return res.json();
}

export const api = {
  // dashboard
  dashboard: () => request('/api/dashboard'),

  // conversations
  listConversations: (page = 1, size = 20) =>
    request(`/api/conversations?page=${page}&size=${size}`),
  getConversation: (chatId) => request(`/api/conversations/${chatId}`),

  // rag
  listRag: () => request('/api/rag'),
  ingestRag: (form) => request('/api/rag/ingest', { method: 'POST', body: form }),
  deleteRag: (docId) => request(`/api/rag/${docId}`, { method: 'DELETE' }),
  searchRag: (q, itemId) =>
    request(`/api/rag/search?q=${encodeURIComponent(q)}${itemId ? '&item_id=' + itemId : ''}`),

  // prompts
  listPrompts: () => request('/api/prompts'),
  updatePrompt: (key, content, reload = true) =>
    request(`/api/prompts/${key}`, { method: 'PUT', body: { content, reload } }),

  // config
  getConfig: () => request('/api/config'),
  updateConfig: (data) => request('/api/config', { method: 'PUT', body: data }),
  testConfig: (targets) => request('/api/config/test', { method: 'POST', body: { targets } }),

  // logs
  logSources: () => request('/api/logs/sources'),
  readLogs: (source = 'bot', lines = 300, level = '', keyword = '') =>
    request(`/api/logs?source=${source}&lines=${lines}&level=${encodeURIComponent(level)}` +
            `&keyword=${encodeURIComponent(keyword)}`),
  clearLogs: (source = 'bot') => request(`/api/logs?source=${source}`, { method: 'DELETE' }),
  logDownloadUrl: (source = 'bot') => `/api/logs/download?source=${source}`,
};
