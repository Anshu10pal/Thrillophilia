import { useState } from 'react'

export default function TravelStylePicker({ styles, selected, onSelect, customStyle, onCustomStyle }) {
  const [showCustom, setShowCustom] = useState(selected === 'other')

  const handleSelect = (id) => {
    onSelect(id)
    setShowCustom(id === 'other')
  }

  const fallback = [
    { id:'adventure',  label:'Adventure',   emoji:'???' },
    { id:'relaxation', label:'Relaxation',  emoji:'??' },
    { id:'romance',    label:'Romance',     emoji:'??' },
    { id:'culture',    label:'Culture',     emoji:'???' },
    { id:'food',       label:'Food',        emoji:'??' },
    { id:'family',     label:'Family',      emoji:'????????' },
    { id:'nightlife',  label:'Nightlife',   emoji:'??' },
    { id:'photography',label:'Photography', emoji:'??' },
    { id:'balanced',   label:'Balanced',    emoji:'??' },
    { id:'other',      label:'Other',       emoji:'?' },
  ]

  const list = styles && styles.length > 0 ? styles : fallback

  return (
    <div>
      <div style={{ display:'grid', gridTemplateColumns:'repeat(5,1fr)', gap:'8px' }}>
        {list.map(s => (
          <button key={s.id} onClick={() => handleSelect(s.id)}
            style={{
              position:'relative', padding:'12px 8px', borderRadius:'12px',
              border: selected===s.id ? '2px solid #C9A84C' : '2px solid #2E2E2E',
              background: selected===s.id ? 'linear-gradient(180deg,#2A1F08,#1A1A1A)' : '#1E1E1E',
              cursor:'pointer', textAlign:'center', transition:'all 0.2s',
            }}>
            <div style={{ fontSize:'1.5rem', marginBottom:'4px' }}>{s.emoji}</div>
            <div style={{ fontFamily:"'Montserrat',sans-serif", fontSize:'0.68rem', fontWeight:700,
                          color: selected===s.id ? '#C9A84C' : '#B8B0A0' }}>{s.label}</div>
            {selected===s.id && (
              <div style={{ position:'absolute', top:'-4px', right:'-4px', width:'16px', height:'16px',
                            background:'#C9A84C', borderRadius:'50%', display:'flex',
                            alignItems:'center', justifyContent:'center',
                            fontSize:'8px', fontWeight:700, color:'#0D0D0D' }}>?</div>
            )}
          </button>
        ))}
      </div>
      {showCustom && (
        <div style={{ maxWidth:'480px', margin:'16px auto 0' }}>
          <input className="input-field" style={{ fontSize:'0.875rem' }}
            placeholder="e.g. spiritual journey, photography trip…"
            value={customStyle} onChange={e => onCustomStyle(e.target.value)} />
          <p style={{ textAlign:'center', fontSize:'0.72rem', color:'#888', marginTop:'6px',
                      fontFamily:"'Inter',sans-serif" }}>
            Our AI will interpret your style and personalise everything
          </p>
        </div>
      )}
    </div>
  )
}
