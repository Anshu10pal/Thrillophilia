import { AnimatePresence, motion } from 'framer-motion'
import usePlanStore from './store/planStore'
import HeroPage from './pages/HeroPage'
import PlanningPage from './pages/PlanningPage'
import ResultsPage from './pages/ResultsPage'
import ChatPopup from './components/ChatPopup'
import './styles/globals.css'

const PAGE_VARIANTS = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1,  y: 0, transition: { duration: 0.4, ease: 'easeOut' } },
  exit:    { opacity: 0,  y: -8, transition: { duration: 0.25 } },
}

export default function App() {
  const { page, chatOpen } = usePlanStore()
  return (
    <div style={{ minHeight: '100vh', background: 'var(--dark)' }}>
      <AnimatePresence mode="wait">
        {page === 'hero'     && <motion.div key="hero"     {...PAGE_VARIANTS}><HeroPage /></motion.div>}
        {page === 'planning' && <motion.div key="planning" {...PAGE_VARIANTS}><PlanningPage /></motion.div>}
        {page === 'results'  && <motion.div key="results"  {...PAGE_VARIANTS}><ResultsPage /></motion.div>}
      </AnimatePresence>
      {chatOpen && <ChatPopup />}
    </div>
  )
}
