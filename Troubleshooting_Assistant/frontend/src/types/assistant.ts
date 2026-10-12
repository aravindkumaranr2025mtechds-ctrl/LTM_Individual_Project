export type WorkflowStage =
  | 'report'
  | 'understand'
  | 'evidence'
  | 'checks'
  | 'decision'
  | 'summary'

export type FinalDecision =
  | 'ANSWER'
  | 'CLARIFY'
  | 'ABSTAIN'
  | 'ESCALATE'

export type UserView =
  | 'technician'
  | 'engineering'

export type SupportArea =
  | 'technical'
  | 'fresher'
  | 'trainee'
  | 'department'

export interface TechnicalContext {
  manufacturer?: string
  alarmNumber?: string
  query?: string
  machine?: string

  abbRequest?:
    | 'list_possible_causes'
    | 'review_reports'
    | 'identify_cause'
}

export interface EvidenceItem {
  evidence_id: string
  evidence_id_origin?: 'source' | 'adapter'
  source_type?: string
  document_id?: string | null
  source_filename?: string | null
  page_numbers: number[]
  content: string
  metadata?: Record<string, unknown>
}

export interface EvidenceContract {
  schema?: string
  mode?: string
  source_status?: string
  source_validation?: string
  evidence_count: number
  items: EvidenceItem[]
  diagnosis_confirmed?: boolean
  automatic_execution?: boolean
}

export interface FinalOutcome {
  schema?: string
  decision: FinalDecision
  reason_code?: string
  terminal_action?: string
}

export interface AssistantResponse {
  status?: string
  mode?: string
  message?: string

  final_outcome?: FinalOutcome
  evidence_contract?: EvidenceContract

  diagnosis_confirmed?: boolean
  approved_for_automatic_execution?: boolean

  next_question?: unknown

  [key: string]: unknown
}

