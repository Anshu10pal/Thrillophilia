import axios from 'axios'
const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'
export const api = axios.create({ baseURL: `${BASE}/api`, timeout: 30000 })
export const planTrip        = d => api.post('/plan', d)
export const getPlanResult   = id => api.get(`/plan/${id}`)
export const getPlanStatus   = id => api.get(`/plan/${id}/status`)
export const clarifyQuery    = d => api.post('/clarify', d)
export const getRecentPlans  = sid => api.get(`/recent/${sid}`)
export const getNearby       = (city, style, days) => api.get(`/nearby/${city}?style=${style}&days=${days}`)
export const getStyles       = () => api.get('/styles')
export const addCityToPlan   = d => api.post('/plan/add-city', d)
export const createEventSource = jobId => new EventSource(`${BASE}/api/stream/${jobId}`)
