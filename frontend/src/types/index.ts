export type VariableType =
  | 'person_name'
  | 'organization'
  | 'date'
  | 'address'
  | 'money'
  | 'phone'
  | 'email'
  | 'identifier'
  | 'role'
  | 'location'
  | 'custom';

export interface SourceLocator {
  kind: string;
  container_id: string;
  run_index?: number;
  char_start?: number;
  char_end?: number;
  bbox?: number[];
  page?: number;
}

export interface Occurrence {
  id: string;
  variable_id?: string;
  source_locator: SourceLocator;
  original_text: string;
  status: 'active' | 'excluded';
}

export interface VariableItem {
  id: string;
  key: string;
  label: string;
  type: VariableType;
  original_value: string;
  replacement_value?: string;
  occurrence_ids: string[];
  confidence?: number;
  reason?: string;
  required: boolean;
  status: 'pending' | 'approved' | 'excluded';
}

export interface DocumentInfo {
  id: string;
  filename: string;
  format: 'docx' | 'pdf';
  sha256: string;
  created_at: string;
  status: string;
  page_count: number;
  error_message?: string;
}

export interface AnalysisResult {
  document_id: string;
  document_type: string;
  extracted_text_preview: string;
  total_paragraphs: number;
  total_tables: number;
  has_headers_footers: boolean;
  is_scanned: boolean;
  warning?: string;
  occurrences: Occurrence[];
  variables: VariableItem[];
}

export interface TemplateSummary {
  id: string;
  name: string;
  source_document_id: string;
  source_filename: string;
  source_format: 'docx' | 'pdf';
  version: number;
  status: string;
  created_at: string;
  variable_count: number;
}

export interface TemplateDetail {
  id: string;
  name: string;
  source_document_id: string;
  source_filename: string;
  source_format: 'docx' | 'pdf';
  source_checksum: string;
  version: number;
  status: string;
  created_at: string;
  variables: VariableItem[];
  occurrences: Occurrence[];
}

export interface ValidationIssue {
  severity: 'error' | 'warning';
  code: string;
  message: string;
  location?: string;
}

export interface ValidationReport {
  status: 'passed' | 'warning' | 'failed';
  intended_replacements_count: number;
  verified_replacements_count: number;
  protected_content_verified: boolean;
  issues: ValidationIssue[];
}

export interface GenerationJob {
  id: string;
  template_id: string;
  template_version: number;
  output_format?: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  created_at: string;
  error_code?: string;
  error_message?: string;
  validation_report?: ValidationReport;
  download_url?: string;
}

export interface AppSettings {
  ai_provider: string;
  has_gemini_key: boolean;
  has_openai_key: boolean;
  max_upload_size_mb: number;
  max_page_limit: number;
  file_retention_days: number;
  storage_dir: string;
}

export interface UpdateSettingsRequest {
  ai_provider?: string;
  gemini_api_key?: string;
  openai_api_key?: string;
  file_retention_days?: number;
}
