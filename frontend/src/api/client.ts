import type {
  DocumentInfo,
  AnalysisResult,
  TemplateSummary,
  TemplateDetail,
  VariableItem,
  GenerationJob,
  AppSettings,
  Occurrence
} from '../types';

export function getApiBase(): string {
  return localStorage.getItem('DOCREUSE_API_URL') || (import.meta as any).env?.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api/v1';
}

export function getSessionId(): string {
  let sid = localStorage.getItem('DOCREUSE_SESSION_ID');
  if (!sid) {
    sid = 'sess_' + Math.random().toString(36).substring(2, 15) + Date.now().toString(36);
    localStorage.setItem('DOCREUSE_SESSION_ID', sid);
  }
  return sid;
}

export function getApiKey(): string {
  return localStorage.getItem('DOCREUSE_API_KEY') || '';
}

export function setApiKey(key: string): void {
  if (key) {
    localStorage.setItem('DOCREUSE_API_KEY', key);
  } else {
    localStorage.removeItem('DOCREUSE_API_KEY');
  }
}

export function getAuthHeaders(extraHeaders?: Record<string, string>): Record<string, string> {
  const headers: Record<string, string> = {
    'X-Session-ID': getSessionId(),
    ...(extraHeaders || {})
  };
  const key = getApiKey();
  if (key) {
    headers['X-API-Key'] = key;
  }
  return headers;
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let errorDetail = 'Network request failed';
    try {
      const errJson = await res.json();
      errorDetail = errJson.detail?.message || errJson.message || JSON.stringify(errJson);
    } catch {
      errorDetail = `HTTP ${res.status}: ${res.statusText}`;
    }
    throw new Error(errorDetail);
  }
  return res.json();
}

export const api = {
  // Documents
  async uploadDocument(file: File): Promise<DocumentInfo> {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(`${getApiBase()}/documents`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: formData,
    });
    return handleResponse<DocumentInfo>(res);
  },

  async getDocument(id: string): Promise<DocumentInfo> {
    const res = await fetch(`${getApiBase()}/documents/${id}`, {
      headers: getAuthHeaders(),
    });
    return handleResponse<DocumentInfo>(res);
  },

  async deleteDocument(id: string): Promise<{ message: string; id: string }> {
    const res = await fetch(`${getApiBase()}/documents/${id}`, {
      method: 'DELETE',
      headers: getAuthHeaders(),
    });
    return handleResponse<{ message: string; id: string }>(res);
  },

  // Analysis
  async analyzeDocument(id: string): Promise<AnalysisResult> {
    const res = await fetch(`${getApiBase()}/documents/${id}/analyze`, {
      method: 'POST',
      headers: getAuthHeaders(),
    });
    return handleResponse<AnalysisResult>(res);
  },

  // Templates
  async saveTemplate(
    name: string,
    documentId: string,
    variables: VariableItem[],
    occurrences?: Occurrence[]
  ): Promise<TemplateDetail> {
    const res = await fetch(`${getApiBase()}/templates`, {
      method: 'POST',
      headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({
        name,
        document_id: documentId,
        variables,
        occurrences,
      }),
    });
    return handleResponse<TemplateDetail>(res);
  },

  async listTemplates(): Promise<TemplateSummary[]> {
    const res = await fetch(`${getApiBase()}/templates`, {
      headers: getAuthHeaders(),
    });
    return handleResponse<TemplateSummary[]>(res);
  },

  async getTemplate(id: string): Promise<TemplateDetail> {
    const res = await fetch(`${getApiBase()}/templates/${id}`, {
      headers: getAuthHeaders(),
    });
    return handleResponse<TemplateDetail>(res);
  },

  async updateVariable(
    templateId: string,
    variableId: string,
    data: Partial<VariableItem>
  ): Promise<VariableItem> {
    const res = await fetch(`${getApiBase()}/templates/${templateId}/variables/${variableId}`, {
      method: 'PATCH',
      headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(data),
    });
    return handleResponse<VariableItem>(res);
  },

  // Generation
  async generateDocument(
    templateId: string,
    values: Record<string, string>,
    outputFormat: 'docx' | 'pdf' = 'docx'
  ): Promise<GenerationJob> {
    const res = await fetch(`${getApiBase()}/templates/${templateId}/generate`, {
      method: 'POST',
      headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({
        values,
        output_format: outputFormat,
      }),
    });
    return handleResponse<GenerationJob>(res);
  },

  async getGeneration(id: string): Promise<GenerationJob> {
    const res = await fetch(`${getApiBase()}/generations/${id}`, {
      headers: getAuthHeaders(),
    });
    return handleResponse<GenerationJob>(res);
  },

  async listGenerations(): Promise<GenerationJob[]> {
    const res = await fetch(`${getApiBase()}/generations`, {
      headers: getAuthHeaders(),
    });
    return handleResponse<GenerationJob[]>(res);
  },

  getDownloadUrl(jobId: string): string {
    const base = `${getApiBase()}/generations/${jobId}/download`;
    const key = getApiKey();
    const sid = getSessionId();
    const params = new URLSearchParams();
    if (key) params.append('api_key', key);
    if (sid) params.append('session_id', sid);
    const q = params.toString();
    return q ? `${base}?${q}` : base;
  },

  // Settings
  async getSettings(): Promise<AppSettings> {
    const res = await fetch(`${getApiBase()}/settings`, {
      headers: getAuthHeaders(),
    });
    return handleResponse<AppSettings>(res);
  },

  async updateSettings(data: import('../types').UpdateSettingsRequest): Promise<AppSettings> {
    const res = await fetch(`${getApiBase()}/settings`, {
      method: 'POST',
      headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(data),
    });
    return handleResponse<AppSettings>(res);
  },
};
