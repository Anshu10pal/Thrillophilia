// frontend/src/pages/ResultsPage.jsx
import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import usePlanStore from '../store/planStore'
import { addCityToPlan } from '../api/client'

const fmt = n => typeof n === 'number' ? n.toLocaleString('en-IN') : (n || 'N/A')

// ── Budget Donut Chart ────────────────────────────────────────────────────────
function BudgetChart({ bd, currency }) {
  const ref = useRef(null)
  useEffect(() => {
    if (!bd || !ref.current) return
    const keys   = ['transport','accommodation','food','activities','miscellaneous']
    const labels = ['Transport','Accommodation','Food','Activities','Misc']
    const colors = ['#1A4A8A','#C9A84C','#2E7D52','#8B5CF6','#555']
    const values = keys.map(k => bd[k] || 0)
    const total  = values.reduce((a,b)=>a+b,0)
    if (!total) return
    const c = ref.current, ctx = c.getContext('2d')
    const W = c.width, H = c.height
    const cx = W/2, cy = H/2-20, r = Math.min(cx,cy)-15, hole = r*0.55
    ctx.clearRect(0,0,W,H)
    let a = -Math.PI/2
    values.forEach((v,i) => {
      if (!v) return
      const s = (v/total)*2*Math.PI
      ctx.beginPath(); ctx.moveTo(cx,cy); ctx.arc(cx,cy,r,a,a+s); ctx.closePath()
      ctx.fillStyle=colors[i]; ctx.fill(); a+=s
    })
    ctx.beginPath(); ctx.arc(cx,cy,hole,0,2*Math.PI)
    ctx.fillStyle='rgba(10,10,8,0.95)'; ctx.fill()
    ctx.fillStyle='#C9A84C'; ctx.font='bold 10px Montserrat,sans-serif'
    ctx.textAlign='center'; ctx.textBaseline='middle'; ctx.fillText(currency,cx,cy)
    const ly=cy+r+20
    labels.forEach((l,i) => {
      if(!values[i]) return
      const lx=8+i*(W/labels.length)
      ctx.fillStyle=colors[i]; ctx.fillRect(lx,ly,8,8)
      ctx.fillStyle='#888'; ctx.font='8px Inter,sans-serif'
      ctx.textAlign='left'; ctx.fillText(l,lx+11,ly+7)
    })
  }, [bd, currency])
  return <canvas ref={ref} width={270} height={210} style={{ maxWidth:'100%' }} />
}

// ── Local Tips Database ───────────────────────────────────────────────────────
const LOCAL_TIPS = {
  "burj khalifa":    "Visit the 148th floor 'At the Top SKY' above the clouds. Book online — 30% cheaper, skip the queue. Best time: sunset 6-7pm. 🏙️",
  "dubai mall":      "The Dubai Fountain show runs every 30 min after 6pm — free. Snow World inside is a great escape from the 40°C heat outside. ⛲",
  "gold souk":       "Always bargain — start at 40% of asking price. Best time: early morning (10am) before tour groups arrive. 🥇",
  "desert safari":   "Morning safaris (6am) have cooler temperatures and better photography light. Ask about 'ghaf' trees — 5,000 years old. 🏜️",
  "dhow cruise":     "Dubai Creek dhow cruises are more authentic and cheaper than Marina cruises. Sit at the front for best views. ⛵",
  "palm jumeirah":   "Take the Palm Monorail for aerial views. Connects to Atlantis Aquaventure — buy combo tickets to save 20%. 🌴",
  "dubai frame":     "The glass-floored bridge is included. Visit at 5pm — one side in daylight, the other in golden hour. 🖼️",
  "sheikh zayed":    "Free entry but modest dress required — abayas at the gate at no charge. The marble floor has world's largest flower arrangement. 🕌",
  "dubai museum":    "Only AED 3 (₹67) per person — best value in Dubai. The underground section recreates 3,000-year-old desert life. 🏛️",
  "jumeirah beach":  "Kite Beach is less crowded with free parking. Iconic Burj Al Arab view for photos. 🏖️",
  "miracle garden":  "Only open Oct–May. Arrive at 8am opening. The heart tunnel is most photographed — go there first. 🌸",
  "red fort":        "Sound and light show runs evenings at 7:30pm — worth the extra ticket. The museums inside are excellent. 🏰",
  "india gate":      "Best visited after 8pm when it's lit up and cooler. Avoid weekends — very crowded. 🏛️",
  "qutub minar":     "The iron pillar hasn't rusted in 1600 years — a metallurgical mystery. Go in the morning for best photos. 🗼",
  "humayun's tomb":  "The garden is geometrically perfect — forerunner to the Taj Mahal design. Far fewer crowds but equally stunning. 🕌",
  "lotus temple":    "Free entry, no photography inside. Architecture is mesmerizing from outside. Visit at golden hour. 🪷",
  "sagrada familia": "Book tickets 2–3 months in advance — sells out constantly. The interior at noon has stunning light. ⛪",
  "park güell":      "The free area is equally beautiful as the ticketed zone. Visit early morning to avoid crowds. 🌿",
  "la boqueria":     "Skip the tourist stalls at the entrance — better prices and quality deeper inside. Arrive before 10am. 🍅",
}

function LocalTip({ activityName }) {
  if (!activityName) return null
  const key = Object.keys(LOCAL_TIPS).find(k => activityName.toLowerCase().includes(k))
  if (!key) return null
  return (
    <div style={{
      padding:'8px 12px',
      background:'rgba(201,168,76,0.07)',
      border:'1px solid rgba(201,168,76,0.25)',
      borderLeft:'3px solid #C9A84C',
      borderRadius:'0 8px 8px 0',
      fontSize:'0.75rem', color:'#C8C0B0',
      fontFamily:'Inter,sans-serif', lineHeight:1.5,
    }}>
      <span style={{ color:'#C9A84C', fontWeight:600 }}>💡 Local tip: </span>
      {LOCAL_TIPS[key]}
    </div>
  )
}

const TABS = [
  { id:'itinerary', label:'📅 Itinerary' },
  { id:'hotels',    label:'🏨 Hotels'    },
  { id:'transport', label:'✈️ Transport' },
  { id:'places',    label:'📍 Places'    },
  { id:'budget',    label:'💰 Budget'    },
  { id:'weather',   label:'🌤️ Weather'  },
]

