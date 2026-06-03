import { motion } from 'framer-motion'
import { getPlanResult } from '../api/client'
import usePlanStore from '../store/planStore'

const GRADE_COLOR = { A:'#2E7D52', B:'#1A4A8A', C:'#C9A84C', D:'#B07020', F:'#B02A2A' }

export default function RecentPlans({ plans }) {
  const { setResult, setPage } = usePlanStore()

  const handleView = async (plan) => {
    try {
      const res = await getPlanResult(plan.plan_id)
      if (res.data?.result) { setResult(res.data.result); setPage('results') }
    } catch(e) { console.error(e) }
  }

  return (
    <div style={{ display:'grid', gridTemplateColumns:'repeat(3,1fr)', gap:'16px' }}>
      {plans.slice(0,6).map((plan, i) => {
        const gc = GRADE_COLOR[plan.grade] || '#888'
        return (
          <motion.div key={plan.plan_id}
            initial={{ opacity:0, y:10 }} animate={{ opacity:1, y:0 }}
            transition={{ delay: i*0.05 }}
            onClick={() => handleView(plan)}
            style={{ background:'#1E1E1E', border:'1px solid #2E2E2E', borderRadius:'12px',
                     padding:'16px', cursor:'pointer' }}
            onMouseEnter={e => e.currentTarget.style.borderColor='rgba(201,168,76,0.4)'}
            onMouseLeave={e => e.currentTarget.style.borderColor='#2E2E2E'}>
            <div style={{ display:'flex', justifyContent:'space-between', marginBottom:'8px' }}>
              <span style={{ fontSize:'2rem' }}>{plan.thumbnail_emoji || '??'}</span>
              <span style={{ fontFamily:"'Montserrat',sans-serif", fontSize:'0.68rem', fontWeight:700,
                             padding:'2px 8px', borderRadius:'4px',
                             background:${gc}18, color:gc, border:1px solid 30 }}>
                {plan.grade || 'B'}
              </span>
            </div>
            <div style={{ fontFamily:"'Playfair Display',serif", fontWeight:700, fontSize:'0.88rem',
                          color:'#F0EAD6', marginBottom:'6px',
                          overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
              {plan.trip_title}
            </div>
            <div style={{ fontFamily:"'Inter',sans-serif", fontSize:'0.75rem', color:'#888', lineHeight:1.6 }}>
              <div>?? {plan.source} ? {plan.destination}</div>
              <div>?? {plan.num_days} days · {plan.currency} {plan.budget?.toLocaleString()}</div>
              <div className="capitalize">?? {plan.travel_style}</div>
            </div>
            <div style={{ marginTop:'10px', paddingTop:'8px', borderTop:'1px solid #2E2E2E',
                          display:'flex', justifyContent:'space-between', alignItems:'center' }}>
              <span style={{ fontSize:'0.7rem', color:'#888' }}>
                {plan.created_at ? new Date(plan.created_at).toLocaleDateString('en-IN',{day:'numeric',month:'short'}) : ''}
              </span>
              <span style={{ fontSize:'0.72rem', fontWeight:600, color:'#C9A84C',
                             fontFamily:"'Montserrat',sans-serif" }}>View ?</span>
            </div>
          </motion.div>
        )
      })}
    </div>
  )
}
