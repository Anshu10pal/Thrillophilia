import { useEffect } from 'react'
import { motion } from 'framer-motion'
import usePlanStore from '../store/planStore'
import { usePlanningStream } from '../hooks/usePlanningStream'

const STEPS = [
  { key:'user_input_agent',   emoji:'🔍', label:'Parsing your request'       },
  { key:'memory_agent',       emoji:'🧠', label:'Retrieving travel knowledge' },
  { key:'weather_agent',      emoji:'🌤️', label:'Live weather check'          },
  { key:'transport_agent',    emoji:'✈️',  label:'Finding best routes'         },
  { key:'hotel_agent',        emoji:'🏨', label:'Searching hotels'            },
  { key:'places_agent',       emoji:'📍', label:'Discovering attractions'     },
  { key:'budget_agent',       emoji:'💰', label:'Calculating budget'          },
  { key:'itinerary_agent',    emoji:'📅', label:'Building your itinerary'     },
  { key:'final_review_agent', emoji:'✅', label:'Final quality review'        },
]

export default function PlanningPage() {
  const { jobId, streamEvents, planStatus, setPage, preferences, nearbySuggestions } = usePlanStore()
  usePlanningStream(jobId)

  useEffect(() => {
    if (planStatus === 'complete') {
      setTimeout(() => setPage('results'), 1000)
    }
  }, [planStatus])

  const completed = new Set(streamEvents.filter(e => e.event==='agent_done').map(e => e.agent))
  const pct       = Math.max(5, Math.min(95, (completed.size / STEPS.length) * 90 + 5))
  const latest    = streamEvents.findLast?.(e => e.message)?.message || 'Starting up…'
  const dest      = preferences?.destination || 'your destination'

  return (
    <div style={{
      minHeight:'100vh', display:'flex', alignItems:'center', justifyContent:'center',
      background:'var(--dark)', padding:'2rem 1rem',
    }}>
      <div style={{ width:'100%', maxWidth:'540px' }}>

        {/* Header */}
        <div style={{ textAlign:'center', marginBottom:'2.5rem' }}>
          <motion.div
            animate={{ rotate:360 }}
            transition={{ repeat:Infinity, duration:4, ease:'linear' }}
            style={{ fontSize:'3.5rem', display:'inline-block', marginBottom:'1rem' }}
          >✨</motion.div>
          <h2 className="t-heading" style={{ fontSize:'1.8rem', color:'var(--text-1)', marginBottom:'6px' }}>
            Crafting Your Journey
          </h2>
          <p className="t-body" style={{ color:'var(--text-3)', fontSize:'0.9rem' }}>
            AI agents are building your perfect {dest} trip
          </p>
        </div>

        {/* Progress bar */}
        <div className="progress-track" style={{ marginBottom:'8px', height:'6px' }}>
          <motion.div className="progress-fill" animate={{ width:`${pct}%` }} transition={{ duration:0.5 }} />
        </div>
        <div style={{ display:'flex', justifyContent:'space-between', marginBottom:'1.5rem' }}>
          <span className="t-label" style={{ color:'var(--text-3)', fontSize:'0.6rem' }}>{Math.round(pct)}% complete</span>
          <span className="t-label" style={{ color:'var(--gold)', fontSize:'0.6rem', maxWidth:'300px', textAlign:'right',
                                              overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
            {latest}
          </span>
        </div>

        {/* Agent steps */}
        <div className="card" style={{ padding:'20px 24px' }}>
          {STEPS.map((step, i) => {
            const done    = completed.has(step.key)
            const running = !done && streamEvents.some(e => e.event==='agent_start' && e.agent===step.key)
            const detail  = streamEvents.findLast?.(e => e.event==='agent_done' && e.agent===step.key)?.message

            return (
              <motion.div
                key={step.key}
                initial={{ opacity:0.3 }}
                animate={{ opacity: done||running ? 1 : 0.35 }}
                style={{ display:'flex', alignItems:'flex-start', gap:'12px', marginBottom: i<STEPS.length-1 ? '14px' : 0 }}
              >
                <div style={{
                  width:'26px', height:'26px', borderRadius:'50%', flexShrink:0,
                  display:'flex', alignItems:'center', justifyContent:'center',
                  fontSize:'11px', fontFamily:'Montserrat,sans-serif', fontWeight:700,
                  marginTop:'1px',
                  background: done ? 'rgba(46,125,82,0.15)' : running ? 'rgba(201,168,76,0.15)' : 'var(--dark-3)',
                  border:     done ? '1px solid rgba(46,125,82,0.5)' : running ? '1px solid rgba(201,168,76,0.5)' : '1px solid var(--border)',
                  color:      done ? '#2E7D52' : running ? 'var(--gold)' : 'var(--text-3)',
                  animation:  running ? 'pulse 1.5s ease-in-out infinite' : 'none',
                }}>
                  {done ? '✓' : running ? '⟳' : String(i+1)}
                </div>
                <div style={{ flex:1, minWidth:0 }}>
                  <div className="t-label" style={{
                    fontSize:'0.65rem',
                    color: done ? 'var(--text-1)' : running ? 'var(--gold)' : 'var(--text-3)',
                  }}>
                    {step.emoji} {step.label}
                  </div>
                  {done && detail && (
                    <div className="t-body" style={{
                      fontSize:'0.72rem', color:'var(--text-3)', marginTop:'2px',
                      overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap',
                    }}>{detail}</div>
                  )}
                </div>
              </motion.div>
            )
          })}
        </div>

        {/* Nearby prompt */}
        {nearbySuggestions.length > 0 && (
          <motion.div initial={{ opacity:0, y:8 }} animate={{ opacity:1, y:0 }}
            className="card-gold" style={{ marginTop:'16px', padding:'14px 18px' }}>
            <p className="t-label" style={{ fontSize:'0.62rem', color:'var(--gold)', marginBottom:'8px' }}>
              🗺️ Want to explore nearby?
            </p>
            <div style={{ display:'flex', gap:'8px', flexWrap:'wrap' }}>
              {nearbySuggestions.slice(0,3).map(c => (
                <span key={c.name} className="t-body" style={{
                  fontSize:'0.78rem', color:'var(--text-2)',
                  background:'rgba(201,168,76,0.08)', border:'1px solid rgba(201,168,76,0.2)',
                  borderRadius:'20px', padding:'4px 12px',
                }}>
                  {c.emoji} {c.name} · {c.drive_hours}h
                </span>
              ))}
            </div>
          </motion.div>
        )}

        {planStatus === 'complete' && (
          <motion.div initial={{ opacity:0, scale:0.95 }} animate={{ opacity:1, scale:1 }}
            className="card-gold" style={{ marginTop:'16px', padding:'16px', textAlign:'center' }}>
            <p className="t-heading" style={{ fontSize:'1.1rem', color:'var(--gold)' }}>
              🎉 Your plan is ready!
            </p>
            <p className="t-body" style={{ fontSize:'0.82rem', color:'var(--text-3)', marginTop:'4px' }}>
              Taking you to your itinerary…
            </p>
          </motion.div>
        )}

        {planStatus === 'error' && (
          <motion.div initial={{ opacity:0 }} animate={{ opacity:1 }}
            style={{ marginTop:'16px', padding:'16px', borderRadius:'12px', textAlign:'center',
                     background:'rgba(160,32,32,0.12)', border:'1px solid rgba(160,32,32,0.3)' }}>
            <p style={{ color:'#FFB3B3', fontSize:'0.88rem', fontFamily:'Inter,sans-serif' }}>
              ❌ Planning encountered an issue.
            </p>
            <button className="btn-gold" style={{ marginTop:'12px', fontSize:'0.75rem' }}
              onClick={() => usePlanStore.getState().resetPlan()}>
              Try Again
            </button>
          </motion.div>
        )}
      </div>

      <style>{`
        @keyframes pulse {
          0%,100% { opacity:1 }
          50%      { opacity:0.5 }
        }
      `}</style>
    </div>
  )
}
