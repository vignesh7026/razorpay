import type { FailureReason, Outcome } from './types'

export const FAILURE_REASON_ORDER: FailureReason[] = [
  'card_declined',
  'checkout_abandoned',
  'insufficient_funds',
  'gateway_timeout',
  'otp_timeout',
  'mandate_insufficient_funds',
  'mandate_expired',
]

export const FAILURE_REASON_LABEL: Record<FailureReason, string> = {
  card_declined: 'Card declined',
  checkout_abandoned: 'Checkout abandoned',
  insufficient_funds: 'Insufficient funds',
  gateway_timeout: 'Gateway timeout',
  otp_timeout: 'OTP timeout',
  mandate_insufficient_funds: 'Mandate — insufficient funds',
  mandate_expired: 'Mandate expired',
}

export const FAILURE_REASON_INTERVENTION: Record<FailureReason, string> = {
  card_declined: 'Resend link — alternate method',
  checkout_abandoned: 'Link resend + bounded incentive',
  insufficient_funds: 'Delayed retry after cooldown',
  gateway_timeout: 'Single immediate retry',
  otp_timeout: 'Payment-link resend',
  mandate_insufficient_funds: 'Capped retry after cooldown',
  mandate_expired: 'Re-authorization request',
}

// fixed order, dataviz-skill validated dark-mode categorical steps
export const FAILURE_REASON_COLOR: Record<FailureReason, string> = {
  card_declined: 'var(--series-card_declined)',
  checkout_abandoned: 'var(--series-checkout_abandoned)',
  insufficient_funds: 'var(--series-insufficient_funds)',
  gateway_timeout: 'var(--series-gateway_timeout)',
  otp_timeout: 'var(--series-otp_timeout)',
  mandate_insufficient_funds: 'var(--series-mandate_insufficient_funds)',
  mandate_expired: 'var(--series-mandate_expired)',
}

export const OUTCOME_LABEL: Record<Outcome, string> = {
  recovered: 'Recovered',
  escalated: 'Escalated',
  pending_retry: 'Pending retry',
  failed: 'Failed',
}

export const OUTCOME_COLOR: Record<Outcome, string> = {
  recovered: 'var(--good)',
  escalated: 'var(--critical)',
  pending_retry: 'var(--warning)',
  failed: 'var(--text-muted)',
}

// Raw hex twins of the CSS custom properties above -- WebGL materials
// (Three.js `color` props) can't resolve `var(--x)`, so anything rendered
// in the 3D galaxy reads from these instead of the CSS variable maps.
export const FAILURE_REASON_HEX: Record<FailureReason, string> = {
  card_declined: '#3987e5',
  checkout_abandoned: '#d95926',
  insufficient_funds: '#199e70',
  gateway_timeout: '#c98500',
  otp_timeout: '#d55181',
  mandate_insufficient_funds: '#4caf3f',
  mandate_expired: '#9085e9',
}

export const OUTCOME_HEX: Record<Outcome, string> = {
  recovered: '#0ca30c',
  escalated: '#e66767',
  pending_retry: '#fab219',
  failed: '#7d8089',
}

export function formatInr(amount: number): string {
  return `₹${Math.round(amount).toLocaleString('en-IN')}`
}

export function formatPct(rate: number, digits = 1): string {
  return `${(rate * 100).toFixed(digits)}%`
}
