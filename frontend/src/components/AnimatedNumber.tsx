import { animate, useMotionValue, useTransform } from 'framer-motion'
import { useEffect, useRef, useState } from 'react'

interface AnimatedNumberProps {
  value: number
  format?: (v: number) => string
  duration?: number
}

export default function AnimatedNumber({ value, format, duration = 1.4 }: AnimatedNumberProps) {
  const motionValue = useMotionValue(0)
  const [display, setDisplay] = useState('0')
  const rounded = useTransform(motionValue, (v) => (format ? format(v) : Math.round(v).toLocaleString('en-IN')))
  const firstRun = useRef(true)

  useEffect(() => {
    const controls = animate(motionValue, value, {
      duration: firstRun.current ? duration : 0.8,
      ease: [0.16, 1, 0.3, 1] as const,
    })
    firstRun.current = false
    const unsub = rounded.on('change', (v) => setDisplay(v))
    return () => {
      controls.stop()
      unsub()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value])

  return <span className="mono">{display}</span>
}
