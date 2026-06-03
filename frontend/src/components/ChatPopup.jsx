import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import usePlanStore from '../store/planStore'
import { planTrip } from '../api/client'

const QUESTIONS = {
  destination: 'Where do you want to go?',
  source:      'Where are you travelling from?',
  num_days:    'How many days is your trip?',
  budget:      'What is your total budget? (e.g. ₹50,000)',
  travelers:   'How many people are travelling?',
}

export default function ChatPopup() {
  const {
    chatMessages, missingFields, currentQuestion,
    answerQuestion, preferences, query, travelStyle, customStyle,
    sessionId, setJobId, setPlanStatus, setPage, addChatMessage,
    setChatOpen, resetPlan,
  } = usePlanStore()

  const [input,   setInput]   = useState('')
  const [loading, setLoading] = useState(false)
  const endRef = useRef(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior:'smooth' })
  }, [chatMessages])

  const handleSend = async () => {
    if (!input.trim() || loading) return
    const field  = currentQuestion?.field || missingFields[0]
    const answer = input.trim()
    addChatMessage({ role:'user', content: answer, type:'answer' })
    setInput('')
    answerQuestion(field, answer)

    const remaining = missingFields.filter(f => f !== field)
    if (remaining.length === 0) {
      // All answered — start planning
      setLoading(true)
      addChatMessage({ role:'bot', type:'status', content:'✨ Perfect! Starting your plan now…' })
      try {
        const prefs = { ...preferences, [field]: answer }
        const res   = await planTrip({
          query, preferences: prefs,
          travel_style: travelStyle,
          custom_style: customStyle || null,
          session_id:   sessionId,
        })
        setJobId(res.data.job_id)
        setPlanStatus('queued')
        setChatOpen(false)
        setPage('planning')
      } catch(e) {
        addChatMessage({ role:'bot', type:'status', content:'❌ Something went wrong. Please try again.' })
      } finally {
        setLoading(false)
      }
    } else {
      // Ask next question
      const next = remaining[0]
      addChatMessage({
        role:'bot', type:'question',
        content: QUESTIONS[next] || `What is your ${next}?`,
        field: next,
      })
    }
  }

  const nextQuestion = currentQuestion
    ? (QUESTIONS[currentQuestion.field] || currentQuestion.question || currentQuestion)
    : null

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity:0, scale:0.94, y:16 }}
        animate={{ opacity:1, scale:1,    y:0 }}
        exit={{    opacity:0, scale:0.94, y:16 }}
        style={{
          position:'fixed', bottom:'1.5rem', right:'1.5rem',
          width:'360px', zIndex:100,
          borderRadius:'20px', overflow:'hidden',
          boxShadow:'0 24px 64px rgba(0,0,0,0.55), 0 0 0 1px rgba(201,168,76,0.25)',
        }}
      >
        {/* Header */}
        <div style={{
          background:'linear-gradient(135deg, #1A1400, #2A2000)',
          borderBottom:'2px solid var(--gold)',
          padding:'14px 16px',
          display:'flex', alignItems:'center', justifyContent:'space-between',
        }}>
          <div style={{ display:'flex', alignItems:'center', gap:'10px' }}>
            <div style={{
              width:'36px', height:'36px', borderRadius:'50%',
              background:'linear-gradient(135deg,var(--gold),var(--gold-light))',
              display:'flex', alignItems:'center', justifyContent:'center', fontSize:'1.1rem',
            }}>🧳</div>
            <div>
              <div className="t-heading" style={{ fontSize:'0.88rem', color:'var(--gold-light)' }}>Thrillophilia</div>
              <div className="t-label" style={{ fontSize:'0.6rem', color:'var(--gold)' }}>AI Concierge</div>
            </div>
          </div>
          <button
            onClick={() => setChatOpen(false)}
            style={{ background:'none', border:'none', cursor:'pointer', color:'var(--text-3)', fontSize:'1.4rem', lineHeight:1 }}
          >×</button>
        </div>

        {/* Messages */}
        <div style={{
          background:'#F8F4EE', padding:'14px', height:'260px',
          overflowY:'auto', display:'flex', flexDirection:'column', gap:'8px',
        }}>
          {chatMessages.length === 0 && (
            <div className="bubble-bot">
              👋 Hi! I'm your AI travel concierge. I'll help plan your perfect trip. Let me ask a few quick questions!
            </div>
          )}
          {chatMessages.map((msg, i) => (
            <div key={i}>
              {msg.type === 'status' ? (
                <div className="bubble-status">{msg.content}</div>
              ) : msg.role === 'user' ? (
                <div className="bubble-user">{msg.content}</div>
              ) : (
                <div>
                  {msg.type === 'question' && (
                    <div style={{
                      fontFamily:'Montserrat,sans-serif', fontSize:'0.62rem', fontWeight:700,
                      color:'#1A4A8A', letterSpacing:'0.08em', marginBottom:'3px',
                    }}>CONCIERGE</div>
                  )}
                  <div className="bubble-bot">{msg.content}</div>
                </div>
              )}
            </div>
          ))}
          <div ref={endRef} />
        </div>

        {/* Current question */}
        {nextQuestion && (
          <div style={{
            background:'#fff', borderTop:'1px solid #E8E0D0',
            padding:'10px 14px',
          }}>
            <div style={{
              background:'#fff', border:'2px solid #1A4A8A', borderRadius:'10px',
              padding:'10px 12px',
            }}>
              <div style={{ fontFamily:'Montserrat,sans-serif', fontSize:'0.62rem', fontWeight:700, color:'#1A4A8A', marginBottom:'3px' }}>
                🤖 CONCIERGE
              </div>
              <div style={{ fontFamily:'Inter,sans-serif', fontSize:'0.86rem', color:'#111', lineHeight:1.4 }}>
                {nextQuestion}
              </div>
            </div>
          </div>
        )}

        {/* Input */}
        <div style={{
          background:'#fff', padding:'10px 12px 14px',
          display:'flex', gap:'8px', alignItems:'center',
        }}>
          <input
            style={{
              flex:1, background:'#F5F0E8', border:'1px solid #DDD8D0',
              borderRadius:'10px', padding:'9px 12px', fontSize:'0.86rem',
              color:'#111', outline:'none', fontFamily:'Inter,sans-serif',
            }}
            placeholder="Type your answer…"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => { if (e.key==='Enter') handleSend() }}
            disabled={loading}
            onFocus={e => e.target.style.borderColor='#C9A84C'}
            onBlur={e => e.target.style.borderColor='#DDD8D0'}
          />
          <button
            className="btn-gold"
            onClick={handleSend}
            disabled={!input.trim() || loading}
            style={{ padding:'9px 14px', fontSize:'0.8rem', flexShrink:0 }}
          >
            {loading ? '⟳' : '→'}
          </button>
        </div>

        {/* Progress pills */}
        <div style={{
          background:'var(--dark-2)', padding:'8px 12px',
          display:'flex', justifyContent:'center', gap:'5px',
        }}>
          {['Details','Planning','Hotels','Done'].map((p,i) => (
            <span key={p} className="t-label" style={{
              fontSize:'0.58rem', padding:'3px 10px', borderRadius:'20px',
              background: i===0 ? 'linear-gradient(135deg,var(--gold),var(--gold-light))' : 'var(--dark-3)',
              color: i===0 ? '#0A0A08' : 'var(--text-3)',
            }}>{p}</span>
          ))}
        </div>
      </motion.div>
    </AnimatePresence>
  )
}
