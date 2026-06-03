import { useEffect, useRef } from 'react'

export default function BudgetChart({ breakdown, currency }) {
  const ref = useRef(null)
  useEffect(() => {
    if (!breakdown || !ref.current) return
    const keys   = ['transport','accommodation','food','activities','miscellaneous']
    const labels = ['Transport','Accommodation','Food','Activities','Misc']
    const colors = ['#1A4A8A','#C9A84C','#2E7D52','#8B5CF6','#555']
    const values = keys.map(k => breakdown[k] || 0)
    const total  = values.reduce((a,b) => a+b, 0)
    if (!total) return
    const canvas = ref.current
    const ctx    = canvas.getContext('2d')
    const cx = canvas.width/2, cy = canvas.height/2 - 20
    const r  = Math.min(cx, cy) - 15
    const hole = r * 0.55
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    let angle = -Math.PI/2
    values.forEach((val, i) => {
      if (!val) return
      const slice = (val/total) * 2 * Math.PI
      ctx.beginPath(); ctx.moveTo(cx,cy)
      ctx.arc(cx, cy, r, angle, angle+slice); ctx.closePath()
      ctx.fillStyle = colors[i]; ctx.fill()
      angle += slice
    })
    ctx.beginPath(); ctx.arc(cx,cy,hole,0,2*Math.PI)
    ctx.fillStyle = '#1E1E1E'; ctx.fill()
    ctx.fillStyle = '#C9A84C'; ctx.font = 'bold 10px Montserrat,sans-serif'
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle'
    ctx.fillText(currency, cx, cy)
    const ly = cy + r + 20
    labels.forEach((label, i) => {
      if (!values[i]) return
      const x = 10 + i * (canvas.width/labels.length)
      ctx.fillStyle = colors[i]; ctx.fillRect(x, ly, 10, 10)
      ctx.fillStyle = '#888'; ctx.font = '8px Inter,sans-serif'
      ctx.textAlign = 'left'; ctx.fillText(label, x+13, ly+8)
    })
  }, [breakdown, currency])
  return <canvas ref={ref} width={280} height={220} style={{ maxWidth:'100%' }} />
}
