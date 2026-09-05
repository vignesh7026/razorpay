import { motion, useMotionTemplate, useMotionValue, useSpring, useTransform } from 'framer-motion'
import type { CSSProperties, PointerEvent, ReactNode } from 'react'

interface TiltCardProps {
  children: ReactNode
  className?: string
  style?: CSSProperties
  maxTilt?: number
  glare?: boolean
  onClick?: () => void
}

export default function TiltCard({
  children,
  className = '',
  style,
  maxTilt = 10,
  glare = true,
  onClick,
}: TiltCardProps) {
  const rawX = useMotionValue(0.5)
  const rawY = useMotionValue(0.5)
  const px = useSpring(rawX, { stiffness: 200, damping: 20, mass: 0.4 })
  const py = useSpring(rawY, { stiffness: 200, damping: 20, mass: 0.4 })

  const rotY = useMotionValue(0)
  const rotX = useMotionValue(0)
  const springRotY = useSpring(rotY, { stiffness: 180, damping: 18, mass: 0.4 })
  const springRotX = useSpring(rotX, { stiffness: 180, damping: 18, mass: 0.4 })

  const pxPercent = useTransform(px, (v) => `${v * 100}%`)
  const pyPercent = useTransform(py, (v) => `${v * 100}%`)
  const background = useMotionTemplate`radial-gradient(circle at ${pxPercent} ${pyPercent}, rgba(255,255,255,0.10), transparent 55%)`

  function handlePointerMove(e: PointerEvent<HTMLDivElement>) {
    const rect = e.currentTarget.getBoundingClientRect()
    const x = (e.clientX - rect.left) / rect.width
    const y = (e.clientY - rect.top) / rect.height
    rawX.set(x)
    rawY.set(y)
    rotY.set((x - 0.5) * maxTilt * 2)
    rotX.set(-(y - 0.5) * maxTilt * 2)
  }

  function handlePointerLeave() {
    rotY.set(0)
    rotX.set(0)
    rawX.set(0.5)
    rawY.set(0.5)
  }

  return (
    <motion.div
      className={className}
      style={{
        ...style,
        transformStyle: 'preserve-3d',
        rotateX: springRotX,
        rotateY: springRotY,
        position: 'relative',
      }}
      onPointerMove={handlePointerMove}
      onPointerLeave={handlePointerLeave}
      onClick={onClick}
    >
      {children}
      {glare && (
        <motion.div
          aria-hidden
          style={{
            position: 'absolute',
            inset: 0,
            borderRadius: 'inherit',
            pointerEvents: 'none',
            background,
            mixBlendMode: 'overlay',
          }}
        />
      )}
    </motion.div>
  )
}
