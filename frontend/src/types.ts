export type User = {
  id: number;
  username: string;
  role: "admin" | "clinician" | "patient";
  patient_id: number | null;
};

export type Patient = {
  public_id: string;
  first_name: string;
  last_name: string;
  date_of_birth: string | null;
  is_active: boolean;
  created_at: string;
};

export type Message = {
  id: number;
  chat_session_id: string;
  role: "patient" | "agent" | "clinician" | "system";
  content: string;
  sequence_number: number;
  flagged: boolean;
  created_at: string;
};

export type Consultation = {
  public_id: string;
  patient_id: number;
  status: "active" | "completed" | "cancelled";
  started_at: string;
  ended_at: string | null;
  requires_review: boolean;
  has_assessment: boolean;
  messages: Message[];
};

export type VoiceRecording = {
  public_id: string;
  consultation_id: number;
  content_type: string;
  byte_size: number;
  created_at: string;
};

export type Question = {
  number: number;
  text: string;
  answer_options: string[];
};

export type Answer = {
  question_number: number;
  question_text: string;
  score: number;
  answer_text: string;
};

export type Assessment = {
  public_id: string;
  instrument: string;
  status: "in_progress" | "completed";
  total_score: number | null;
  severity: string | null;
  started_at: string;
  completed_at: string | null;
  answers: Answer[];
};

export type AssessmentComparison = {
  assessment: Assessment;
  score_change: number | null;
  answer_changes: Record<string, number>;
};

export type SafetyEvent = {
  id: number;
  consultation_id: number;
  reason: string;
  action_taken: string;
  status: "open" | "acknowledged" | "resolved";
  created_at: string;
  resolved_at: string | null;
};

export type Summary = {
  id: number;
  consultation_id: number;
  content: string;
  generated_by: string;
  review_status: "draft" | "approved" | "rejected";
  reviewed_at: string | null;
  created_at: string;
};
