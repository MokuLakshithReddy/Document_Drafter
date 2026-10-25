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
      body: formData,
    });
    return handleResponse<DocumentInfo>(res);
  },

  async getDocument(id: string): Promise<DocumentInfo> {
    const res = await fetch(`${getApiBase()}/documents/${id}`);
    return handleResponse<DocumentInfo>(res);
  },

  async deleteDocument(id: string): Promise<{ message: string; id: string }> {
    const res = await fetch(`${getApiBase()}/documents/${id}`, {
      method: 'DELETE',
    });
    return handleResponse<{ message: string; id: string }>(res);
  },

  // Analysis
  async analyzeDocument(id: string): Promise<AnalysisResult> {
    const res = await fetch(`${getApiBase()}/documents/${id}/analyze`, {
      method: 'POST',
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
      headers: { 'Content-Type': 'application/json' },
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
    const res = await fetch(`${getApiBase()}/templates`);
    return handleResponse<TemplateSummary[]>(res);
  },

  async getTemplate(id: string): Promise<TemplateDetail> {
    const res = await fetch(`${getApiBase()}/templates/${id}`);
    return handleResponse<TemplateDetail>(res);
  },

  async updateVariable(
    templateId: string,
    variableId: string,
    data: Partial<VariableItem>
  ): Promise<VariableItem> {
    const res = await fetch(`${getApiBase()}/templates/${templateId}/variables/${variableId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
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
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        values,
        output_format: outputFormat,
      }),
    });
    return handleResponse<GenerationJob>(res);
  },

  async getGeneration(id: string): Promise<GenerationJob> {
    const res = await fetch(`${getApiBase()}/generations/${id}`);
    return handleResponse<GenerationJob>(res);
  },

  async listGenerations(): Promise<GenerationJob[]> {
    const res = await fetch(`${getApiBase()}/generations`);
    return handleResponse<GenerationJob[]>(res);
  },

  getDownloadUrl(jobId: string): string {
    return `${getApiBase()}/generations/${jobId}/download`;
  },

  // Settings
  async getSettings(): Promise<AppSettings> {
    const res = await fetch(`${getApiBase()}/settings`);
    return handleResponse<AppSettings>(res);
  },

  async updateSettings(data: import('../types').UpdateSettingsRequest): Promise<AppSettings> {
    const res = await fetch(`${getApiBase()}/settings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    return handleResponse<AppSettings>(res);
  },
};
