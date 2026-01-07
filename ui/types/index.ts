/**
 * TypeScript types matching backend Pydantic models.
 * These types mirror src/mirage/models/types.py
 */

// Status types
export type RunStatus = 'queued' | 'running' | 'succeeded' | 'failed';
export type ExperimentStatus = 'draft' | 'running' | 'complete';
export type StatusBadge = 'pass' | 'flagged' | 'reject';
export type Choice = 'left' | 'right' | 'tie' | 'skip';

// Metrics bundle (Tier 0 + Tier 1 + Tier 2 + Status)
export interface MetricBundleV1 {
  // Tier 0 (ffmpeg/opencv/numpy)
  decode_ok: boolean;
  video_duration_ms: number;
  audio_duration_ms: number;
  av_duration_delta_ms: number;
  fps: number;
  frame_count: number;
  scene_cut_count: number;
  freeze_frame_ratio: number;
  flicker_score: number;
  blur_score: number;
  frame_diff_spike_count: number;

  // Tier 1 (mediapipe)
  face_present_ratio: number;
  face_bbox_jitter: number;
  landmark_jitter: number;
  mouth_open_energy: number;
  mouth_audio_corr: number;
  blink_count: number | null;
  blink_rate_hz: number | null;

  // Tier 2 (syncnet, optional)
  lse_d: number | null;
  lse_c: number | null;

  // Status
  status_badge: StatusBadge;
  reasons: string[];
}

// Generation spec detail
export interface GenerationSpecDetail {
  generation_spec_id: string;
  provider: string;
  model: string;
  model_version: string | null;
  prompt_template: string;
  params: Record<string, unknown> | null;
}

// Dataset item detail
export interface DatasetItemDetail {
  item_id: string;
  subject_id: string;
  source_video_uri: string;
  audio_uri: string;
  ref_image_uri: string | null;
}

// Run detail (individual variant)
export interface RunDetail {
  run_id: string;
  experiment_id: string;
  item_id: string;
  variant_key: string;
  spec_hash: string;
  status: RunStatus;
  output_canon_uri: string | null;
  output_sha256: string | null;
  metrics: MetricBundleV1 | null;
  status_badge: StatusBadge | null;
  reasons: string[];
}

// Human evaluation summary
export interface HumanSummary {
  win_rates: Record<string, number>;
  recommended_pick: string | null;
  total_comparisons: number;
}

// Experiment overview (main API response)
export interface ExperimentOverview {
  experiment_id: string;
  status: ExperimentStatus;
  generation_spec: GenerationSpecDetail;
  dataset_item: DatasetItemDetail;
  runs: RunDetail[];
  human_summary: HumanSummary | null;
}

// Task detail (for pairwise comparison)
export interface TaskDetail {
  task_id: string;
  experiment_id: string;
  left_run_id: string;
  right_run_id: string;
  presented_left_run_id: string;
  presented_right_run_id: string;
  flip: boolean;
  status: 'open' | 'assigned' | 'done' | 'void';
}

// Rating submission
export interface RatingSubmission {
  task_id: string;
  rater_id: string;
  choice_realism: Choice;
  choice_lipsync: Choice;
  choice_targetmatch?: Choice | null;
  notes?: string | null;
}
