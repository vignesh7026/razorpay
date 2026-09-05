import { motion } from 'framer-motion'
import type { ReactNode } from 'react'

export type ViewKey = 'overview' | 'guardrails' | 'inbox' | 'learning' | 'galaxy' | 'simulator' | 'customers' | 'audit'

interface NavItem {
  key: ViewKey
  label: string
  icon: ReactNode
  hint: string
}

interface SidebarProps {
  active: ViewKey
  onChange: (view: ViewKey) => void
  onOpenPalette: () => void
  inboxOpenCount?: number
}

const iconProps = { width: 18, height: 18, viewBox: '0 0 24 24', fill: 'none' as const }

function IconGrid() {
  return (
    <svg {...iconProps}>
      <rect x="3.5" y="3.5" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.6" />
      <rect x="13.5" y="3.5" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.6" />
      <rect x="3.5" y="13.5" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.6" />
      <rect x="13.5" y="13.5" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.6" />
    </svg>
  )
}
function IconShield() {
  return (
    <svg {...iconProps}>
      <path d="M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6l7-3Z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
    </svg>
  )
}
function IconList() {
  return (
    <svg {...iconProps}>
      <path d="M8 6h13M8 12h13M8 18h13" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      <circle cx="3.5" cy="6" r="1.4" fill="currentColor" />
      <circle cx="3.5" cy="12" r="1.4" fill="currentColor" />
      <circle cx="3.5" cy="18" r="1.4" fill="currentColor" />
    </svg>
  )
}
function IconInbox() {
  return (
    <svg {...iconProps}>
      <path d="M3 12h5l2 3h4l2-3h5" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
      <path d="M5 5h14l2 7v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-7l2-7Z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
    </svg>
  )
}
function IconBrain() {
  return (
    <svg {...iconProps}>
      <path
        d="M9 4a3 3 0 0 0-3 3v.5A2.5 2.5 0 0 0 4.5 10 2.5 2.5 0 0 0 6 14.3V16a3 3 0 0 0 3 3M9 4a3 3 0 0 1 3 3v10a3 3 0 0 1-3 3M15 4a3 3 0 0 1 3 3v.5a2.5 2.5 0 0 1 1.5 2.5A2.5 2.5 0 0 1 18 14.3V16a3 3 0 0 1-3 3M15 4a3 3 0 0 0-3 3v10a3 3 0 0 0 3 3"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function IconGalaxy() {
  return (
    <svg {...iconProps}>
      <circle cx="12" cy="12" r="2" fill="currentColor" />
      <ellipse cx="12" cy="12" rx="9" ry="3.5" stroke="currentColor" strokeWidth="1.4" transform="rotate(-20 12 12)" />
      <ellipse cx="12" cy="12" rx="9" ry="3.5" stroke="currentColor" strokeWidth="1.4" transform="rotate(20 12 12)" />
    </svg>
  )
}

function IconSliders() {
  return (
    <svg {...iconProps}>
      <path d="M4 6h10M17 6h3M4 12h3M9 12h11M4 18h13M20 18h0" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      <circle cx="14" cy="6" r="2" fill="currentColor" />
      <circle cx="6" cy="12" r="2" fill="currentColor" />
      <circle cx="16" cy="18" r="2" fill="currentColor" />
    </svg>
  )
}
function IconUsers() {
  return (
    <svg {...iconProps}>
      <circle cx="9" cy="8" r="3" stroke="currentColor" strokeWidth="1.6" />
      <path d="M3 20c1-3.5 3.5-5.5 6-5.5s5 2 6 5.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      <path d="M16 4.5a3 3 0 0 1 0 6M20 20c-.7-2.5-2-4.2-3.5-5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  )
}

const NAV_ITEMS: NavItem[] = [
  { key: 'overview', label: 'Overview', icon: <IconGrid />, hint: 'KPIs & recovery rate' },
  { key: 'guardrails', label: 'Guardrails', icon: <IconShield />, hint: 'Stopping rules, live' },
  { key: 'inbox', label: 'Inbox', icon: <IconInbox />, hint: 'Human escalation queue' },
  { key: 'learning', label: 'Learning', icon: <IconBrain />, hint: 'Adaptive bandit' },
  { key: 'galaxy', label: 'Galaxy', icon: <IconGalaxy />, hint: '3D transaction map' },
  { key: 'simulator', label: 'Simulator', icon: <IconSliders />, hint: 'What-if policy sliders' },
  { key: 'customers', label: 'Customers', icon: <IconUsers />, hint: 'Customer 360' },
  { key: 'audit', label: 'Audit trail', icon: <IconList />, hint: 'Every decision, logged' },
]

export default function Sidebar({ active, onChange, onOpenPalette, inboxOpenCount }: SidebarProps) {
  return (
    <motion.nav
      className="sidebar"
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] as const }}
    >
      <div className="sidebar-brand">
        <div className="app-logo">RR</div>
        <div>
          <div className="sidebar-brand-title">Revenue Recovery</div>
          <div className="sidebar-brand-sub">Agent console</div>
        </div>
      </div>

      <motion.button
        className="palette-trigger"
        onClick={onOpenPalette}
        whileHover={{ scale: 1.02 }}
        whileTap={{ scale: 0.98 }}
      >
        <span>Search…</span>
        <kbd>⌘K</kbd>
      </motion.button>

      <div className="sidebar-nav">
        {NAV_ITEMS.map((item) => {
          const isActive = item.key === active
          return (
            <motion.button
              key={item.key}
              className={`sidebar-nav-item ${isActive ? 'active' : ''}`}
              onClick={() => onChange(item.key)}
              whileHover={{ x: 2 }}
              whileTap={{ scale: 0.98 }}
            >
              {isActive && (
                <motion.span
                  layoutId="sidebar-active"
                  className="sidebar-nav-highlight"
                  transition={{ type: 'spring', stiffness: 400, damping: 32 }}
                />
              )}
              <span className="sidebar-nav-icon">{item.icon}</span>
              <span className="sidebar-nav-text">
                <span className="sidebar-nav-label">{item.label}</span>
                <span className="sidebar-nav-hint">{item.hint}</span>
              </span>
              {item.key === 'inbox' && !!inboxOpenCount && (
                <span className="sidebar-nav-badge">{inboxOpenCount}</span>
              )}
            </motion.button>
          )
        })}
      </div>

      <div className="sidebar-footer">
        <p>Detect → decide → execute → log → report, with guardrails.</p>
      </div>
    </motion.nav>
  )
}
