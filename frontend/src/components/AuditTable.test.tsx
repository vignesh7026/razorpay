import { render, screen, waitForElementToBeRemoved } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ComponentProps } from 'react'
import { describe, expect, it, vi } from 'vitest'
import AuditTable from './AuditTable'
import { makeRecord } from '../test/fixtures'

const records = [
  makeRecord({ transaction_id: 'txn_0001', failure_reason: 'card_declined', outcome: 'recovered', customer_name: 'Arjun' }),
  makeRecord({ transaction_id: 'txn_0002', failure_reason: 'gateway_timeout', outcome: 'escalated', customer_name: 'Priya' }),
  makeRecord({ transaction_id: 'txn_0003', failure_reason: 'card_declined', outcome: 'failed', customer_name: 'Rohan' }),
]

function renderTable(overrides: Partial<ComponentProps<typeof AuditTable>> = {}) {
  const onQueryChange = vi.fn()
  render(
    <AuditTable records={records} query="" onQueryChange={onQueryChange} {...overrides} />
  )
  return { onQueryChange }
}

describe('AuditTable', () => {
  it('renders every record with no filter applied', () => {
    renderTable()
    expect(screen.getByText('txn_0001')).toBeInTheDocument()
    expect(screen.getByText('txn_0002')).toBeInTheDocument()
    expect(screen.getByText('txn_0003')).toBeInTheDocument()
  })

  it('filters by outcome when a filter chip is clicked', async () => {
    const user = userEvent.setup()
    renderTable()
    await user.click(screen.getByRole('button', { name: /escalated/i }))
    expect(screen.getByText('txn_0002')).toBeInTheDocument()
    // filtered-out rows exit via a framer-motion animation, so they
    // linger in the DOM briefly rather than disappearing synchronously
    await waitForElementToBeRemoved(() => screen.queryByText('txn_0001'))
  })

  it('applies a preset failure_reason filter and shows the active chip', () => {
    renderTable({
      presetFilter: { kind: 'failure_reason', value: 'gateway_timeout', label: 'Gateway timeout' },
    })
    expect(screen.getByText('txn_0002')).toBeInTheDocument()
    expect(screen.queryByText('txn_0001')).not.toBeInTheDocument()
    expect(screen.getByText(/Filtered by Gateway timeout/i)).toBeInTheDocument()
  })

  it('calls onClearPreset when the preset chip is dismissed', async () => {
    const user = userEvent.setup()
    const onClearPreset = vi.fn()
    renderTable({
      presetFilter: { kind: 'failure_reason', value: 'gateway_timeout', label: 'Gateway timeout' },
      onClearPreset,
    })
    await user.click(screen.getByRole('button', { name: /clear filter/i }))
    expect(onClearPreset).toHaveBeenCalledOnce()
  })

  it('combines the outcome filter and preset filter with AND semantics', async () => {
    const user = userEvent.setup()
    renderTable({
      presetFilter: { kind: 'failure_reason', value: 'card_declined', label: 'Card declined' },
    })
    // txn_0001 (card_declined, recovered) and txn_0003 (card_declined, failed)
    // both match the preset; narrowing to "Failed" should leave only txn_0003.
    await user.click(screen.getByRole('button', { name: /^failed/i }))
    expect(screen.getByText('txn_0003')).toBeInTheDocument()
    await waitForElementToBeRemoved(() => screen.queryByText('txn_0001'))
  })

  it('expands a row to show its rule notes on click', async () => {
    const user = userEvent.setup()
    renderTable()
    await user.click(screen.getByText('txn_0001'))
    expect(screen.getByText(/Why:/i)).toBeInTheDocument()
  })
})
