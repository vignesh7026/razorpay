import { animate, stagger } from 'animejs'
import { useEffect, useRef } from 'react'
import TiltCard from './TiltCard'
import { formatInr } from '../lib/constants'
import { RULE_CODES, RULE_META, metricForRule, recordsForRule, type RuleCode } from '../lib/guardrails'
import type { AuditRecord } from '../lib/types'

interface GuardrailsViewProps {
  records: AuditRecord[]
  onSelectRule: (code: RuleCode) => void
}

const iconProps = { width: 22, height: 22, viewBox: '0 0 24 24', fill: 'none' as const }

function IconStack() {
  return (
    <svg {...iconProps}>
      <path d="M12 3 3 8l9 5 9-5-9-5Z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
      <path d="m3 12 9 5 9-5" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
      <path d="m3 16 9 5 9-5" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
    </svg>
  )
}
function IconClock() {
  return (
    <svg {...iconProps}>
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.6" />
      <path d="M12 7v5l3.5 2" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}
function IconShieldOff() {
  return (
    <svg {...iconProps}>
      <path d="M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6l7-3Z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
      <path d="M9 12l3 3 3-5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}
function IconScale() {
  return (
    <svg {...iconProps}>
      <path d="M12 3v18M7 21h10" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      <path d="M4 7h6M14 7h6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      <path d="M4 7 2 12a3 3 0 0 0 4 0L4 7ZM20 7l-2 5a3 3 0 0 0 4 0l-2-5Z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
    </svg>
  )
}
function IconUser() {
  return (
    <svg {...iconProps}>
      <circle cx="12" cy="8" r="3.4" stroke="currentColor" strokeWidth="1.6" />
      <path d="M5 20c1.2-4 4-6 7-6s5.8 2 7 6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  )
}

function IconFingerprint() {
  return (
    <svg {...iconProps}>
      <path
        d="M12 4c4.4 0 8 3.6 8 8v3M4 12c0-2.4 1-4.5 2.6-6M12 4C7.6 4 4 7.6 4 12M8 20c-.6-1.5-1-3.2-1-5v-3a5 5 0 0 1 10 0v3c0 2.5-.5 4.6-1.3 6.3M12 9a3 3 0 0 1 3 3v3c0 1.7-.3 3.3-.9 4.7"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

const RULE_ICONS: Record<RuleCode, React.ReactNode> = {
  SR1: <IconStack />,
  SR2: <IconClock />,
  SR3: <IconShieldOff />,
  SR4: <IconScale />,
  SR5: <IconUser />,
  SR6: <IconFingerprint />,
}

export default function GuardrailsView({ records, onSelectRule }: GuardrailsViewProps) {
  const gridRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const cards = gridRef.current?.querySelectorAll('.rule-card')
    if (!cards || cards.length === 0) return
    animate(cards, {
      opacity: [0, 1],
      translateY: [28, 0],
      scale: [0.95, 1],
      delay: stagger(90, { start: 80 }),
      duration: 700,
      ease: 'outExpo',
    })
  }, [])

  return (
    <div className="guardrails-view">
      <div className="view-intro">
        <p>
          Every automated action traces back to one of these five rules — this is what makes the audit log explain
          "why," not just "what." Counts below are live, pulled straight from the current run's audit log. Click a
          card to see exactly which transactions it fired on.
        </p>
      </div>

      <div className="rules-grid" ref={gridRef}>
        {RULE_CODES.map((code) => {
          const meta = RULE_META[code]
          const example = recordsForRule(records, code)[0]
          return (
            <TiltCard
              key={code}
              className="rule-card glass clickable"
              maxTilt={6}
              onClick={() => onSelectRule(code)}
            >
              <div className="rule-card-head">
                <div
                  className="rule-icon"
                  style={{ color: meta.color, background: `color-mix(in srgb, ${meta.color} 16%, transparent)` }}
                >
                  {RULE_ICONS[code]}
                </div>
                <span className="rule-code">{code}</span>
              </div>
              <h4>{meta.title}</h4>
              <p className="rule-description">{meta.description}</p>
              <div className="rule-metric" style={{ color: meta.color }}>
                {metricForRule(records, code)}
              </div>
              {example && (
                <div className="rule-example">
                  <span className="rule-example-label">Example from this run</span>
                  <span className="mono">{example.transaction_id}</span>
                  <span className="muted"> · {example.customer_name} · {formatInr(example.amount_inr)}</span>
                </div>
              )}
            </TiltCard>
          )
        })}
      </div>
    </div>
  )
}
