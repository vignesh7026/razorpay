import type { AuditRecord } from '../lib/types'

export function makeRecord(overrides: Partial<AuditRecord> = {}): AuditRecord {
  return {
    transaction_id: 'txn_test',
    failure_reason: 'card_declined',
    intervention_chosen: 'create_payment_link',
    rule_fired: 'card_declined_alt_method_link',
    outcome: 'recovered',
    stopping_rule_hit: false,
    escalated_to_human: false,
    amount_inr: 1000,
    timestamp: '2026-08-27T12:00:00Z',
    recovered_inr: 1000,
    incentive_pct: 0,
    product_margin_pct: 0.2,
    prior_retry_count: 0,
    is_recurring: false,
    customer_id: 'cust_test',
    customer_name: 'Test Customer',
    product_name: 'Test Product',
    rule_notes: '',
    execution: null,
    ...overrides,
  }
}
