import { AnimatePresence, motion } from 'framer-motion'
import { useCallback, useEffect, useState } from 'react'
import './App.css'
import Background3D from './components/Background3D'
import Header from './components/Header'
import Sidebar, { type ViewKey } from './components/Sidebar'
import CommandPalette from './components/CommandPalette'
import KpiTiles from './components/KpiTiles'
import GaugeRing from './components/GaugeRing'
import RecoveryChart from './components/RecoveryChart'
import RecoveryTrend from './components/RecoveryTrend'
import AuditTable from './components/AuditTable'
import EscalatedCase from './components/EscalatedCase'
import GuardrailsView from './components/GuardrailsView'
import BaselineComparison from './components/BaselineComparison'
import MarginAnalysis from './components/MarginAnalysis'
import EscalationInbox from './components/EscalationInbox'
import LearningView from './components/LearningView'
import TransactionGalaxy from './components/TransactionGalaxy'
import ReasoningConsole from './components/ReasoningConsole'
import AskAgentPanel from './components/AskAgentPanel'
import OnePagerModal from './components/OnePagerModal'
import GuardrailSimulator from './components/GuardrailSimulator'
import CustomerView from './components/CustomerView'
import DecisionTreeModal from './components/DecisionTreeModal'
import { fetchAuditLog, fetchBanditState, fetchEscalations, fetchReport, runBatch } from './lib/api'
import { FAILURE_REASON_LABEL, OUTCOME_COLOR, OUTCOME_LABEL } from './lib/constants'
import { RULE_META, type RuleCode } from './lib/guardrails'
import type { PresetFilter } from './lib/filters'
import type { AuditRecord, BanditState, FailureReason, Report } from './lib/types'

const VIEW_META: Record<ViewKey, { title: string; subtitle: string }> = {
  overview: { title: 'Overview', subtitle: 'Detect → decide → execute → log → report, with guardrails.' },
  guardrails: { title: 'Guardrails & stopping rules', subtitle: 'Five hard rules the agent cannot cross — with live counts.' },
  inbox: { title: 'Escalation inbox', subtitle: 'A human acts here — approve, override, or resolve.' },
  learning: { title: 'Adaptive learning', subtitle: 'A bandit across message variants, improving run over run.' },
  galaxy: { title: 'Transaction galaxy', subtitle: 'Every transaction this run, mapped in 3D space.' },
  simulator: { title: 'Guardrail simulator', subtitle: 'Drag a threshold, see the projected impact instantly.' },
  customers: { title: 'Customers', subtitle: 'Every customer this run, grouped and cross-referenced.' },
  audit: { title: 'Audit trail', subtitle: 'One record per decision — every action names the rule that fired.' },
}

const LIVE_POLL_INTERVAL_MS = 3000

