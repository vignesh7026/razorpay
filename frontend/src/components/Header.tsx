import { motion } from 'framer-motion'
import ScrambleText from './ScrambleText'

interface HeaderProps {
  title: string
  subtitle: string
  clientMode?: string
  onRunBatch: () => void
  running: boolean
  onOpenPalette: () => void
  liveMode: boolean
  onToggleLiveMode: () => void
  consoleOpen: boolean
  onToggleConsole: () => void
  onOpenOnePager: () => void
}

export default function Header({
  title,
  subtitle,
  clientMode,
  onRunBatch,
  running,
  onOpenPalette,
  liveMode,
  onToggleLiveMode,
  consoleOpen,
  onToggleConsole,
  onOpenOnePager,
}: HeaderProps) {
  const isSimulated = clientMode !== 'RealRazorpayClient'

  return (
    <motion.header
      className="app-header"
      initial={{ opacity: 0, y: -16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] as const }}
    >
      <div className="app-header-title">
        <h1>
          <ScrambleText text={title} as="span" triggerKey={title} chars="uppercase" />
        </h1>
        <p>{subtitle}</p>
      </div>

      <div className="app-header-actions">
        <button className="palette-trigger mobile-only" onClick={onOpenPalette}>
          <span>Search…</span>
          <kbd>⌘K</kbd>
        </button>
        <motion.button
          className={`live-toggle ${liveMode ? 'active' : ''}`}
          onClick={onToggleLiveMode}
          whileHover={{ scale: 1.03 }}
          whileTap={{ scale: 0.97 }}
          title="Poll for live webhook-ingested transactions every 3s"
        >
          <span className="live-toggle-dot" />
          Live feed {liveMode ? 'on' : 'off'}
        </motion.button>
        <span className={`mode-badge ${isSimulated ? 'sim' : 'real'}`}>
          <span className="mode-dot" />
          {isSimulated ? 'Simulated execution' : 'Live Razorpay test-mode'}
        </span>
        <motion.button
          className={`console-toggle ${consoleOpen ? 'active' : ''}`}
          onClick={onToggleConsole}
          whileHover={{ scale: 1.03 }}
          whileTap={{ scale: 0.97 }}
          title="Toggle the agent reasoning console"
        >
          <span>&gt;_</span> Console
        </motion.button>
        <motion.button
          className="console-toggle"
          onClick={onOpenOnePager}
          whileHover={{ scale: 1.03 }}
          whileTap={{ scale: 0.97 }}
          title="Export a one-pager summary"
        >
          Export
        </motion.button>
        <motion.button
          className="run-btn"
          onClick={onRunBatch}
          disabled={running}
          whileHover={running ? undefined : { scale: 1.03, y: -1 }}
          whileTap={running ? undefined : { scale: 0.97 }}
        >
          {running ? (
            <>
              <span className="spinner" /> Running…
            </>
          ) : (
            'Re-run batch'
          )}
        </motion.button>
      </div>
    </motion.header>
  )
}
