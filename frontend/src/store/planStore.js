import { create } from 'zustand'
const sid = () => {
  let s = localStorage.getItem('t_sid')
  if (!s) { s = Math.random().toString(36).slice(2)+Date.now().toString(36); localStorage.setItem('t_sid',s) }
  return s
}
const usePlanStore = create(set => ({
  sessionId: sid(),
  jobId: null, planStatus: 'idle', result: null, streamEvents: [], progress: 0,
  currentAgent: null, page: 'hero', chatOpen: false, chatMessages: [],
  missingFields: [], currentQuestion: null, query: '', preferences: {},
  travelStyle: 'balanced', customStyle: '', recentPlans: [],
  nearbySuggestions: [], nearbyPromptShown: false,

  setPage: p => set({ page: p }),
  setJobId: j => set({ jobId: j }),
  setPlanStatus: s => set({ planStatus: s }),
  setResult: r => set({ result: r }),
  setQuery: q => set({ query: q }),
  setPreferences: p => set({ preferences: p }),
  setTravelStyle: s => set({ travelStyle: s }),
  setCustomStyle: s => set({ customStyle: s }),
  setRecentPlans: p => set({ recentPlans: p }),
  setNearbySuggestions: c => set({ nearbySuggestions: c, nearbyPromptShown: true }),
  setChatOpen: o => set({ chatOpen: o }),
  addStreamEvent: ev => set(s => ({ streamEvents: [...s.streamEvents, ev], currentAgent: ev.agent || s.currentAgent })),
  addChatMessage: m => set(s => ({ chatMessages: [...s.chatMessages, m] })),
  setMissingFields: (fields, questions) => set({ missingFields: fields, currentQuestion: questions?.[0] || null, chatOpen: fields.length > 0 }),
  answerQuestion: (field, answer) => set(s => {
    const prefs = { ...s.preferences, [field]: answer }
    const remaining = s.missingFields.filter(f => f !== field)
    return { preferences: prefs, missingFields: remaining, currentQuestion: remaining.length > 0 ? { field: remaining[0] } : null, chatOpen: remaining.length > 0 }
  }),
  resetPlan: () => set({ jobId: null, planStatus: 'idle', result: null, streamEvents: [], currentAgent: null, page: 'hero', chatOpen: false, chatMessages: [], missingFields: [], currentQuestion: null, query: '', preferences: {}, nearbySuggestions: [], nearbyPromptShown: false }),
}))
export default usePlanStore
