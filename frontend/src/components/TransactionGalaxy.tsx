import { Canvas, useFrame } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'
import { useMemo, useRef, useState } from 'react'
import * as THREE from 'three'
import {
  FAILURE_REASON_HEX,
  FAILURE_REASON_LABEL,
  FAILURE_REASON_ORDER,
  OUTCOME_HEX,
  OUTCOME_LABEL,
  formatInr,
} from '../lib/constants'
import type { AuditRecord, FailureReason, Outcome } from '../lib/types'

const RING_RADIUS = 5.6
const CLUSTER_SPREAD = 1.9

function hashString(s: string): number {
  let h = 0
  for (let i = 0; i < s.length; i++) {
    h = (Math.imul(h, 31) + s.charCodeAt(i)) >>> 0
  }
  return h >>> 0
}

function mulberry32(seed: number) {
  let s = seed
  return () => {
    s |= 0
    s = (s + 0x6d2b79f5) | 0
    let t = Math.imul(s ^ (s >>> 15), 1 | s)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

interface NodeDatum {
  record: AuditRecord
  position: [number, number, number]
  radius: number
}

function useGalaxyLayout(records: AuditRecord[]): NodeDatum[] {
  return useMemo(() => {
    const maxAmount = Math.max(...records.map((r) => r.amount_inr), 1)
    return records.slice(0, 220).map((record) => {
      const clusterIndex = FAILURE_REASON_ORDER.indexOf(record.failure_reason)
      const angle = (Math.max(clusterIndex, 0) / FAILURE_REASON_ORDER.length) * Math.PI * 2
      const cx = Math.cos(angle) * RING_RADIUS
      const cz = Math.sin(angle) * RING_RADIUS

      const rng = mulberry32(hashString(record.transaction_id))
      const u = rng()
      const v = rng()
      const w = rng()
      const r = CLUSTER_SPREAD * Math.cbrt(w)
      const theta = Math.acos(2 * u - 1)
      const phi = 2 * Math.PI * v

      const x = cx + r * Math.sin(theta) * Math.cos(phi)
      const y = r * Math.sin(theta) * Math.sin(phi) * 0.6
      const z = cz + r * Math.cos(theta)

      const norm = Math.sqrt(record.amount_inr / maxAmount)
      const radius = 0.09 + norm * 0.26

      return { record, position: [x, y, z] as [number, number, number], radius }
    })
  }, [records])
}

function TransactionNode({
  datum,
  isHovered,
  isSelected,
  onHover,
  onSelect,
}: {
  datum: NodeDatum
  isHovered: boolean
  isSelected: boolean
  onHover: (id: string | null) => void
  onSelect: (id: string) => void
}) {
  const meshRef = useRef<THREE.Mesh>(null)
  const color = OUTCOME_HEX[datum.record.outcome]
  const scale = isHovered || isSelected ? 1.6 : 1

  useFrame(() => {
    if (!meshRef.current) return
    meshRef.current.scale.lerp(new THREE.Vector3(scale, scale, scale), 0.25)
  })

  return (
    <mesh
      ref={meshRef}
      position={datum.position}
      onPointerOver={(e) => {
        e.stopPropagation()
        onHover(datum.record.transaction_id)
        document.body.style.cursor = 'pointer'
      }}
      onPointerOut={(e) => {
        e.stopPropagation()
        onHover(null)
        document.body.style.cursor = 'auto'
      }}
      onClick={(e) => {
        e.stopPropagation()
        onSelect(datum.record.transaction_id)
      }}
    >
      <sphereGeometry args={[datum.radius, 16, 16]} />
      <meshBasicMaterial color={color} transparent opacity={isHovered || isSelected ? 1 : 0.85} />
    </mesh>
  )
}

function ClusterRing({ autoRotate }: { autoRotate: boolean }) {
  const groupRef = useRef<THREE.Group>(null)
  useFrame((_, delta) => {
    if (autoRotate && groupRef.current) {
      groupRef.current.rotation.y += delta * 0.05
    }
  })
  return (
    <group ref={groupRef}>
      {FAILURE_REASON_ORDER.map((reason, i) => {
        const angle = (i / FAILURE_REASON_ORDER.length) * Math.PI * 2
        const x = Math.cos(angle) * RING_RADIUS
        const z = Math.sin(angle) * RING_RADIUS
        return (
          <mesh key={reason} position={[x, 0, z]}>
            <ringGeometry args={[CLUSTER_SPREAD + 0.15, CLUSTER_SPREAD + 0.19, 48]} />
            <meshBasicMaterial color={FAILURE_REASON_HEX[reason]} transparent opacity={0.28} side={THREE.DoubleSide} />
          </mesh>
        )
      })}
    </group>
  )
}

function GalaxyScene({
  nodes,
  hoveredId,
  selectedId,
  onHover,
  onSelect,
  autoRotate,
}: {
  nodes: NodeDatum[]
  hoveredId: string | null
  selectedId: string | null
  onHover: (id: string | null) => void
  onSelect: (id: string) => void
  autoRotate: boolean
}) {
  return (
    <group>
      <ClusterRing autoRotate={autoRotate} />
      {nodes.map((datum) => (
        <TransactionNode
          key={datum.record.transaction_id}
          datum={datum}
          isHovered={hoveredId === datum.record.transaction_id}
          isSelected={selectedId === datum.record.transaction_id}
          onHover={onHover}
          onSelect={onSelect}
        />
      ))}
    </group>
  )
}

interface TransactionGalaxyProps {
  records: AuditRecord[]
}

export default function TransactionGalaxy({ records }: TransactionGalaxyProps) {
  const nodes = useGalaxyLayout(records)
  const [hoveredId, setHoveredId] = useState<string | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [autoRotate, setAutoRotate] = useState(true)

  const activeId = hoveredId ?? selectedId
  const activeRecord = activeId ? records.find((r) => r.transaction_id === activeId) ?? null : null

  return (
    <div className="galaxy-view">
      <div className="view-intro">
        <p>
          Every transaction this run, as a node in space — clustered by failure type, colored by outcome, sized by
          amount. Drag to rotate, scroll to zoom, click a node to inspect it.
        </p>
      </div>

      <div className="galaxy-canvas-wrap">
        <Canvas
          camera={{ position: [0, 4, 12], fov: 50 }}
          onPointerMissed={() => setSelectedId(null)}
          onPointerDown={() => setAutoRotate(false)}
        >
          <color attach="background" args={['#050609']} />
          <GalaxyScene
            nodes={nodes}
            hoveredId={hoveredId}
            selectedId={selectedId}
            onHover={setHoveredId}
            onSelect={setSelectedId}
            autoRotate={autoRotate}
          />
          <OrbitControls enablePan={false} minDistance={4} maxDistance={26} />
        </Canvas>

        <div className="galaxy-legend">
          <div className="galaxy-legend-group">
            <span className="galaxy-legend-title">Cluster = failure reason</span>
            {FAILURE_REASON_ORDER.map((reason) => (
              <div className="galaxy-legend-row" key={reason}>
                <span className="galaxy-legend-dot" style={{ background: FAILURE_REASON_HEX[reason] }} />
                {FAILURE_REASON_LABEL[reason]}
              </div>
            ))}
          </div>
          <div className="galaxy-legend-group">
            <span className="galaxy-legend-title">Color = outcome</span>
            {(Object.keys(OUTCOME_HEX) as Outcome[]).map((outcome) => (
              <div className="galaxy-legend-row" key={outcome}>
                <span className="galaxy-legend-dot" style={{ background: OUTCOME_HEX[outcome] }} />
                {OUTCOME_LABEL[outcome]}
              </div>
            ))}
          </div>
        </div>

        {activeRecord && (
          <div className="galaxy-detail glass">
            <div className="galaxy-detail-head">
              <span className="mono">{activeRecord.transaction_id}</span>
              <span
                className="outcome-badge"
                style={{ '--badge-color': OUTCOME_HEX[activeRecord.outcome] } as React.CSSProperties}
              >
                {OUTCOME_LABEL[activeRecord.outcome]}
              </span>
            </div>
            <div className="galaxy-detail-row">{activeRecord.customer_name} · {activeRecord.product_name}</div>
            <div className="galaxy-detail-row">
              {FAILURE_REASON_LABEL[activeRecord.failure_reason as FailureReason]} · {formatInr(activeRecord.amount_inr)}
            </div>
            <div className="galaxy-detail-row mono small muted">{activeRecord.rule_fired}</div>
          </div>
        )}
      </div>
    </div>
  )
}