export default function ResultsPage() {
  const { result, nearbySuggestions, nearbyPromptShown, resetPlan, jobId, setJobId, setPlanStatus, setPage } = usePlanStore()
  const [tab, setTab]                 = useState('itinerary')
  const [expandedDays, setExpandedDays] = useState(new Set(['all']))
  const [downloading, setDownload]    = useState(false)
  const [selectedHotel, setSelectedHotel]   = useState(null)
  const [removedActivities, setRemovedActivities] = useState(new Set())

  if (!result) return (
    <div style={{ minHeight:'100vh', display:'flex', alignItems:'center', justifyContent:'center', background:'var(--dark)' }}>
      <div style={{ textAlign:'center' }}>
        <p style={{ color:'var(--text-3)', marginBottom:'16px' }}>No result found</p>
        <button className="btn-gold" onClick={resetPlan}>Start New Trip</button>
      </div>
    </div>
  )

  const prefs     = result.trip_preferences || {}
  const weather   = result.weather_data     || {}
  const transport = result.transport_data   || {}
  const hotel     = result.hotel_data       || {}
  const places    = result.places_data      || {}
  const budget    = result.budget_summary   || {}
  const itin      = result.itinerary        || {}
  const review    = result.review_status    || {}
  const currency  = prefs.currency          || 'INR'
  const days      = itin.days               || []
  const prim      = transport.primary_option || {}
  const bd        = budget.breakdown        || {}
  const surplus   = budget.surplus_or_deficit || 0
  const over      = surplus < 0

  const hotelOptions   = hotel.hotel_options || []
  const activeHotelIdx = selectedHotel !== null ? selectedHotel : (hotel.recommended_index || 1)
  const activeHotel    = hotelOptions[Math.min(activeHotelIdx, hotelOptions.length-1)] || hotel.recommended_hotel || {}
  const hotelCost      = (activeHotel.price_per_night || 0) * (prefs.num_days || 5)
  const bdWithHotel    = { ...bd, accommodation: hotelCost || bd.accommodation,
    estimated_total: (bd.transport||0) + (hotelCost||bd.accommodation||0) + (bd.food||0) + (bd.activities||0) + (bd.miscellaneous||0) }
  const surplus2       = (budget.budget_provided || 0) - (bdWithHotel.estimated_total || 0)

  const toggleDay = (dayNum) => setExpandedDays(prev => {
    const next = new Set(prev)
    if (next.has('all')) { next.clear(); next.add(dayNum) }
    else if (next.has(dayNum)) next.delete(dayNum)
    else next.add(dayNum)
    return next
  })
  const isDayExpanded = (dayNum) => expandedDays.has('all') || expandedDays.has(dayNum)
  const removeActivity = (key) => setRemovedActivities(prev => new Set([...prev, key]))
  const restoreActivity = (key) => setRemovedActivities(prev => { const n=new Set(prev); n.delete(key); return n })

  const handleAddCity = async (city) => {
    try {
      const res = await addCityToPlan({ job_id:jobId, city:city.name, num_days:2 })
      setJobId(res.data.job_id); setPlanStatus('queued'); setPage('planning')
    } catch(e) { console.error(e) }
  }

  const handleDownloadPDF = async () => {
    if (!result.pdf_path) return
    setDownload(true)
    try {
      const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'
      const filename = result.pdf_path.split('\\').pop().split('/').pop()
      const pdfRes = await fetch(`${BASE}/api/pdf/${filename}`)
      if (pdfRes.ok) {
        const blob = await pdfRes.blob()
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href=url; a.download=filename; a.click()
        URL.revokeObjectURL(url)
      } else { alert('PDF not found on server.') }
    } catch(e) { alert('PDF download error: ' + e.message) }
    finally { setDownload(false) }
  }

  return (
    <div style={{ minHeight:'100vh', background:'var(--dark)', overflowY:'auto' }}>

      {/* ── STICKY HEADER ───────────────────────────────────────────────── */}
      <div style={{
        display:'flex', alignItems:'center', justifyContent:'space-between',
        padding:'0.9rem 2rem', borderBottom:'1px solid var(--border)',
        background:'rgba(10,10,8,0.96)', backdropFilter:'blur(12px)',
        position:'sticky', top:0, zIndex:50,
      }}>
        <span className="t-display gold-text" style={{ fontSize:'1.4rem' }}>🧳 Thrillophilia</span>
        <div style={{ display:'flex', gap:'8px' }}>
          <button className="btn-outline" style={{ fontSize:'0.7rem', padding:'6px 12px' }} onClick={resetPlan}>
            🔄 New Trip
          </button>
          {result.pdf_path && (
            <button className="btn-gold" style={{ fontSize:'0.7rem', padding:'6px 14px' }}
              onClick={handleDownloadPDF} disabled={downloading}>
              {downloading ? '⟳' : '📥'} PDF Report
            </button>
          )}
        </div>
      </div>

      <div style={{ maxWidth:'1100px', margin:'0 auto', padding:'1.5rem 1.5rem 5rem' }}>

        {/* ── TRIP BANNER ─────────────────────────────────────────────── */}
        <div className="card-gold" style={{ padding:'1.2rem 1.5rem', marginBottom:'1.2rem' }}>
          <h1 className="t-heading" style={{ fontSize:'1.5rem', color:'var(--text-1)', marginBottom:'6px' }}>
            {itin.trip_title || `${prefs.num_days}-Day Trip`}
          </h1>
          <div style={{ display:'flex', flexWrap:'wrap', gap:'16px', fontSize:'0.82rem', color:'var(--text-3)', fontFamily:'Inter,sans-serif' }}>
            <span>📍 {prefs.source} → {prefs.destination}</span>
            <span>👥 {prefs.travelers} travellers</span>
            <span>📅 {prefs.num_days} days</span>
            {activeHotel.name && activeHotel.name !== 'the hotel' && (
              <span>🏨 {activeHotel.name}</span>
            )}
            <span style={{ color:review.approved?'#2E7D52':'var(--gold)' }}>
              {review.approved?'✅ Approved':'⚠️ Reviewed'}
            </span>
          </div>
        </div>

        {/* ── METRICS ─────────────────────────────────────────────────── */}
        <div style={{ display:'grid', gridTemplateColumns:'repeat(5,1fr)', gap:'10px', marginBottom:'1.2rem' }}>
          {[
            { l:'Budget',    v:`${currency} ${fmt(prefs.budget)}` },
            { l:'Estimated', v:`${currency} ${fmt(Math.round(bdWithHotel.estimated_total||0))}`,
              sub:`${surplus2>=0?'+':''}${fmt(Math.round(surplus2))}`,
              sc: surplus2>=0?'#90EE90':'#FFB3B3' },
            { l:'Transport', v:(prim.mode||'N/A').toUpperCase() },
            { l:'Weather',   v:(weather.conditions||'N/A').toUpperCase() },
            { l:'Status',    v:surplus2>=0?'On Track':'Over Budget', vc:surplus2>=0?'#90EE90':'#FFB3B3' },
          ].map(m => (
            <div key={m.l} className="metric">
              <div className="metric-label">{m.l}</div>
              <div className="metric-value" style={{ fontSize:'1rem', ...(m.vc?{color:m.vc}:{}) }}>{m.v}</div>
              {m.sub && <div style={{ fontSize:'0.72rem', color:m.sc, marginTop:'2px', fontFamily:'Inter,sans-serif' }}>{m.sub}</div>}
            </div>
          ))}
        </div>

        {/* ── NEARBY PROMPT ───────────────────────────────────────────── */}
        {nearbyPromptShown && nearbySuggestions.length>0 && (
          <motion.div initial={{ opacity:0, y:8 }} animate={{ opacity:1, y:0 }}
            className="card-gold" style={{ padding:'14px 18px', marginBottom:'1.2rem' }}>
            <p className="t-label" style={{ fontSize:'0.62rem', color:'var(--gold)', marginBottom:'10px' }}>
              🗺️ Want to explore nearby destinations?
            </p>
            <div style={{ display:'flex', gap:'8px', flexWrap:'wrap' }}>
              {nearbySuggestions.map(c => (
                <button key={c.name} onClick={() => handleAddCity(c)}
                  className="btn-outline" style={{ fontSize:'0.72rem', padding:'6px 14px' }}>
                  {c.emoji} {c.name} · +2 days
                </button>
              ))}
            </div>
          </motion.div>
        )}

        {/* ── TABS ────────────────────────────────────────────────────── */}
        <div className="tab-bar" style={{ marginBottom:'1.2rem' }}>
          {TABS.map(t => (
            <button key={t.id} onClick={() => setTab(t.id)}
              className={`tab-btn${tab===t.id?' active':''}`}>{t.label}</button>
          ))}
        </div>

        {/* ════════════════════════════════════════════════════════════
            TAB: ITINERARY
        ════════════════════════════════════════════════════════════ */}
        {tab==='itinerary' && (
          <div>
            <div style={{ display:'flex', gap:'8px', marginBottom:'12px', alignItems:'center' }}>
              <button className="btn-outline" style={{ fontSize:'0.7rem', padding:'5px 12px' }}
                onClick={() => setExpandedDays(new Set(['all']))}>▼ Expand All</button>
              <button className="btn-outline" style={{ fontSize:'0.7rem', padding:'5px 12px' }}
                onClick={() => setExpandedDays(new Set())}>▲ Collapse All</button>
              <span style={{ fontSize:'0.72rem', color:'var(--text-3)', fontFamily:'Inter,sans-serif' }}>
                Click any day header to toggle
              </span>
            </div>

            {days.length===0 ? (
              <div className="card" style={{ padding:'2rem', textAlign:'center', color:'var(--text-3)' }}>
                Itinerary not generated yet.
              </div>
            ) : days.map(day => (
              <div key={day.day} style={{ marginBottom:'12px' }}>
                {/* Day header */}
                <div onClick={() => toggleDay(day.day)} style={{
                  display:'flex', alignItems:'center', justifyContent:'space-between',
                  flexWrap:'wrap', gap:'8px',
                  background:'linear-gradient(90deg,#1E1C08,#141410)',
                  borderLeft:'4px solid var(--gold)',
                  borderRadius:'0 10px 10px 0',
                  padding:'10px 16px',
                  marginBottom: isDayExpanded(day.day) ? '6px' : 0,
                  cursor:'pointer', userSelect:'none',
                }}>
                  <div style={{ display:'flex', alignItems:'center', gap:'10px', flexWrap:'wrap' }}>
                    <span className="t-heading" style={{ fontSize:'1rem', color:'var(--gold-light)' }}>
                      Day {day.day} — {day.theme}
                    </span>
                    {day.date_label && (
                      <span className="t-label" style={{ fontSize:'0.58rem', color:'var(--text-3)' }}>{day.date_label}</span>
                    )}
                    {day.weather?.emoji && (
                      <span style={{
                        background:'rgba(0,0,0,0.4)', border:'1px solid rgba(255,255,255,0.08)',
                        borderRadius:'20px', padding:'2px 10px', fontSize:'0.72rem',
                        display:'inline-flex', alignItems:'center', gap:'5px', fontFamily:'Inter,sans-serif',
                      }}>
                        <span>{day.weather.emoji}</span>
                        <span style={{ color:'var(--text-1)' }}>{day.weather.max_temp}/{day.weather.min_temp}</span>
                        <span style={{ color:'var(--text-3)' }}>·</span>
                        <span style={{ color:'var(--gold)' }}>{day.weather.conditions}</span>
                      </span>
                    )}
                  </div>
                  <div style={{ display:'flex', alignItems:'center', gap:'8px' }}>
                    {day.estimated_day_cost>0 && (
                      <span className="t-label" style={{ fontSize:'0.6rem', color:'var(--text-3)' }}>
                        {currency} {fmt(day.estimated_day_cost)}
                      </span>
                    )}
                    <span style={{ color:'var(--gold)', fontSize:'0.8rem' }}>
                      {isDayExpanded(day.day)?'▲':'▼'}
                    </span>
                  </div>
                </div>

                <AnimatePresence>
                  {isDayExpanded(day.day) && (
                    <motion.div
                      initial={{ opacity:0, height:0 }} animate={{ opacity:1, height:'auto' }}
                      exit={{ opacity:0, height:0 }} transition={{ duration:0.2 }}
                      style={{ overflow:'hidden' }}>
                      <div className="card" style={{ padding:'16px' }}>
                        {/* 3-column layout: activities | meals+stay | tips */}
                        <div style={{ display:'grid', gridTemplateColumns:'1.8fr 1fr 1.2fr', gap:'16px' }}>

                          {/* LEFT: Activities (no inline tips) */}
                          <div>
                            {[['morning','🌅'],['afternoon','☀️'],['evening','🌇'],['night','🌙']].map(([period,emoji]) => {
                              const act = day[period]
                              if (!act?.activity) return null
                              const key = `${day.day}-${period}`
                              const removed = removedActivities.has(key)
                              return (
                                <div key={period} style={{
                                  paddingBottom:'10px', marginBottom:'10px',
                                  borderBottom:'1px solid var(--border)',
                                  opacity: removed ? 0.4 : 1,
                                  transition:'opacity 0.2s',
                                }}>
                                  <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start' }}>
                                    <div style={{ flex:1 }}>
                                      <div className="t-label" style={{ fontSize:'0.58rem', color:'var(--gold)', marginBottom:'2px' }}>
                                        {emoji} {period}
                                      </div>
                                      <div style={{
                                        color: removed?'var(--text-3)':'var(--text-1)',
                                        fontSize:'0.88rem', fontFamily:'Inter,sans-serif', fontWeight:500,
                                        textDecoration: removed?'line-through':'none',
                                      }}>
                                        {act.activity}
                                      </div>
                                      {act.location && (
                                        <div style={{ color:'var(--text-3)', fontSize:'0.74rem', marginTop:'1px' }}>
                                          📍 {act.location}
                                        </div>
                                      )}
                                    </div>
                                    <button
                                      onClick={() => removed ? restoreActivity(key) : removeActivity(key)}
                                      title={removed?'Restore':'Remove from itinerary'}
                                      style={{
                                        background:'none', border:'none', cursor:'pointer',
                                        color: removed?'#2E7D52':'rgba(160,32,32,0.55)',
                                        fontSize:'0.85rem', padding:'2px 5px', marginLeft:'6px',
                                        borderRadius:'4px', transition:'all 0.2s',
                                        flexShrink:0,
                                      }}>
                                      {removed?'↩':'✕'}
                                    </button>
                                  </div>
                                </div>
                              )
                            })}
                          </div>

                          {/* MIDDLE: Meals + Stay */}
                          <div>
                            {day.meals && Object.values(day.meals).some(Boolean) && (
                              <div style={{ marginBottom:'14px' }}>
                                <div className="t-label" style={{ fontSize:'0.58rem', color:'var(--gold)', marginBottom:'6px' }}>🍽️ Meals</div>
                                {Object.entries(day.meals).map(([m,v]) => v && (
                                  <div key={m} style={{ fontSize:'0.79rem', color:'var(--text-2)', fontFamily:'Inter,sans-serif', marginBottom:'3px' }}>
                                    <span style={{ color:'var(--text-3)', textTransform:'capitalize' }}>{m}:</span> {v}
                                  </div>
                                ))}
                              </div>
                            )}
                            {/* Stay — shows selected hotel name */}
                            <div style={{
                              background:'rgba(26,74,138,0.12)', border:'1px solid rgba(26,74,138,0.3)',
                              borderRadius:'8px', padding:'10px',
                            }}>
                              <div className="t-label" style={{ fontSize:'0.58rem', color:'#4A90E2', marginBottom:'3px' }}>🏨 Stay</div>
                              <div style={{ fontSize:'0.82rem', color:'var(--text-1)', fontFamily:'Inter,sans-serif', fontWeight:500 }}>
                                {activeHotel.name && activeHotel.name !== 'the hotel'
                                  ? activeHotel.name
                                  : (day.accommodation && day.accommodation !== 'the hotel'
                                      ? day.accommodation
                                      : `Hotel in ${prefs.destination || 'destination'}`)}
                              </div>
                              {activeHotel.price_per_night > 0 && (
                                <div style={{ fontSize:'0.7rem', color:'var(--text-3)', marginTop:'2px' }}>
                                  {currency} {fmt(activeHotel.price_per_night)}/night
                                </div>
                              )}
                              {activeHotel.location && (
                                <div style={{ fontSize:'0.7rem', color:'var(--text-3)', marginTop:'1px' }}>
                                  📍 {activeHotel.location}
                                </div>
                              )}
                            </div>
                          </div>

                          {/* RIGHT: Consolidated tips for this day */}
                          <div style={{
                            background:'rgba(201,168,76,0.04)',
                            border:'1px solid rgba(201,168,76,0.15)',
                            borderRadius:'10px',
                            padding:'12px',
                            display:'flex',
                            flexDirection:'column',
                            gap:'8px',
                          }}>
                            <div className="t-label" style={{ fontSize:'0.6rem', color:'var(--gold)', marginBottom:'2px' }}>
                              💡 Today's Tips
                            </div>
                            {/* Collect tips from all periods */}
                            {[['morning'],['afternoon'],['evening']].map(([period]) => {
                              const act = day[period]
                              if (!act?.activity) return null
                              const key = `${day.day}-${period}`
                              if (removedActivities.has(key)) return null
                              // LLM-generated tip
                              if (act.tip) return (
                                <div key={period} style={{
                                  fontSize:'0.73rem', color:'var(--text-2)',
                                  fontFamily:'Inter,sans-serif', lineHeight:1.5,
                                  paddingBottom:'6px', borderBottom:'1px solid rgba(201,168,76,0.1)',
                                }}>
                                  <span style={{ color:'var(--gold-light)', fontWeight:600, fontSize:'0.65rem' }}>
                                    {period === 'morning' ? '🌅' : period === 'afternoon' ? '☀️' : '🌇'} {act.activity.split(' ').slice(0,3).join(' ')}:
                                  </span>
                                  <span> {act.tip}</span>
                                </div>
                              )
                              // Static tips database fallback
                              const tipKey = Object.keys(LOCAL_TIPS).find(k => act.activity.toLowerCase().includes(k))
                              if (tipKey) return (
                                <div key={period} style={{
                                  fontSize:'0.73rem', color:'var(--text-2)',
                                  fontFamily:'Inter,sans-serif', lineHeight:1.5,
                                  paddingBottom:'6px', borderBottom:'1px solid rgba(201,168,76,0.1)',
                                }}>
                                  <span style={{ color:'var(--gold-light)', fontWeight:600, fontSize:'0.65rem' }}>
                                    {period === 'morning' ? '🌅' : period === 'afternoon' ? '☀️' : '🌇'} {act.activity.split(' ').slice(0,3).join(' ')}:
                                  </span>
                                  <span> {LOCAL_TIPS[tipKey]}</span>
                                </div>
                              )
                              return null
                            })}
                            {/* If no tips available */}
                            {!([['morning'],['afternoon'],['evening']].some(([p]) => {
                              const act = day[p]
                              if (!act?.activity) return false
                              if (removedActivities.has(`${day.day}-${p}`)) return false
                              return act.tip || Object.keys(LOCAL_TIPS).find(k => act.activity.toLowerCase().includes(k))
                            })) && (
                              <div style={{ fontSize:'0.72rem', color:'var(--text-3)', fontFamily:'Inter,sans-serif', fontStyle:'italic' }}>
                                Explore freely — tips will appear for well-known locations.
                              </div>
                            )}
                          </div>

                        </div>{/* end 3-col grid */}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            ))}

            {/* Packing + Travel Tips */}
            {days.length>0 && (
              <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:'14px', marginTop:'8px' }}>
                {itin.packing_checklist?.length>0 && (
                  <div className="card" style={{ padding:'14px' }}>
                    <div className="sec-div"><div className="sec-div-title">🧳 Packing Checklist</div></div>
                    <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:'4px' }}>
                      {itin.packing_checklist.map(i => (
                        <div key={i} style={{ fontSize:'0.8rem', color:'var(--text-2)', fontFamily:'Inter,sans-serif' }}>☐ {i}</div>
                      ))}
                    </div>
                  </div>
                )}
                {itin.travel_tips?.length>0 && (
                  <div className="card" style={{ padding:'14px' }}>
                    <div className="sec-div"><div className="sec-div-title">💡 Travel Tips</div></div>
                    {itin.travel_tips.map(t => (
                      <div key={t} style={{ fontSize:'0.8rem', color:'var(--text-2)', marginBottom:'5px', fontFamily:'Inter,sans-serif' }}>• {t}</div>
                    ))}
                    {itin.emergency_contacts && (
                      <div style={{ marginTop:'8px', paddingTop:'8px', borderTop:'1px solid var(--border)' }}>
                        <div className="t-label" style={{ fontSize:'0.58rem', color:'#E85D04', marginBottom:'5px' }}>🚨 Emergency</div>
                        {Object.entries(itin.emergency_contacts).map(([k,v]) => (
                          <div key={k} style={{ fontSize:'0.75rem', color:'var(--text-3)', fontFamily:'Inter,sans-serif' }}>
                            {k}: <span style={{ color:'var(--text-1)' }}>{v}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* ════════════════════════════════════════════════════════════
            TAB: HOTELS — Interactive selection
        ════════════════════════════════════════════════════════════ */}
        {tab==='hotels' && (
          <div>
            {hotelOptions.length===0 ? (
              <div className="card" style={{ padding:'2rem', textAlign:'center' }}>
                <div style={{ fontSize:'2rem', marginBottom:'12px' }}>🏨</div>
                <p style={{ color:'var(--text-3)', marginBottom:'8px', fontFamily:'Inter,sans-serif' }}>
                  Hotel options are being generated for this plan.
                </p>
                {hotel.recommended_hotel?.name && hotel.recommended_hotel.name !== 'the hotel' && (
                  <div style={{ marginTop:'12px', padding:'12px', background:'var(--dark-3)', borderRadius:'8px' }}>
                    <div className="t-heading" style={{ fontSize:'1rem', color:'var(--text-1)' }}>
                      {hotel.recommended_hotel.name}
                    </div>
                    <div style={{ color:'var(--text-3)', fontSize:'0.8rem', marginTop:'4px', fontFamily:'Inter,sans-serif' }}>
                      {currency} {fmt(hotel.recommended_hotel.price_per_night)}/night
                    </div>
                  </div>
                )}
                <p style={{ color:'var(--text-3)', fontSize:'0.75rem', marginTop:'12px', fontFamily:'Inter,sans-serif' }}>
                  Tip: Try planning again — hotel API sometimes needs a retry.
                </p>
              </div>
            ) : (
              <>
                <div style={{
                  padding:'12px 16px', marginBottom:'16px', borderRadius:'10px',
                  background:'rgba(201,168,76,0.06)', border:'1px solid rgba(201,168,76,0.2)',
                  display:'flex', alignItems:'center', gap:'10px',
                }}>
                  <span style={{ fontSize:'1.2rem' }}>💡</span>
                  <div>
                    <div style={{ fontFamily:'Montserrat,sans-serif', fontSize:'0.75rem', fontWeight:700, color:'var(--text-1)' }}>
                      Click a hotel to select it — budget updates automatically
                    </div>
                    <div style={{ fontFamily:'Inter,sans-serif', fontSize:'0.72rem', color:'var(--text-3)' }}>
                      Total budget: {currency} {fmt(budget.budget_provided)} ·
                      Hotel budget (40%): {currency} {fmt(Math.round((budget.budget_provided||0)*0.4))}
                    </div>
                  </div>
                </div>

                {hotelOptions.map((opt, i) => {
                  const cs = { 'Budget Pick':'#2E7D52', 'Best Value':'#C9A84C', 'Comfort Choice':'#8B5CF6' }
                  const c  = cs[opt.tier] || 'var(--gold)'
                  const isSelected = i === activeHotelIdx
                  const totalCost  = (opt.price_per_night||0) * (prefs.num_days||5)
                  const withinBudget = totalCost <= (budget.budget_provided||0)*0.4
                  return (
                    <motion.div key={i}
                      whileHover={{ scale:1.005 }}
                      onClick={() => setSelectedHotel(i)}
                      style={{
                        padding:'18px', marginBottom:'12px',
                        borderRadius: isSelected ? '12px' : '0 12px 12px 0',
                        borderLeft:`4px solid ${c}`,
                        border: isSelected ? `2px solid ${c}` : `1px solid var(--border)`,
                        background: isSelected ? `${c}09` : 'var(--card)',
                        cursor:'pointer', transition:'all 0.2s',
                      }}>
                      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start' }}>
                        <div>
                          <div style={{ display:'flex', alignItems:'center', gap:'8px', marginBottom:'4px' }}>
                            <span className="t-label" style={{ fontSize:'0.6rem', color:c }}>{opt.tier}</span>
                            {isSelected && (
                              <span className="t-label" style={{
                                fontSize:'0.58rem', padding:'2px 8px', borderRadius:'5px',
                                background:`${c}20`, color:c, border:`1px solid ${c}40`,
                              }}>✦ Selected</span>
                            )}
                            {i===(hotel.recommended_index||1) && !isSelected && (
                              <span className="t-label" style={{
                                fontSize:'0.58rem', padding:'2px 8px', borderRadius:'5px',
                                background:'rgba(201,168,76,0.1)', color:'var(--gold)',
                                border:'1px solid rgba(201,168,76,0.3)',
                              }}>Recommended</span>
                            )}
                          </div>
                          <div className="t-heading" style={{ fontSize:'1.1rem', color:'var(--text-1)' }}>{opt.name}</div>
                          <div style={{ color:'var(--text-3)', fontSize:'0.78rem', marginTop:'3px', fontFamily:'Inter,sans-serif' }}>
                            📍 {opt.location} · {opt.category} · ⭐ {opt.rating}
                          </div>
                          <div style={{ display:'flex', flexWrap:'wrap', gap:'4px', marginTop:'8px' }}>
                            {(opt.amenities||[]).map(a => (
                              <span key={a} className="t-label" style={{
                                fontSize:'0.58rem', padding:'2px 8px', borderRadius:'4px',
                                background:`${c}12`, color:c, border:`1px solid ${c}25`,
                              }}>{a}</span>
                            ))}
                          </div>
                          {opt.why_pick && (
                            <div style={{ marginTop:'6px', fontSize:'0.76rem', color:'var(--text-3)', fontStyle:'italic', fontFamily:'Inter,sans-serif' }}>
                              {opt.why_pick}
                            </div>
                          )}
                        </div>
                        <div style={{ textAlign:'right', minWidth:'140px' }}>
                          <div className="t-heading" style={{ fontSize:'1.3rem', color:isSelected?c:'var(--text-1)' }}>
                            {currency} {fmt(opt.price_per_night)}
                            <span style={{ fontSize:'0.65rem', color:'var(--text-3)', fontFamily:'Inter,sans-serif' }}>/night</span>
                          </div>
                          <div style={{ fontSize:'0.75rem', color:'var(--text-3)', fontFamily:'Inter,sans-serif' }}>
                            {prefs.num_days} nights = {currency} {fmt(totalCost)}
                          </div>
                          <div style={{
                            marginTop:'6px', fontSize:'0.72rem', fontFamily:'Montserrat,sans-serif', fontWeight:600,
                            color: withinBudget ? '#2E7D52' : '#FFB3B3',
                          }}>
                            {withinBudget ? '✅ Within budget' : '⚠️ High spend'}
                          </div>
                          <div style={{ fontSize:'0.7rem', color:'var(--gold)', marginTop:'4px', fontFamily:'Montserrat,sans-serif' }}>
                            📱 {opt.booking_platform}
                          </div>
                        </div>
                      </div>
                    </motion.div>
                  )
                })}

                {selectedHotel !== null && (
                  <motion.div initial={{ opacity:0, y:6 }} animate={{ opacity:1, y:0 }}
                    className="card-gold" style={{ padding:'12px 16px', marginTop:'8px' }}>
                    <p style={{ fontSize:'0.82rem', color:'var(--gold)', fontFamily:'Inter,sans-serif' }}>
                      ✅ <strong>{activeHotel.name}</strong> selected ·
                      {currency} {fmt(hotelCost)} for {prefs.num_days} nights ·
                      Budget tab updated automatically.
                    </p>
                  </motion.div>
                )}
              </>
            )}
          </div>
        )}

        {/* ════════════════════════════════════════════════════════════
            TAB: TRANSPORT
        ════════════════════════════════════════════════════════════ */}
        {tab==='transport' && (
          <div>
            {prim.mode && (
              <div className="card" style={{ padding:'18px', marginBottom:'12px', border:'1px solid rgba(26,74,138,0.5)' }}>
                <div className="sec-div" style={{ marginTop:0 }}><div className="sec-div-title">✈️ Primary Transport</div></div>
                <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start' }}>
                  <div>
                    <div className="t-heading" style={{ fontSize:'1.1rem', color:'var(--text-1)' }}>
                      {prim.mode?.toUpperCase()} — {prim.operator}
                    </div>
                    <div style={{ color:'var(--text-3)', fontSize:'0.8rem', marginTop:'4px', fontFamily:'Inter,sans-serif' }}>
                      ⏱ {prim.duration} · 🗓 {prim.schedule} · 📱 {prim.booking_platform}
                    </div>
                    <div style={{ color:prim.fits_budget?'var(--green)':'var(--gold)', fontSize:'0.8rem', marginTop:'6px' }}>
                      {prim.fits_budget?'✅ Fits budget':'⚠️ May exceed budget'}
                    </div>
                  </div>
                  <div style={{ textAlign:'right' }}>
                    <div className="t-heading" style={{ fontSize:'1.4rem' }}>
                      {currency} {fmt(prim.price_per_person)}
                      <span style={{ fontSize:'0.65rem', color:'var(--text-3)', fontFamily:'Inter,sans-serif' }}>/person</span>
                    </div>
                    <div style={{ fontSize:'0.75rem', color:'var(--text-3)', fontFamily:'Inter,sans-serif' }}>
                      ×{prefs.travelers}: {currency} {fmt(prim.total_price)}
                    </div>
                  </div>
                </div>
              </div>
            )}
            {transport.alternative_options?.length>0 && (
              <div>
                <div className="sec-div"><div className="sec-div-title">🔄 Alternative Options</div></div>
                {transport.alternative_options.map((alt,i) => (
                  <div key={i} className="card" style={{ padding:'12px 16px', marginBottom:'8px', display:'flex', justifyContent:'space-between', alignItems:'center' }}>
                    <div>
                      <span className="t-label" style={{ fontSize:'0.65rem', color:'var(--text-1)' }}>{alt.mode?.toUpperCase()}</span>
                      <span style={{ color:'var(--text-3)', fontSize:'0.78rem', marginLeft:'10px', fontFamily:'Inter,sans-serif' }}>⏱ {alt.duration}</span>
                      <div style={{ color:'var(--text-3)', fontSize:'0.72rem', fontFamily:'Inter,sans-serif' }}>{alt.notes || alt.operator}</div>
                    </div>
                    <div className="t-heading" style={{ fontSize:'1.1rem', color:'var(--gold)' }}>
                      {alt.price_per_person>0 ? `${currency} ${fmt(alt.price_per_person)}/p` : 'N/A'}
                    </div>
                  </div>
                ))}
              </div>
            )}
            {transport.local_transport && (
              <div style={{ marginTop:'16px' }}>
                <div className="sec-div"><div className="sec-div-title">🛺 Local Transport in {prefs.destination}</div></div>
                <div style={{ display:'grid', gridTemplateColumns:'repeat(3,1fr)', gap:'10px', marginBottom:'10px' }}>
                  {[['Mode',transport.local_transport.recommended],
                    ['Daily',`${currency} ${fmt(transport.local_transport.daily_cost)}`],
                    ['Total',`${currency} ${fmt(transport.local_transport.total_local_cost)}`]].map(([l,v]) => (
                    <div key={l} className="metric"><div className="metric-label">{l}</div><div className="metric-value" style={{ fontSize:'1rem' }}>{v}</div></div>
                  ))}
                </div>
                {transport.local_transport.tips && (
                  <div style={{ padding:'10px 14px', borderRadius:'9px', background:'var(--dark-3)', border:'1px solid var(--border)', fontSize:'0.82rem', color:'var(--text-2)', fontFamily:'Inter,sans-serif' }}>
                    💡 {transport.local_transport.tips}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* ════════════════════════════════════════════════════════════
            TAB: PLACES
        ════════════════════════════════════════════════════════════ */}
        {tab==='places' && (
          <div>
            {places.top_attractions?.length>0 && (
              <div>
                <div className="sec-div"><div className="sec-div-title">🗺️ Top Attractions</div></div>
                <div style={{ display:'grid', gridTemplateColumns:'repeat(2,1fr)', gap:'10px', marginBottom:'20px' }}>
                  {places.top_attractions.map(att => (
                    <div key={att.name} className="card" style={{ padding:'12px' }}>
                      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start' }}>
                        <div style={{ flex:1 }}>
                          <div style={{ fontFamily:'Montserrat,sans-serif', fontWeight:600, fontSize:'0.86rem', color:'var(--text-1)' }}>{att.name}</div>
                          <div style={{ display:'flex', gap:'8px', marginTop:'4px', flexWrap:'wrap' }}>
                            <span className="t-label" style={{ fontSize:'0.58rem', background:'rgba(201,168,76,0.1)', color:'var(--gold)', border:'1px solid rgba(201,168,76,0.2)', borderRadius:'4px', padding:'1px 6px' }}>{att.type}</span>
                            <span style={{ color:'var(--text-3)', fontSize:'0.72rem' }}>⏱ {att.duration}</span>
                            <span style={{ color:'var(--gold)', fontSize:'0.72rem' }}>⭐ {att.rating}</span>
                          </div>
                          <LocalTip activityName={att.name} />
                        </div>
                        <div style={{ color:'var(--gold)', fontSize:'0.8rem', fontFamily:'Montserrat,sans-serif', fontWeight:600, whiteSpace:'nowrap', marginLeft:'8px' }}>
                          {att.entry_fee>0 ? `🎟 ${currency} ${fmt(att.entry_fee)}` : 'Free'}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
            <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:'20px' }}>
              {places.restaurants?.length>0 && (
                <div>
                  <div className="sec-div"><div className="sec-div-title">🍽️ Where to Eat</div></div>
                  {places.restaurants.map(r => (
                    <div key={r.name} className="card" style={{ padding:'12px', marginBottom:'8px' }}>
                      <div style={{ fontFamily:'Montserrat,sans-serif', fontWeight:600, fontSize:'0.86rem', color:'var(--text-1)' }}>{r.name}</div>
                      <div style={{ color:'var(--text-3)', fontSize:'0.76rem', marginTop:'4px', fontFamily:'Inter,sans-serif' }}>
                        {r.cuisine} · ⭐ {r.rating} · ~{currency} {fmt(r.avg_cost_per_person)}/person
                      </div>
                      <div style={{ color:'var(--text-3)', fontSize:'0.73rem', fontStyle:'italic', marginTop:'3px', fontFamily:'Inter,sans-serif' }}>
                        Must try: {r.must_try_dish}
                      </div>
                    </div>
                  ))}
                </div>
              )}
              {places.activities?.length>0 && (
                <div>
                  <div className="sec-div"><div className="sec-div-title">🏄 Activities</div></div>
                  {places.activities.map(act => {
                    const actKey = `place-${act.name}`
                    const isRemoved = removedActivities.has(actKey)
                    return (
                      <div key={act.name} className="card" style={{ padding:'12px', marginBottom:'8px', opacity:isRemoved?0.4:1, transition:'opacity 0.2s' }}>
                        <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start' }}>
                          <div style={{ flex:1 }}>
                            <div style={{ fontFamily:'Montserrat,sans-serif', fontWeight:600, fontSize:'0.86rem', color:'var(--text-1)', textDecoration:isRemoved?'line-through':'none' }}>{act.name}</div>
                            <div style={{ display:'flex', gap:'8px', marginTop:'4px', flexWrap:'wrap' }}>
                              <span className="t-label" style={{ fontSize:'0.58rem', background:'rgba(201,168,76,0.1)', color:'var(--gold)', border:'1px solid rgba(201,168,76,0.2)', borderRadius:'4px', padding:'1px 6px' }}>{act.type}</span>
                              <span style={{ color:'var(--text-3)', fontSize:'0.72rem' }}>⏱ {act.duration}</span>
                            </div>
                            <div style={{ color:'#2E7D52', fontFamily:'Playfair Display,serif', fontWeight:700, fontSize:'0.9rem', marginTop:'5px' }}>
                              {currency} {fmt(act.cost_per_person)}/person
                            </div>
                          </div>
                          <button onClick={() => isRemoved ? restoreActivity(actKey) : removeActivity(actKey)}
                            className="btn-outline"
                            style={{ fontSize:'0.68rem', padding:'4px 10px', marginLeft:'8px', color:isRemoved?'#2E7D52':'rgba(160,32,32,0.8)', borderColor:isRemoved?'#2E7D52':'rgba(160,32,32,0.4)' }}>
                            {isRemoved?'↩ Add back':'✕ Remove'}
                          </button>
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          </div>
        )}

        {/* ════════════════════════════════════════════════════════════
            TAB: BUDGET
        ════════════════════════════════════════════════════════════ */}
        {tab==='budget' && (
          <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:'20px' }}>
            <div>
              <div className="card" style={{ padding:'16px', marginBottom:'14px', border:`1px solid ${surplus2>=0?'rgba(46,125,82,0.5)':'rgba(160,32,32,0.5)'}` }}>
                <div className="t-heading" style={{ fontSize:'1rem', color:surplus2>=0?'#90EE90':'#FFB3B3' }}>
                  {surplus2>=0 ? `✅ ${currency} ${fmt(Math.round(surplus2))} to spare` : `⚠️ Over by ${currency} ${fmt(Math.abs(Math.round(surplus2)))}`}
                </div>
                <div style={{ color:'var(--text-3)', fontSize:'0.78rem', marginTop:'3px', fontFamily:'Inter,sans-serif' }}>
                  {selectedHotel!==null ? `With ${activeHotel.name}` : 'With recommended hotel'} · {(budget.budget_status||'').replace(/_/g,' ')}
                </div>
              </div>

              {[
                ['✈️ Transport',     bdWithHotel.transport,     '#1A4A8A'],
                ['🏨 Accommodation', bdWithHotel.accommodation, 'var(--gold)'],
                ['🍽️ Food',          bdWithHotel.food,          '#2E7D52'],
                ['🎯 Activities',    bdWithHotel.activities,    '#8B5CF6'],
                ['🛍️ Misc',          bdWithHotel.miscellaneous, '#555'],
              ].map(([l,v,c]) => {
                const total = bdWithHotel.estimated_total || 1
                const pct   = ((v||0)/total*100)
                return (
                  <div key={l} style={{ marginBottom:'12px' }}>
                    <div style={{ display:'flex', justifyContent:'space-between', fontSize:'0.82rem', marginBottom:'4px' }}>
                      <span style={{ color:'var(--text-1)', fontFamily:'Inter,sans-serif' }}>{l}</span>
                      <span style={{ fontFamily:'Montserrat,sans-serif', fontWeight:600, color:'var(--text-1)' }}>
                        {currency} {fmt(Math.round(v||0))}
                        <span style={{ color:'var(--text-3)', fontWeight:400, fontSize:'0.72rem' }}> ({pct.toFixed(0)}%)</span>
                      </span>
                    </div>
                    <div className="progress-track">
                      <div className="progress-fill" style={{ width:`${Math.min(pct,100)}%`, background:c }} />
                    </div>
                  </div>
                )
              })}

              <div style={{ padding:'10px 14px', borderRadius:'9px', display:'flex', justifyContent:'space-between', background:'var(--dark-3)', border:'1px solid var(--border)' }}>
                <span style={{ color:'var(--text-3)', fontSize:'0.82rem', fontFamily:'Inter,sans-serif' }}>📆 Daily avg</span>
                <span className="t-label" style={{ color:'var(--gold)' }}>
                  {currency} {fmt(Math.round((bdWithHotel.estimated_total||0)/Math.max(prefs.num_days||5,1)))}/day
                </span>
              </div>
            </div>
            <div>
              <BudgetChart bd={bdWithHotel} currency={currency} />
              {budget.optimization_tips?.filter(t => t && !t.includes('tip1') && !t.includes('tip2')).map(tip => (
                <div key={tip} style={{ padding:'10px 14px', marginBottom:'6px', borderRadius:'0 8px 8px 0', borderLeft:'3px solid var(--gold)', background:'var(--dark-3)', color:'var(--text-1)', fontSize:'0.8rem', fontFamily:'Inter,sans-serif' }}>
                  💡 {tip}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ════════════════════════════════════════════════════════════
            TAB: WEATHER
        ════════════════════════════════════════════════════════════ */}
        {tab==='weather' && (
          <div>
            <div style={{ display:'grid', gridTemplateColumns:'repeat(4,1fr)', gap:'10px', marginBottom:'20px' }}>
              {[['🌡️ Day',weather.avg_temp_day],['🌙 Night',weather.avg_temp_night],
                ['🌧️ Rain',weather.rainfall],['☀️ Cond',(weather.conditions||'').toUpperCase()]].map(([l,v]) => (
                <div key={l} className="metric"><div className="metric-label">{l}</div><div className="metric-value" style={{ fontSize:'1rem' }}>{v||'N/A'}</div></div>
              ))}
            </div>
            <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:'16px' }}>
              <div className="card" style={{ padding:'16px' }}>
                <div className="sec-div" style={{ marginTop:0 }}><div className="sec-div-title">Suitability</div></div>
                <div style={{ lineHeight:1.8, fontFamily:'Inter,sans-serif', fontSize:'0.86rem' }}>
                  <div style={{ color:weather.beach_suitable?'#90EE90':'#FFB3B3' }}>{weather.beach_suitable?'✅':'❌'} Beach activities</div>
                  <div style={{ color:weather.outdoor_suitable?'#90EE90':'#FFB3B3' }}>{weather.outdoor_suitable?'✅':'❌'} Outdoor activities</div>
                  {weather.clothing_advice && <div style={{ color:'var(--text-2)', marginTop:'8px' }}>👕 {weather.clothing_advice}</div>}
                </div>
              </div>
              <div className="card" style={{ padding:'16px' }}>
                <div className="sec-div" style={{ marginTop:0 }}><div className="sec-div-title">Summary</div></div>
                <p style={{ color:'var(--text-2)', fontSize:'0.85rem', lineHeight:1.6, fontFamily:'Inter,sans-serif' }}>{weather.weather_summary}</p>
                {weather.weather_warnings?.map(w => w && (
                  <div key={w} style={{ marginTop:'8px', color:'var(--gold)', fontSize:'0.8rem', fontFamily:'Inter,sans-serif' }}>⚠️ {w}</div>
                ))}
              </div>
            </div>
          </div>
        )}

      </div>
    </div>
  )
}