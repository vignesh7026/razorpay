import { animate, scrambleText } from 'animejs'
import { useEffect, useRef } from 'react'

interface ScrambleTextProps {
  text: string
  className?: string
  as?: 'span' | 'h1' | 'h2' | 'h3' | 'div'
  triggerKey?: string | number
  chars?: string
}

export default function ScrambleText({ text, className, as = 'span', triggerKey, chars = 'uppercase' }: ScrambleTextProps) {
  const ref = useRef<HTMLElement | null>(null)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    el.textContent = text
    const anim = animate(el, {
      textContent: scrambleText({ text, chars, revealRate: 55, settleDuration: 260 }),
      duration: 700,
    })
    return () => {
      anim.pause()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [text, triggerKey])

  const Tag = as as 'span'
  return (
    <Tag ref={ref as never} className={className}>
      {text}
    </Tag>
  )
}
