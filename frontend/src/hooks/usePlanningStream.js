import { useEffect } from 'react'
import { createEventSource, getPlanResult } from '../api/client'
import usePlanStore from '../store/planStore'

export function usePlanningStream(jobId) {
  const { addStreamEvent, setPlanStatus, setResult, setNearbySuggestions } = usePlanStore()
  useEffect(() => {
    if (!jobId) return
    const es = createEventSource(jobId)
    es.onmessage = e => {
      try {
        const data = JSON.parse(e.data)
        addStreamEvent(data)
        if (data.event === 'complete') {
          setPlanStatus('complete')
          getPlanResult(jobId).then(r => { if (r.data?.result) setResult(r.data.result) }).catch(() => {})
        }
        if (data.event === 'nearby_prompt' && data.cities) setNearbySuggestions(data.cities)
        if (data.event === 'error') setPlanStatus('error')
      } catch(err) { console.error('SSE parse error:', err) }
    }
    es.onerror = () => { setPlanStatus('error'); es.close() }
    return () => es.close()
  }, [jobId])
}
