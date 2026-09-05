import type { FailureReason } from './types'
import type { RuleCode } from './guardrails'

export type PresetFilter =
  | { kind: 'failure_reason'; value: FailureReason; label: string }
  | { kind: 'rule'; code: RuleCode; label: string }
