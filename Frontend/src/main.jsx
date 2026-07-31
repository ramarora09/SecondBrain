import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import SecondBrainApp from './SecondBrainApp.jsx'
import './theme.css'
import './index.css'
import './secondbrain.css'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <SecondBrainApp />
  </StrictMode>,
)
