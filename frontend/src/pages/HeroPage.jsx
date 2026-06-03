// frontend/src/pages/HeroPage.jsx
import { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import usePlanStore from '../store/planStore'
import { getStyles, getRecentPlans, clarifyQuery, planTrip, getPlanResult } from '../api/client'

const INDIA = [
  { name:'Goa',        emoji:'🏖️', tag:'Beaches & Parties',     img:'https://images.unsplash.com/photo-1512343879784-a960bf40e7f2?w=400&q=75' },
  { name:'Kerala',     emoji:'🌴', tag:'Backwaters & Ayurveda',  img:'https://images.unsplash.com/photo-1602216056096-3b40cc0c9944?w=400&q=75' },
  { name:'Rajasthan',  emoji:'🏰', tag:'Forts & Desert Safari',  img:'https://images.unsplash.com/photo-1477587458883-47145ed6736c?w=400&q=75' },
  { name:'Manali',     emoji:'🏔️', tag:'Snow & Adventure',       img:'https://images.unsplash.com/photo-1626621341517-bbf3d9990a23?w=400&q=75' },
  { name:'Andaman',    emoji:'🐚', tag:'Crystal Clear Beaches',  img:'https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=400&q=75' },
  { name:'Darjeeling', emoji:'🍵', tag:'Tea Gardens & Sunrise',  img:'https://images.unsplash.com/photo-1585136917228-ce68f7aeabce?w=400&q=75' },
  { name:'Leh Ladakh', emoji:'🗻', tag:'High Altitude Valleys',  img:'https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=400&q=75' },
  { name:'Rishikesh',  emoji:'🕉️', tag:'Yoga & River Rafting',   img:'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=400&q=75' },
  { name:'Coorg',      emoji:'☕', tag:'Coffee & Misty Hills',   img:'https://images.unsplash.com/photo-1509316785289-025f5b846b35?w=400&q=75' },
  { name:'Udaipur',    emoji:'🛶', tag:'City of Lakes',          img:'https://images.unsplash.com/photo-1524492412937-b28074a5d7da?w=400&q=75' },
  { name:'Varanasi',   emoji:'🪔', tag:'Spiritual Ghats',        img:'https://images.unsplash.com/photo-1561361058-c24e5e3d885f?w=400&q=75' },
  { name:'Mumbai',     emoji:'🌆', tag:'City That Never Sleeps', img:'https://images.unsplash.com/photo-1570168007204-dfb528c6958f?w=400&q=75' },
]

const ABROAD = [
  { name:'Bali',        emoji:'🌺', tag:'Island of the Gods',   img:'https://images.unsplash.com/photo-1537996194471-e657df975ab4?w=400&q=75' },
  { name:'Dubai',       emoji:'🏙️', tag:'Luxury & Skyscrapers', img:'https://images.unsplash.com/photo-1512453979798-5ea266f8880c?w=400&q=75' },
  { name:'Thailand',    emoji:'🐘', tag:'Temples & Beaches',    img:'https://images.unsplash.com/photo-1528360983277-13d401cdc186?w=400&q=75' },
  { name:'Maldives',    emoji:'🐠', tag:'Overwater Bliss',      img:'https://images.unsplash.com/photo-1514282401047-d79a71a590e8?w=400&q=75' },
  { name:'Paris',       emoji:'🗼', tag:'Romance & Culture',    img:'https://images.unsplash.com/photo-1502602898657-3e91760cbb34?w=400&q=75' },
  { name:'Singapore',   emoji:'🦁', tag:'Garden City',          img:'https://images.unsplash.com/photo-1525625293386-3f8f99389edd?w=400&q=75' },
  { name:'Switzerland', emoji:'🏔️', tag:'Alps & Chocolates',    img:'https://images.unsplash.com/photo-1476514525535-07fb3b4ae5f1?w=400&q=75' },
  { name:'Japan',       emoji:'⛩️', tag:'Temples & Technology', img:'https://images.unsplash.com/photo-1540959733332-eab4deabeeaf?w=400&q=75' },
  { name:'Barcelona',   emoji:'⚽', tag:'Gaudí & Beaches',      img:'https://images.unsplash.com/photo-1539037116277-4db20889f2d4?w=400&q=75' },
  { name:'New York',    emoji:'🗽', tag:'The Concrete Jungle',  img:'https://images.unsplash.com/photo-1485871981521-5b1fd3805eee?w=400&q=75' },
  { name:'London',      emoji:'🎡', tag:'History & Culture',    img:'https://images.unsplash.com/photo-1513635269975-59663e0ac1ad?w=400&q=75' },
  { name:'Santorini',   emoji:'🫐', tag:'Whitewashed Paradise', img:'https://images.unsplash.com/photo-1570077188670-e3a8d69ac5ff?w=400&q=75' },
]

const STYLE_FALLBACK = [
  { id:'adventure',   label:'Adventure',   emoji:'🏔️', color:'#E85D04' },
  { id:'relaxation',  label:'Relaxation',  emoji:'🧘', color:'#4ECDC4' },
  { id:'romance',     label:'Romance',     emoji:'💑', color:'#E63946' },
  { id:'culture',     label:'Culture',     emoji:'🏛️', color:'#C9A84C' },
  { id:'food',        label:'Food',        emoji:'🍜', color:'#F4A261' },
  { id:'family',      label:'Family',      emoji:'👨‍👩‍👧', color:'#2E7D52' },
  { id:'nightlife',   label:'Nightlife',   emoji:'🎉', color:'#7B2FBE' },
  { id:'photography', label:'Photography', emoji:'📸', color:'#1A4A8A' },
  { id:'balanced',    label:'Balanced',    emoji:'⚖️', color:'#888' },
  { id:'other',       label:'Other',       emoji:'✨', color:'#C9A84C' },
]

const GRADE_C = { A:'#2E7D52', B:'#1A4A8A', C:'#C9A84C', D:'#B07020', F:'#A02020' }

export default function HeroPage() {
  const {
    query, setQuery, travelStyle, setTravelStyle, customStyle, setCustomStyle,
    setPage, setJobId, setPlanStatus, setMissingFields, setChatOpen,
    addChatMessage, sessionId, setRecentPlans, preferences, setPreferences, setResult,
  } = usePlanStore()

  const [region,     setRegion]     = useState(null)
  const [styles,     setStyles]     = useState(STYLE_FALLBACK)
  const [recent,     setRecent]     = useState([])
  const [loading,    setLoading]    = useState(false)
  const [showCustom, setShowCustom] = useState(false)
  const textRef = useRef(null)

  useEffect(() => {
    getStyles().then(r => setStyles(r.data.styles || STYLE_FALLBACK)).catch(() => {})
    getRecentPlans(sessionId).then(r => {
      const p = r.data.plans || []
      setRecent(p); setRecentPlans(p)
    }).catch(() => {})
  }, [])

  const startPlanning = async (q, prefs) => {
    try {
      const res = await planTrip({ query:q, preferences:prefs, travel_style:travelStyle, custom_style:customStyle||null, session_id:sessionId })
      setJobId(res.data.job_id); setPlanStatus('queued'); setPage('planning')
    } catch(err) {
      addChatMessage({ role:'bot', type:'status', content:'❌ Could not start planning. Please try again.' })
    }
  }

  const triggerClarify = async (q, prefs) => {
    setLoading(true)
    try {
      const res = await clarifyQuery({ query:q, extracted:prefs })
      const { missing_fields, questions, extracted } = res.data
      const merged = { ...prefs, ...extracted }
      setPreferences(merged)
      if (missing_fields?.length > 0) {
        setMissingFields(missing_fields, questions)
        setChatOpen(true)
        addChatMessage({ role:'bot', type:'question', content:questions[0]?.question, field:questions[0]?.field })
      } else {
        await startPlanning(q, merged)
      }
    } catch(err) {
      await startPlanning(q, prefs)
    } finally { setLoading(false) }
  }

  const handleDestSelect = async (dest) => {
    const q = `I want to go to ${dest.name}`
    setQuery(q)
    const prefs = { ...preferences, destination:dest.name, currency:region==='India'?'INR':'USD' }
    setPreferences(prefs)
    addChatMessage({ role:'bot', type:'status', content:`✨ ${dest.name} — wonderful choice!` })
    await triggerClarify(q, prefs)
  }

  const handleSubmit = async () => {
    if (!query.trim() || loading) return
    addChatMessage({ role:'user', content:query, type:'query' })
    await triggerClarify(query, preferences)
  }

  const handleViewRecent = async (plan) => {
    try {
      const res = await getPlanResult(plan.plan_id)
      if (res.data?.result) { setResult(res.data.result); setPage('results') }
    } catch(e) {}
  }

  return (
    <div style={{ minHeight:'100vh', overflowY:'auto' }}>

      {/* ── HERO WITH BACKGROUND IMAGE ──────────────────────────────────── */}
      {/* Background image sits on the body using a fixed pseudo-element approach */}
      <div style={{
        position:'relative',
        minHeight:'620px',
        overflow:'hidden',
      }}>
        {/* Background image layer */}
        <img
          src="/hero-bg.jpeg"
          alt=""
          aria-hidden="true"
          style={{
            position:'absolute',
            top:0, left:0,
            width:'100%', height:'100%',
            objectFit:'cover',
            objectPosition:'center top',
            opacity:0.22,
            zIndex:0,
            pointerEvents:'none',
          }}
        />
        {/* Gradient overlay */}
        <div style={{
          position:'absolute', inset:0,
          background:'linear-gradient(180deg, rgba(10,10,8,0.6) 0%, rgba(10,10,8,0.82) 55%, rgba(10,10,8,1) 100%)',
          zIndex:1,
          pointerEvents:'none',
        }} />

        {/* Content */}
        <div style={{ position:'relative', zIndex:2 }}>

          {/* NAV */}
          <nav style={{
            display:'flex', alignItems:'center', justifyContent:'space-between',
            padding:'1.25rem 2.5rem',
            borderBottom:'1px solid rgba(255,255,255,0.05)',
          }}>
            <div className="t-display gold-text" style={{ fontSize:'1.8rem' }}>🧳 Thrillophilia</div>
            <div style={{ display:'flex', gap:'2rem' }}>
              {['Destinations','Experiences','Deals'].map(n => (
                <span key={n} className="t-label" style={{
                  color:n==='Destinations'?'var(--gold)':'var(--text-3)',
                  cursor:'pointer', fontSize:'0.65rem',
                }}>{n}</span>
              ))}
            </div>
            <button className="btn-outline" style={{ fontSize:'0.72rem', padding:'0.45rem 1.1rem' }}>Login</button>
          </nav>

          {/* HERO TEXT */}
          <div style={{ textAlign:'center', padding:'3.5rem 1rem 2.5rem' }}>
            <p className="t-label" style={{ color:'var(--gold)', marginBottom:'1.2rem' }}>
              AI-Powered Multi-Day Tour Planning
            </p>
            <h1 className="t-display" style={{
              fontSize:'clamp(3rem,6vw,5rem)', color:'var(--text-1)',
              textShadow:'0 2px 30px rgba(0,0,0,0.9)',
              marginBottom:'1rem',
            }}>
              Your Tour,<br />
              <span className="gold-text">Perfectly Personalised!</span>
            </h1>
            <p className="t-body" style={{
              color:'var(--text-2)', fontSize:'1rem', maxWidth:'520px',
              margin:'0 auto', textShadow:'0 1px 6px rgba(0,0,0,0.8)',
            }}>
              Expert-led, AI-crafted itineraries with live weather, real prices,
              and recommendations built just for you.
            </p>
          </div>

          {/* SEARCH */}
          <div style={{ maxWidth:'700px', margin:'0 auto', padding:'0 1.5rem 2.5rem' }}>
            <div style={{ position:'relative' }}>
              <textarea
                ref={textRef}
                className="input"
                style={{
                  height:'96px', resize:'none', paddingRight:'140px',
                  fontSize:'0.95rem', borderRadius:'14px',
                  background:'rgba(10,10,8,0.7)',
                  border:'1px solid rgba(201,168,76,0.4)',
                  backdropFilter:'blur(10px)',
                }}
                placeholder="e.g. 6-day Dubai honeymoon from Delhi for 2, budget ₹2,00,000 in July…"
                value={query}
                onChange={e => setQuery(e.target.value)}
                onKeyDown={e => { if (e.key==='Enter' && !e.shiftKey) { e.preventDefault(); handleSubmit() }}}
              />
              <button className="btn-gold" onClick={handleSubmit}
                disabled={loading || !query.trim()}
                style={{ position:'absolute', right:'12px', bottom:'12px' }}>
                {loading ? '⟳ Planning…' : '✨ Plan Trip'}
              </button>
            </div>
            <p className="t-body" style={{ textAlign:'center', fontSize:'0.72rem', color:'var(--text-3)', marginTop:'8px' }}>
              Press Enter or click Plan Trip — we'll ask follow-up questions if needed
            </p>
          </div>
        </div>
      </div>

      {/* ── TRAVEL STYLE ────────────────────────────────────────────────────── */}
      <section style={{ background:'var(--dark)', maxWidth:'980px', margin:'0 auto', padding:'3rem 1.5rem' }}>
        <h2 className="t-heading" style={{ fontSize:'1.7rem', textAlign:'center', color:'var(--text-1)', marginBottom:'0.5rem' }}>
          What's Your Travel Style?
        </h2>
        <p className="t-body" style={{ textAlign:'center', color:'var(--text-3)', marginBottom:'2rem', fontSize:'0.9rem' }}>
          We tailor hotels, activities, and your entire itinerary to match your vibe
        </p>
        <div style={{ display:'grid', gridTemplateColumns:'repeat(5,1fr)', gap:'10px' }}>
          {styles.map(s => (
            <motion.button key={s.id} onClick={() => { setTravelStyle(s.id); setShowCustom(s.id==='other') }}
              whileHover={{ y:-2 }} whileTap={{ scale:0.97 }}
              style={{
                position:'relative', padding:'14px 8px', borderRadius:'14px', cursor:'pointer',
                border: travelStyle===s.id ? `2px solid ${s.color||'var(--gold)'}` : '1px solid var(--border)',
                background: travelStyle===s.id ? `linear-gradient(180deg,${(s.color||'#C9A84C')}18,var(--card))` : 'var(--card)',
                textAlign:'center', transition:'all 0.2s',
              }}>
              <div style={{ fontSize:'1.6rem', marginBottom:'5px' }}>{s.emoji}</div>
              <div className="t-label" style={{ fontSize:'0.6rem', color:travelStyle===s.id?(s.color||'var(--gold)'):'var(--text-3)' }}>{s.label}</div>
              {travelStyle===s.id && (
                <div style={{ position:'absolute', top:'-5px', right:'-5px', width:'16px', height:'16px', borderRadius:'50%', background:s.color||'var(--gold)', display:'flex', alignItems:'center', justifyContent:'center', fontSize:'8px', fontWeight:700, color:'#0A0A08' }}>✓</div>
              )}
            </motion.button>
          ))}
        </div>
        <AnimatePresence>
          {showCustom && (
            <motion.div initial={{ opacity:0, height:0 }} animate={{ opacity:1, height:'auto' }} exit={{ opacity:0, height:0 }}
              style={{ maxWidth:'480px', margin:'16px auto 0', overflow:'hidden' }}>
              <input className="input" placeholder="e.g. spiritual journey, photography trip…"
                value={customStyle} onChange={e => setCustomStyle(e.target.value)} />
              <p className="t-body" style={{ fontSize:'0.72rem', color:'var(--text-3)', textAlign:'center', marginTop:'6px' }}>
                Our AI will interpret your style and personalise everything
              </p>
            </motion.div>
          )}
        </AnimatePresence>
      </section>

      {/* ── REGION + DESTINATIONS ─────────────────────────────────────────────── */}
      <section style={{ background:'var(--dark)', maxWidth:'980px', margin:'0 auto', padding:'0 1.5rem 3rem' }}>
        <div style={{ display:'flex', justifyContent:'center', gap:'10px', marginBottom:'2rem' }}>
          {['India','Abroad'].map(r => (
            <button key={r} onClick={() => setRegion(region===r?null:r)}
              className={region===r?'btn-gold':'btn-outline'}
              style={{ fontSize:'0.82rem', padding:'0.6rem 1.6rem' }}>
              {r==='India'?'🇮🇳':'🌍'} {r}
            </button>
          ))}
        </div>
        <AnimatePresence>
          {region && (
            <motion.div initial={{ opacity:0, y:12 }} animate={{ opacity:1, y:0 }} exit={{ opacity:0, y:-8 }}>
              <p className="t-label" style={{ color:'var(--gold)', marginBottom:'1rem', textAlign:'center' }}>Popular in {region}</p>
              {[0,6].map(start => (
                <div key={start} style={{ display:'grid', gridTemplateColumns:'repeat(6,1fr)', gap:'10px', marginBottom:'10px' }}>
                  {(region==='India'?INDIA:ABROAD).slice(start,start+6).map(dest => (
                    <motion.button key={dest.name} onClick={() => handleDestSelect(dest)}
                      whileHover={{ y:-3, boxShadow:'0 8px 24px rgba(0,0,0,0.4)' }}
                      whileTap={{ scale:0.97 }} disabled={loading}
                      style={{ background:'var(--card)', border:'1px solid var(--border)', borderRadius:'12px', overflow:'hidden', cursor:'pointer', padding:0, transition:'border-color 0.2s', opacity:loading?0.6:1 }}
                      onMouseEnter={e=>e.currentTarget.style.borderColor='rgba(201,168,76,0.5)'}
                      onMouseLeave={e=>e.currentTarget.style.borderColor='var(--border)'}>
                      <div style={{ position:'relative', height:'72px', overflow:'hidden' }}>
                        <img src={dest.img} alt={dest.name} style={{ width:'100%', height:'100%', objectFit:'cover' }}
                          onError={e=>{e.target.style.background='var(--dark-3)';e.target.style.display='none'}} />
                        <div style={{ position:'absolute', inset:0, background:'linear-gradient(to bottom,transparent 40%,rgba(0,0,0,0.5))' }} />
                        <span style={{ position:'absolute', top:'6px', left:'6px', fontSize:'14px' }}>{dest.emoji}</span>
                      </div>
                      <div style={{ padding:'6px 8px 8px' }}>
                        <div className="t-label" style={{ fontSize:'0.6rem', color:'var(--text-1)', marginBottom:'1px' }}>{dest.name}</div>
                        <div style={{ fontSize:'0.55rem', color:'var(--text-3)', fontFamily:'Inter,sans-serif' }}>{dest.tag}</div>
                      </div>
                    </motion.button>
                  ))}
                </div>
              ))}
            </motion.div>
          )}
        </AnimatePresence>
      </section>

      {/* ── RECENT PLANS ──────────────────────────────────────────────────────── */}
      {recent.length > 0 && (
        <section style={{ background:'var(--dark)', maxWidth:'980px', margin:'0 auto', padding:'0 1.5rem 4rem' }}>
          <h2 className="t-heading" style={{ fontSize:'1.5rem', color:'var(--text-1)', marginBottom:'4px' }}>
            How about these plans already explored
          </h2>
          <p className="t-body" style={{ color:'var(--text-3)', fontSize:'0.85rem', marginBottom:'1.2rem' }}>Revisit or replan a previous trip</p>
          <div style={{ display:'grid', gridTemplateColumns:'repeat(3,1fr)', gap:'14px' }}>
            {recent.slice(0,6).map((plan,i) => {
              const gc = GRADE_C[plan.grade]||'#888'
              return (
                <motion.div key={plan.plan_id} initial={{ opacity:0, y:10 }} animate={{ opacity:1, y:0 }}
                  transition={{ delay:i*0.06 }} className="card" style={{ padding:'16px', cursor:'pointer' }}
                  whileHover={{ y:-2 }} onClick={() => handleViewRecent(plan)}>
                  <div style={{ display:'flex', justifyContent:'space-between', marginBottom:'10px' }}>
                    <span style={{ fontSize:'2rem' }}>{plan.thumbnail_emoji||'✈️'}</span>
                    <span className="t-label" style={{ fontSize:'0.62rem', padding:'2px 8px', borderRadius:'5px', background:`${gc}18`, color:gc, border:`1px solid ${gc}30` }}>
                      Grade {plan.grade||'B'}
                    </span>
                  </div>
                  <div className="t-heading" style={{ fontSize:'0.88rem', color:'var(--text-1)', marginBottom:'8px', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
                    {plan.trip_title}
                  </div>
                  <div className="t-body" style={{ fontSize:'0.75rem', color:'var(--text-3)', lineHeight:1.7 }}>
                    <div>📍 {plan.source} → {plan.destination}</div>
                    <div>📅 {plan.num_days} days · {plan.currency} {plan.budget?.toLocaleString()}</div>
                    <div className="t-label" style={{ fontSize:'0.58rem', marginTop:'2px' }}>🎯 {plan.travel_style}</div>
                  </div>
                  <div style={{ marginTop:'10px', paddingTop:'8px', borderTop:'1px solid var(--border)', display:'flex', justifyContent:'space-between', alignItems:'center' }}>
                    <span style={{ fontSize:'0.7rem', color:'var(--text-3)' }}>
                      {plan.created_at ? new Date(plan.created_at).toLocaleDateString('en-IN',{day:'numeric',month:'short'}) : ''}
                    </span>
                    <span className="t-label" style={{ fontSize:'0.6rem', color:'var(--gold)' }}>View →</span>
                  </div>
                </motion.div>
              )
            })}
          </div>
        </section>
      )}

      <footer style={{ background:'var(--dark)', borderTop:'1px solid rgba(255,255,255,0.04)', padding:'2rem', textAlign:'center' }}>
        <p className="t-body" style={{ color:'var(--text-3)', fontSize:'0.78rem' }}>© 2025 Thrillophilia · AI-Powered Travel Planning</p>
      </footer>
    </div>
  )
}