export default function App() {
  const [report, setReport] = useState<Report | null>(null)
  const [records, setRecords] = useState<AuditRecord[]>([])
  const [banditState, setBanditState] = useState<BanditState>({})
  const [escalationOpenCount, setEscalationOpenCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [liveMode, setLiveMode] = useState(false)
  const [consoleOpen, setConsoleOpen] = useState(false)
  const [onePagerOpen, setOnePagerOpen] = useState(false)
  const [decisionTreeRecord, setDecisionTreeRecord] = useState<AuditRecord | null>(null)

  const [view, setView] = useState<ViewKey>('overview')
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [auditQuery, setAuditQuery] = useState('')
  const [jumpTarget, setJumpTarget] = useState<string | null>(null)
  const [presetFilter, setPresetFilter] = useState<PresetFilter | null>(null)

  async function refreshSecondary() {
    try {
      const [bandit, escalations] = await Promise.all([fetchBanditState(), fetchEscalations()])
      setBanditState(bandit)
      setEscalationOpenCount(escalations.open_count)
    } catch {
      // secondary data -- don't block the primary dashboard on this failing
    }
  }

  async function loadAll() {
    setError(null)
    try {
      const [reportData, auditData] = await Promise.all([fetchReport(), fetchAuditLog()])
      setReport(reportData)
      setRecords(auditData.records)
      await refreshSecondary()
    } catch {
      setError('Could not reach the API. Is the backend running on :8000?')
    } finally {
      setLoading(false)
    }
  }

  async function handleRunBatch() {
    setRunning(true)
    setError(null)
    try {
      const fresh = await runBatch()
      setReport(fresh)
      const auditData = await fetchAuditLog()
      setRecords(auditData.records)
      await refreshSecondary()
    } catch {
      setError('Batch run failed. Check the backend logs.')
    } finally {
      setRunning(false)
    }
  }

  const handleJumpToTransaction = useCallback((txnId: string) => {
    setView('audit')
    setAuditQuery('')
    setPresetFilter(null)
    setJumpTarget(txnId)
  }, [])

  const handleSelectFailureReason = useCallback((reason: FailureReason) => {
    setView('audit')
    setAuditQuery('')
    setJumpTarget(null)
    setPresetFilter({ kind: 'failure_reason', value: reason, label: FAILURE_REASON_LABEL[reason] })
  }, [])

  const handleSelectRule = useCallback((code: RuleCode) => {
    setView('audit')
    setAuditQuery('')
    setJumpTarget(null)
    setPresetFilter({ kind: 'rule', code, label: `${code} — ${RULE_META[code].title}` })
  }, [])

  useEffect(() => {
    loadAll()
  }, [])

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setPaletteOpen((v) => !v)
      }
      if (e.key === 'Escape') setPaletteOpen(false)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [])

  // Live feed: while enabled, poll the same endpoints a real dashboard
  // would poll to reflect webhook-ingested transactions arriving in real
  // time (see backend/scripts/simulate_webhooks.py) -- proves the live
  // ingestion path end-to-end, not just the batch path.
  useEffect(() => {
    if (!liveMode) return
    const interval = setInterval(async () => {
      try {
        const [reportData, auditData] = await Promise.all([fetchReport(), fetchAuditLog()])
        setReport(reportData)
        setRecords(auditData.records)
      } catch {
        // transient poll failure -- try again next tick
      }
    }, LIVE_POLL_INTERVAL_MS)
    return () => clearInterval(interval)
  }, [liveMode])

  const meta = VIEW_META[view]

  return (
    <div className="app-shell">
      <Background3D />
      <Sidebar active={view} onChange={setView} onOpenPalette={() => setPaletteOpen(true)} inboxOpenCount={escalationOpenCount} />

      <div className="app-main">
        <div className="app-content">
          <Header
            title={meta.title}
            subtitle={meta.subtitle}
            clientMode={report?.client_mode}
            onRunBatch={handleRunBatch}
            running={running}
            onOpenPalette={() => setPaletteOpen(true)}
            liveMode={liveMode}
            onToggleLiveMode={() => setLiveMode((v) => !v)}
            consoleOpen={consoleOpen}
            onToggleConsole={() => setConsoleOpen((v) => !v)}
            onOpenOnePager={() => setOnePagerOpen(true)}
          />

          <AnimatePresence mode="wait">
            {loading ? (
              <motion.div key="loading" className="loading-state" exit={{ opacity: 0 }}>
                <span className="spinner large" />
                <p>Running the recovery engine…</p>
              </motion.div>
            ) : error ? (
              <motion.div key="error" className="error-state" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                <p>{error}</p>
                <button className="run-btn" onClick={loadAll}>
                  Retry
                </button>
              </motion.div>
            ) : report ? (
              <AnimatePresence mode="wait">
                {view === 'overview' && (
                  <motion.main
                    key="overview"
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -8 }}
                    transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
                  >
                    <div className="hero-row">
                      <div className="gauge-card glass">
                        <GaugeRing rate={report.recovery_rate_overall} />
                      </div>
                      <KpiTiles report={report} />
                    </div>

                    <div className="outcome-strip">
                      {Object.entries(report.counts_by_outcome).map(([outcome, count]) => (
                        <div key={outcome} className="outcome-chip">
                          <span
                            className="outcome-chip-dot"
                            style={{ background: OUTCOME_COLOR[outcome as keyof typeof OUTCOME_COLOR] }}
                          />
                          {OUTCOME_LABEL[outcome as keyof typeof OUTCOME_LABEL] ?? outcome}
                          <span className="mono">{count}</span>
                        </div>
                      ))}
                    </div>

                    <div className="grid-2col">
                      <RecoveryChart report={report} onSelectReason={handleSelectFailureReason} />
                      <EscalatedCase record={report.escalated_example} />
                    </div>

                    <div className="grid-2col">
                      <BaselineComparison data={report.baseline_comparison} />
                      <MarginAnalysis data={report.margin_analysis} />
                    </div>

                    <RecoveryTrend records={records} />

                    <button
                      className="view-audit-cta"
                      onClick={() => {
                        setPresetFilter(null)
                        setJumpTarget(null)
                        setView('audit')
                      }}
                    >
                      View the full audit trail
                      <span aria-hidden>→</span>
                    </button>
                  </motion.main>
                )}

                {view === 'guardrails' && (
                  <motion.main
                    key="guardrails"
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -8 }}
                    transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
                  >
                    <GuardrailsView records={records} onSelectRule={handleSelectRule} />
                  </motion.main>
                )}

                {view === 'inbox' && (
                  <motion.main
                    key="inbox"
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -8 }}
                    transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
                  >
                    <EscalationInbox onOpenCountChange={setEscalationOpenCount} />
                  </motion.main>
                )}

                {view === 'learning' && (
                  <motion.main
                    key="learning"
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -8 }}
                    transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
                  >
                    <LearningView banditState={banditState} />
                  </motion.main>
                )}

                {view === 'galaxy' && (
                  <motion.main
                    key="galaxy"
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -8 }}
                    transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
                  >
                    <TransactionGalaxy records={records} />
                  </motion.main>
                )}

                {view === 'simulator' && (
                  <motion.main
                    key="simulator"
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -8 }}
                    transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
                  >
                    <GuardrailSimulator report={report} />
                  </motion.main>
                )}

                {view === 'customers' && (
                  <motion.main
                    key="customers"
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -8 }}
                    transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
                  >
                    <CustomerView />
                  </motion.main>
                )}

                {view === 'audit' && (
                  <motion.main
                    key="audit"
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -8 }}
                    transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
                  >
                    <AuditTable
                      records={records}
                      query={auditQuery}
                      onQueryChange={setAuditQuery}
                      jumpTarget={jumpTarget}
                      presetFilter={presetFilter}
                      onClearPreset={() => setPresetFilter(null)}
                      onViewDecisionTree={setDecisionTreeRecord}
                    />
                  </motion.main>
                )}
              </AnimatePresence>
            ) : null}
          </AnimatePresence>

          {!loading && !error && (
            <footer className="app-footer">
              Batch of {report?.total_transactions ?? 0} synthetic transactions, seeded and reproducible. Audit log
              is the single source of truth for every number above.
            </footer>
          )}
        </div>
      </div>

      <CommandPalette
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
        records={records}
        onNavigate={setView}
        onJumpToTransaction={handleJumpToTransaction}
      />

      <ReasoningConsole records={records} open={consoleOpen} onClose={() => setConsoleOpen(false)} liveMode={liveMode} />
      <AskAgentPanel />
      <OnePagerModal open={onePagerOpen} onClose={() => setOnePagerOpen(false)} />
      <DecisionTreeModal record={decisionTreeRecord} onClose={() => setDecisionTreeRecord(null)} />
    </div>
  )
}
