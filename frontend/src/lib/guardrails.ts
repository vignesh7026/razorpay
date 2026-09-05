import type { AuditRecord } from './types'

export type RuleCode = 'SR1' | 'SR2' | 'SR3' | 'SR4' | 'SR5' | 'SR6'

export const RULE_CODES: RuleCode[] = ['SR1', 'SR2', 'SR3', 'SR4', 'SR5', 'SR6']

export const RULE_MATCHERS: Record<RuleCode, (r: AuditRecord) => boolean> = {
  SR1: (r) => r.rule_fired === 'max_retries_exceeded',
  SR2: (r) => r.stopping_rule_hit === 'cooldown_active',
  SR3: (r) => r.rule_fired === 'mandate_expired_requires_reauth',
  SR4: (r) => r.incentive_pct > 0,
  SR5: (r) => r.rule_fired.startsWith('high_value_prior_failure_escalation'),
  SR6: (r) => r.stopping_rule_hit === 'suspected_fraud',
}

export const RULE_META: Record<RuleCode, { title: string; description: string; color: string }> = {
  SR1: {
    title: 'Max retries',
    description: 'No transaction is auto-retried more than 3 times. A 4th attempt is never automatic — it escalates.',
    color: 'var(--critical)',
  },
  SR2: {
    title: 'Cooldown window',
    description:
      'Recurring / insufficient-funds retries respect a cooldown since the last attempt. Inside it, the outcome is pending_retry — never a forced attempt.',
    color: 'var(--warning)',
  },
  SR3: {
    title: 'Mandate expiry never auto-retries',
    description: 'mandate_expired always routes to re-authorization, never a blind retry — and always escalates to a human.',
    color: 'var(--series-mandate_expired)',
  },
  SR4: {
    title: 'Margin floor',
    description: "Any incentive offered on a recovery nudge is capped so it can never cut into the product's margin floor.",
    color: 'var(--good)',
  },
  SR5: {
    title: 'Mandatory human escalation',
    description:
      'Amount above ₹5,000 combined with a prior failed attempt mandatorily loops in a human — a first-class logged outcome, never a silent drop.',
    color: 'var(--accent-2)',
  },
  SR6: {
    title: 'Card-testing pattern guardrail',
    description:
      'Many distinct customers hitting card_declined at low amounts in a tight window is blocked and escalated outright — a narrow pattern check, not a fraud model.',
    color: 'var(--series-otp_timeout)',
  },
}

export function recordsForRule(records: AuditRecord[], code: RuleCode): AuditRecord[] {
  return records.filter(RULE_MATCHERS[code])
}

export function metricForRule(records: AuditRecord[], code: RuleCode): string {
  const matches = recordsForRule(records, code)
  switch (code) {
    case 'SR1':
      return `${matches.length} transaction${matches.length === 1 ? '' : 's'} hit the ceiling`
    case 'SR2':
      return `${matches.length} held in cooldown this run`
    case 'SR3':
      return `${matches.length} expired mandate${matches.length === 1 ? '' : 's'} re-routed`
    case 'SR4': {
      const avg = matches.length ? matches.reduce((s, r) => s + r.incentive_pct, 0) / matches.length : 0
      return `avg ${(avg * 100).toFixed(1)}% offered, always margin-safe`
    }
    case 'SR5':
      return `${matches.length} high-value repeat failure${matches.length === 1 ? '' : 's'} escalated`
    case 'SR6':
      return `${matches.length} transaction${matches.length === 1 ? '' : 's'} blocked as suspected card testing`
  }
}
