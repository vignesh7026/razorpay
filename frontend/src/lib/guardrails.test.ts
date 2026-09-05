import { describe, expect, it } from 'vitest'
import { RULE_MATCHERS, recordsForRule } from './guardrails'
import { makeRecord } from '../test/fixtures'

describe('RULE_MATCHERS', () => {
  it('SR1 matches only max_retries_exceeded rule_fired', () => {
    const hit = makeRecord({ rule_fired: 'max_retries_exceeded' })
    const miss = makeRecord({ rule_fired: 'gateway_timeout_immediate_retry' })
    expect(RULE_MATCHERS.SR1(hit)).toBe(true)
    expect(RULE_MATCHERS.SR1(miss)).toBe(false)
  })

  it('SR2 matches only cooldown_active stopping_rule_hit', () => {
    const hit = makeRecord({ stopping_rule_hit: 'cooldown_active' })
    const miss = makeRecord({ stopping_rule_hit: 'max_retries' })
    expect(RULE_MATCHERS.SR2(hit)).toBe(true)
    expect(RULE_MATCHERS.SR2(miss)).toBe(false)
  })

  it('SR3 matches only mandate_expired_requires_reauth', () => {
    const hit = makeRecord({ rule_fired: 'mandate_expired_requires_reauth' })
    const miss = makeRecord({ rule_fired: 'mandate_insufficient_funds_capped_retry' })
    expect(RULE_MATCHERS.SR3(hit)).toBe(true)
    expect(RULE_MATCHERS.SR3(miss)).toBe(false)
  })

  it('SR4 matches any record with a positive incentive_pct', () => {
    const hit = makeRecord({ incentive_pct: 0.1 })
    const miss = makeRecord({ incentive_pct: 0 })
    expect(RULE_MATCHERS.SR4(hit)).toBe(true)
    expect(RULE_MATCHERS.SR4(miss)).toBe(false)
  })

  it('SR5 matches rule_fired strings prefixed with the escalation marker, including compound rules', () => {
    const hit = makeRecord({ rule_fired: 'high_value_prior_failure_escalation+card_declined_alt_method_link' })
    const miss = makeRecord({ rule_fired: 'card_declined_alt_method_link' })
    expect(RULE_MATCHERS.SR5(hit)).toBe(true)
    expect(RULE_MATCHERS.SR5(miss)).toBe(false)
  })
})

describe('recordsForRule', () => {
  it('filters a mixed record set down to only the matching rule', () => {
    const records = [
      makeRecord({ transaction_id: 'a', rule_fired: 'max_retries_exceeded' }),
      makeRecord({ transaction_id: 'b', rule_fired: 'otp_timeout_link_resend' }),
      makeRecord({ transaction_id: 'c', rule_fired: 'max_retries_exceeded' }),
    ]
    const matches = recordsForRule(records, 'SR1')
    expect(matches.map((r) => r.transaction_id)).toEqual(['a', 'c'])
  })
})
