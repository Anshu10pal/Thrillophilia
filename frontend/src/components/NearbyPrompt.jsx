import { motion } from 'framer-motion'
import { addCityToPlan } from '../api/client'
import usePlanStore from '../store/planStore'

export default function NearbyPrompt({ cities = [], inPlanning = false }) {
  const { jobId, setJobId, setPlanStatus, setPage } = usePlanStore()

  const handleAdd = async (city) => {
    if (!jobId) return
    try {
      const res = await addCityToPlan({ job_id: jobId, city: city.name, num_days: 2 })
      setJobId(res.data.job_id)
      setPlanStatus('queued')
      if (!inPlanning) setPage('planning')
    } catch(e) { console.error(e) }
  }

  if (!cities || cities.length === 0) return null

  return (
    <motion.div initial={{ opacity:0, y:10 }} animate={{ opacity:1, y:0 }}
      style={{ background:'linear-gradient(135deg,#1A1400,#252510)',
               border:'1px solid rgba(201,168,76,0.4)', borderRadius:'12px', padding:'16px' }}>
      <div style={{ display:'flex', alignItems:'center', gap:'8px', marginBottom:'12px' }}>
        <span style={{ fontSize:'1.2rem' }}>???</span>
        <div>
          <div style={{ fontFamily:"'Playfair Display',serif", fontWeight:700,
                        fontSize:'0.9rem', color:'#F0EAD6' }}>Want to explore nearby?</div>
          <div style={{ fontFamily:"'Inter',sans-serif", fontSize:'0.75rem', color:'#888' }}>
            Add a city and we'll extend your itinerary
          </div>
        </div>
      </div>
      <div style={{ display:'flex', flexWrap:'wrap', gap:'8px' }}>
        {cities.map(city => (
          <button key={city.name} onClick={() => handleAdd(city)}
            style={{ display:'flex', alignItems:'center', gap:'8px', background:'#252525',
                     border:'1px solid #2E2E2E', borderRadius:'12px', padding:'8px 12px',
                     cursor:'pointer', transition:'all 0.2s' }}
            onMouseEnter={e => e.currentTarget.style.borderColor='#C9A84C'}
            onMouseLeave={e => e.currentTarget.style.borderColor='#2E2E2E'}>
            <span style={{ fontSize:'1rem' }}>{city.emoji || '??'}</span>
            <div>
              <div style={{ fontFamily:"'Montserrat',sans-serif", fontSize:'0.75rem',
                            fontWeight:600, color:'#F0EAD6' }}>{city.name}</div>
              <div style={{ fontSize:'0.65rem', color:'#888' }}>{city.drive_hours}h drive</div>
            </div>
            <span style={{ fontSize:'0.72rem', color:'#C9A84C',
                           fontFamily:"'Montserrat',sans-serif" }}>+2d ?</span>
          </button>
        ))}
      </div>
    </motion.div>
  )
}
