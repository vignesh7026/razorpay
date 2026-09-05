import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useRef, useState } from 'react'
import { FAILURE_REASON_LABEL, OUTCOME_COLOR, OUTCOME_LABEL } from '../lib/constants'
import type { AuditRecord } from '../lib/types'

interface ReasoningConsoleProps {
  records: AuditRecord[]
  open: boolean
  onClose: () => void
  liveMode: boolean
}

interface ConsoleLine {
  key: string
  record: AuditRecord
}

function timeOf(ts: string): string {
  try {
    return new Date(ts).toLocaleTimeString('en-IN', { hour12: false })
  } catch {
    return ts
  }
}

export default function ReasoningConsole({ records, open, onClose, liveMode }: ReasoningConsoleProps) {
  const [lines, setLines] = useState<ConsoleLine[]>([])
  const seenIds = useRef<Set<string>>(new Set())
  const bodyRef = useRef<HTMLDivElement>(null)
  const initialized = useRef(false)

  // First mount: mark every already-known transaction as "seen" without
  // printing it -- the console starts empty and only auto-prints genuinely
  // new arrivals (live webhook events) or an explicit replay.
  useEffect(() => {
    if (!initialized.current) {
      records.forEach((r) => seenIds.current.add(r.transaction_id))
      initialized.current = true
      return
    }
    if (!liveMode) return
    const fresh = records.filter((r) => !seenIds.current.has(r.transaction_id))
    if (fresh.length === 0) return
    fresh.forEach((r) => seenIds.current.add(r.transaction_id))
    setLines((prev) => [...prev, ...fresh.map((r) => ({ key: `${r.transaction_id}-${Date.now()}`, record: r }))])
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [records, liveMode])

  useEffect(() => {
    bodyRef.current?.scrollTo({ top: bodyRef.current.scrollHeight, behavior: 'smooth' })
  }, [lines])

  function replay() {
    const sorted = [...records].sort((a, b) => a.timestamp.localeCompare(b.timestamp)).slice(0, 200)
    setLines([])
    sorted.forEach((r, i) => {
      setTimeout(() => {
        setLines((prev) => [...prev, { key: `${r.transaction_id}-replay-${i}`, record: r }])
      }, i * 45)
    })
  }

  function clear() {
    setLines([])
  }

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="reasoning-console"
          initial={{ y: '100%' }}
          animate={{ y: 0 }}
          exit={{ y: '100%' }}
          transition={{ type: 'spring', stiffness: 320, damping: 34 }}
        >
          <div className="reasoning-console-head">
            <div className="reasoning-console-title">
              <span className="reasoning-console-dot" />
              agent-reasoning.log
              {liveMode && <span className="reasoning-console-live">LIVE</span>}
            </div>
            <div className="reasoning-console-actions">
              <button onClick={replay}>Replay batch</button>
              <button onClick={clear}>Clear</button>
              <button onClick={onClose} aria-label="Close console">
                ×
              </button>
            </div>
          </div>
          <div className="reasoning-console-body" ref={bodyRef}>
            {lines.length === 0 && (
              <div className="reasoning-console-empty">
                Empty. Click "Replay batch" to trace the last run's reasoning, or turn on Live feed and run{' '}
                <code>scripts/simulate_webhooks.py</code> to watch decisions arrive in real time.
              </div>
            )}
            {lines.map((line) => {
              const r = line.record
              const color = OUTCOME_COLOR[r.outcome]
              return (
                <motion.div
                  key={line.key}
                  className="reasoning-line"
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.25 }}
                >
                  <span className="reasoning-ts">[{timeOf(r.timestamp)}]</span>
                  <span className="reasoning-txn">{r.transaction_id}</span>
                  <span className="reasoning-arrow">
                    {FAILURE_REASON_LABEL[r.failure_reason]} → <span className="reasoning-rule">{r.rule_fired}</span> →{' '}
                    {r.intervention_chosen}
                  </span>
                  <span className="reasoning-outcome" style={{ color }}>
                    [{OUTCOME_LABEL[r.outcome].toUpperCase()}]
                  </span>
                  {r.source === 'webhook' && <span className="reasoning-live-tag">webhook</span>}
                </motion.div>
              )
            })}
            <div className="reasoning-cursor">
              <span className="reasoning-cursor-blink">▊</span>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
