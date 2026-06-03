// frontend/src/components/DestinationGrid.jsx
export default function DestinationGrid({ destinations, onSelect }) {
  const chunks = []
  for (let i = 0; i < destinations.length; i += 6)
    chunks.push(destinations.slice(i, i + 6))

  return (
    <div className="space-y-3">
      {chunks.map((row, ri) => (
        <div key={ri} className="grid gap-3" style={{gridTemplateColumns:`repeat(${row.length},1fr)`}}>
          {row.map(dest => (
            <button
              key={dest.name}
              onClick={() => onSelect(dest)}
              className="group relative overflow-hidden rounded-xl border-2 border-border hover:border-gold transition-all duration-200 cursor-pointer text-left"
              style={{background:'#1A1A1A'}}
            >
              <div className="relative h-[72px] overflow-hidden">
                <img
                  src={dest.img} alt={dest.name}
                  className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                  onError={e => { e.target.style.display='none' }}
                />
                <div className="absolute inset-0 bg-black/30 group-hover:bg-black/10 transition-colors" />
              </div>
              <div className="px-2 py-1.5 text-center">
                <span className="text-xs font-accent font-600 text-text-primary group-hover:text-gold transition-colors">
                  {dest.name}
                </span>
              </div>
            </button>
          ))}
        </div>
      ))}
    </div>
  )
}


// frontend/src/components/TravelStylePicker.jsx
import { useState } from 'react'

export default function TravelStylePicker({ styles, selected, onSelect, customStyle, onCustomStyle }) {
  const [showCustom, setShowCustom] = useState(selected === 'other')

  const handleSelect = (id) => {
    onSelect(id)
    setShowCustom(id === 'other')
  }

  return (
    <div>
      <div className="grid grid-cols-3 sm:grid-cols-5 gap-2 mb-4">
        {styles.map(s => (
          <button
            key={s.id}
            onClick={() => handleSelect(s.id)}
            className={`relative p-3 rounded-xl border-2 transition-all duration-200 text-center cursor-pointer ${
              selected === s.id
                ? 'border-gold bg-gradient-to-b from-[#2A1F08] to-[#1A1A1A]'
                : 'border-border bg-card hover:border-gold/40'
            }`}
          >
            <div className="text-2xl mb-1">{s.emoji}</div>
            <div className={`font-accent font-700 text-xs ${selected===s.id?'text-gold':'text-text-secondary'}`}>
              {s.label}
            </div>
            {selected === s.id && (
              <div className="absolute -top-1 -right-1 w-4 h-4 bg-gold rounded-full flex items-center justify-center text-[8px] text-dark font-700">✓</div>
            )}
          </button>
        ))}
      </div>

      {showCustom && (
        <div className="max-w-md mx-auto">
          <input
            className="input-field text-sm"
            placeholder="Describe your travel style… e.g. 'spiritual journey with photography'"
            value={customStyle}
            onChange={e => onCustomStyle(e.target.value)}
          />
          <p className="text-xs text-text-muted mt-1.5 font-body text-center">
            Our AI will interpret your style and personalise everything accordingly
          </p>
        </div>
      )}

      {selected && selected !== 'other' && styles.find(s=>s.id===selected) && (
        <p className="text-center text-xs text-text-muted font-body mt-2">
          {styles.find(s=>s.id===selected)?.description}
        </p>
      )}
    </div>
  )
}


// frontend/src/components/RecentPlans.jsx
import { motion } from 'framer-motion'
import usePlanStore from '../store/planStore'
import { getPlanResult } from '../api/client'

