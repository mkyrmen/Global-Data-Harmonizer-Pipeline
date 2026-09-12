export interface Source {
  id: string;
  name: string;
  row_count: number;
  column_names: string[];
  preview_json: Record<string, unknown>[];
  include: boolean;
  sort_order: number;
  created_at: string;
  workspace_id?: string | null;
}

export interface Workspace {
  id: string;
  name: string;
  description: string;
  created_at: string;
  sources: Source[];
}

export interface QualityInfo {
  score: number;
  deductions: Record<string, number>;
  dimensions?: Record<string, unknown>;
}

export interface ValidationSummary {
  passed: number;
  failed: number;
}

export interface ConflictRecord {
  key_field: string;
  key_value: string;
  field: string;
  values: unknown[];
  selected_value: unknown;
  policy: string;
}

export interface JobResult {
  job_id: string;
  pipeline_id: string;
  status: string;
  input_rows: number;
  output_rows: number;
  duplicates_removed: number;
  conflicts: ConflictRecord[];
  quality_before: QualityInfo | null;
  quality_after: QualityInfo | null;
  validation: ValidationSummary | null;
  transformation_count: number;
  columns: string[];
  dataset_id: string;
  outputs: Record<string, string>;
}

export interface JobRow {
  id: string;
  name: string;
  status: string;
  config_json: Record<string, unknown>;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
  dataset_ids: string[];
  dataset?: HarmonizedDataset;
}

export interface HarmonizedDataset {
  id: string;
  job_id: string;
  row_count: number;
  quality_before: number | null;
  quality_after: number | null;
  validation_status: string | null;
  data_json: Record<string, unknown>[];
  report_path: string | null;
  csv_path: string | null;
  created_at: string;
}