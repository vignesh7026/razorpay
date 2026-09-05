export type FailureReason =
  | 'card_declined'
  | 'checkout_abandoned'
  | 'insufficient_funds'
  | 'gateway_timeout'
  | 'otp_timeout'
  | 'mandate_insufficient_funds'
  | 'mandate_expired'

export type Outcome = 'recovered' | 'escalated' | 'pending_retry' | 'failed'

export interface FailureBucket {
  at_risk_inr: number
  recovered_inr: number
  rate: number
  count: number
}

export interface AuditRecord {
  transaction_id: string
  failure_reason: FailureReason
  intervention_chosen: string
  rule_fired: string
  outcome: Outcome
  stopping_rule_hit: string | boolean
  escalated_to_human: boolean
  amount_inr: number
  timestamp: string
  recovered_inr: number
  incentive_pct: number
  is_recurring: boolean
  customer_id: string
  customer_name: string
  product_name: string
  rule_notes: string
  product_margin_pct: number
  prior_retry_count: number
  intervention_variant?: string | null
  source?: 'webhook' | string
  execution: {
    success: boolean
    provider: 'real' | 'simulated'
    reference_id: string
    raw: Record<string, unknown>
  } | null
}

export interface Narrative {
  transaction_id: string
  provider: 'real' | 'simulated'
  customer_message: string
  audit_explanation: string
  escalation_briefing: string | null
}

export type ResolutionStatus = 'open' | 'approve' | 'override' | 'resolve'

export interface EscalationItem extends AuditRecord {
  resolution_status: ResolutionStatus
  resolution_note: string
  resolution_timestamp: string | null
}

export interface EscalationsResponse {
  count: number
  open_count: number
  items: EscalationItem[]
}

export interface BanditArm {
  variant: string
  label: string
  estimated_success_rate: number
  observations: number
  alpha: number
  beta: number
}

export type BanditState = Record<string, BanditArm[]>

export interface BaselineComparison {
  no_action_recovered_inr: number
  naive_generic_retry_recovered_inr: number
  agent_recovered_inr: number
  uplift_vs_naive_retry_inr: number
  uplift_vs_naive_retry_pct: number | null
  naive_retry_success_rate_assumed: number
  structurally_unretryable_reasons: string[]
}

export interface MarginAnalysis {
  at_risk_profit_inr: number
  recovered_profit_inr: number
  margin_recovery_rate: number
  total_incentive_cost_inr: number
}

export interface Report {
  generated_at: string
  total_transactions: number
  total_at_risk_inr: number
  total_recovered_inr: number
  recovery_rate_overall: number
  by_failure_reason: Record<string, FailureBucket>
  escalated_example: AuditRecord | null
  counts_by_outcome: Record<string, number>
  baseline_comparison: BaselineComparison
  margin_analysis: MarginAnalysis
  client_mode?: string
}

export interface AuditLogResponse {
  count: number
  records: AuditRecord[]
}

export interface SimulateFailureBucket {
  at_risk_inr: number
  recovered_inr: number
  count: number
  rate: number
}

export interface SimulateResult {
  total_transactions: number
  total_at_risk_inr: number
  total_recovered_inr: number
  recovery_rate_overall: number
  counts_by_outcome: Record<string, number>
  by_failure_reason: Record<string, SimulateFailureBucket>
}

export interface PolicyConfig {
  max_retries: number
  recurring_cooldown_hours: number
  non_recurring_cooldown_hours: number
  escalation_amount_threshold_inr: number
  incentive_target_pct: number
  margin_safety_buffer_pct: number
}

export interface CustomerSummary {
  customer_id: string
  customer_name: string
  transaction_count: number
  total_at_risk_inr: number
  total_recovered_inr: number
  escalated_count: number
  is_repeat: boolean
  has_live_activity: boolean
}

export interface CustomerDetail extends CustomerSummary {
  transactions: AuditRecord[]
}

export interface RunSnapshot {
  run_number: number
  timestamp: string
  client_mode: string
  total_transactions: number
  total_at_risk_inr: number
  total_recovered_inr: number
  recovery_rate_overall: number
  counts_by_outcome: Record<string, number>
}