export default function RecentPlans({ plans }) {
  const { setResult, setPage } = usePlanStore()

  const handleView = async (plan) => {
    try {
      const res = await getPlanResult(plan.plan_id)
      if (res.data?.result) {
        setResult(res.data.result)
        setPage('results')
      }
    } catch(e) { console.error('Load plan error:', e) }
  }

  const gradeColor = { A:'#2E7D52', B:'#1A4A8A', C:'#C9A84C', D:'#B07020', F:'#B02A2A' }

  // Render in 2x3 grid
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
      {plans.slice(0, 6).map((plan, i) => (
        <motion.div
          key={plan.plan_id}
          initial={{ opacity:0, y:10 }} animate={{ opacity:1, y:0 }} transition={{ delay: i*0.05 }}
          className="card p-4 hover:border-gold/40 transition-all cursor-pointer group"
          onClick={() => handleView(plan)}
        >
          <div className="flex items-start justify-between mb-2">
            <span className="text-3xl">{plan.thumbnail_emoji}</span>
            <span className="font-accent font-700 text-xs px-2 py-0.5 rounded"
              style={{background:`${gradeColor[plan.grade]}18`,color:gradeColor[plan.grade],border:`1px solid ${gradeColor[plan.grade]}30`}}>
              {plan.grade}
            </span>
          </div>
          <div className="font-heading text-sm font-700 text-text-primary mb-1 line-clamp-1">
            {plan.trip_title}
          </div>
          <div className="text-xs text-text-muted font-body space-y-0.5">
            <div>📍 {plan.source} → {plan.destination}</div>
            <div>📅 {plan.num_days} days · {plan.currency} {plan.budget?.toLocaleString()}</div>
            <div className="capitalize">🎯 {plan.travel_style}</div>
          </div>
          <div className="mt-3 pt-2 border-t border-border flex justify-between items-center">
            <span className="text-xs text-text-muted font-body">
              {new Date(plan.created_at).toLocaleDateString('en-IN',{day:'numeric',month:'short'})}
            </span>
            <span className="text-xs text-gold font-accent font-600 group-hover:text-gold-light transition-colors">
              View →
            </span>
          </div>
        </motion.div>
      ))}
    </div>
  )
}


// frontend/src/components/NearbyPrompt.jsx
import { motion } from 'framer-motion'
import { addCityToPlan } from '../api/client'
import usePlanStore from '../store/planStore'

export default function NearbyPrompt({ cities, inPlanning = false }) {
  const { jobId, setJobId, setPlanStatus, setPage } = usePlanStore()

  const handleAdd = async (city) => {
    try {
      const res = await addCityToPlan({ job_id: jobId, city: city.name, num_days: 2 })
      setJobId(res.data.job_id)
      setPlanStatus('queued')
      if (!inPlanning) setPage('planning')
    } catch(e) { console.error('Add city error:', e) }
  }

  return (
    <motion.div
      initial={{ opacity:0, y:10 }} animate={{ opacity:1, y:0 }}
      className="card-gold p-4 rounded-xl"
    >
      <div className="flex items-center gap-2 mb-3">
        <span className="text-xl">🗺️</span>
        <div>
          <div className="font-heading font-700 text-text-primary text-sm">Want to explore nearby?</div>
          <div className="text-xs text-text-muted font-body">Add a city and we'll extend your itinerary</div>
        </div>
      </div>
      <div className="flex flex-wrap gap-2">
        {cities.map(city => (
          <button
            key={city.name}
            onClick={() => handleAdd(city)}
            className="flex items-center gap-2 bg-dark-3 border border-border hover:border-gold rounded-xl px-3 py-2 transition-all text-left group"
          >
            <span className="text-base">{city.emoji}</span>
            <div>
              <div className="font-accent font-600 text-xs text-text-primary group-hover:text-gold transition-colors">
                {city.name}
              </div>
              <div className="text-[10px] text-text-muted">{city.drive_hours}h drive</div>
            </div>
            <span className="text-gold text-xs ml-1 opacity-0 group-hover:opacity-100 transition-opacity">+2 days →</span>
          </button>
        ))}
      </div>
    </motion.div>
  )
}


// frontend/src/components/BudgetChart.jsx
import Plot from 'react-plotly.js'

export default function BudgetChart({ breakdown, currency }) {
  if (!breakdown || !Object.keys(breakdown).length) return null

  const labels = ['Transport','Accommodation','Food','Activities','Misc']
  const keys   = ['transport','accommodation','food','activities','miscellaneous']
  const values = keys.map(k => breakdown[k] || 0)
  const colors = ['#1A4A8A','#C9A84C','#2E7D52','#8B5CF6','#555555']

  return (
    <Plot
      data={[{
        type:   'pie',
        values,
        labels,
        hole:   0.55,
        marker: { colors },
        textinfo: 'percent',
        textfont: { color:'#F0EAD6', family:'Montserrat', size:11 },
        hovertemplate: `<b>%{label}</b><br>${currency} %{value:,.0f}<extra></extra>`,
      }]}
      layout={{
        paper_bgcolor: 'transparent',
        plot_bgcolor:  'transparent',
        showlegend:    true,
        legend:        { font:{ color:'#B8B0A0', family:'Inter', size:11 }, bgcolor:'transparent' },
        margin:        { t:0, b:0, l:0, r:0 },
        height:        220,
        annotations: [{
          text:     `<b>${currency}</b>`,
          x:0.5, y:0.5, showarrow:false,
          font:{ size:12, color:'#C9A84C', family:'Montserrat' },
        }],
      }}
      config={{ displayModeBar:false, responsive:true }}
      style={{ width:'100%' }}
    />
  )
}
