export type Health = {
  ok: boolean;
  app: string;
  version: string;
  localOnly: boolean;
  engine: { installed: boolean; loaded: boolean; device: string; torch: boolean; cuda: boolean };
  media: { ffmpeg: boolean; ffprobe: boolean };
  database: { status: string };
  message?: string;
};

export type VoiceProfile = {
  id: string;
  name: string;
  language: string;
  source_name: string;
  created_at?: string;
  sample_count?: number;
  enrollment_completion?: number;
  quality_score?: number | null;
  accent_notes?: string;
};

export type GenerationJob = {
  id: string;
  status: "queued" | "running" | "complete" | "failed";
  progress: number;
  message: string;
  error?: { code: string; message: string };
  history_id?: string;
  audio_url?: string;
  device?: string;
};

export type HistoryItem = {
  id: string;
  profile_id?: string | null;
  profile_name: string;
  script_preview: string;
  language: string;
  status: string;
  created_at: string;
  audio_url?: string | null;
};

export type ApiError = { ok: false; error: { code: string; message: string } };

export type StudioProjectSummary = {
  id: string;
  title: string;
  script_preview: string;
  character_count: number;
  profile_id: string | null;
  language_id: string;
  created_at: string;
  updated_at: string;
};

export type StudioProject = {
  id: string;
  title: string;
  script: string;
  profile_id: string | null;
  language_id: string;
  output_name: string;
  exaggeration: number;
  cfg_weight: number;
  temperature: number;
  model_id?: "chatterbox" | "voxcpm2";
  created_at: string;
  updated_at: string;
};
